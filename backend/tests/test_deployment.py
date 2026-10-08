"""Persisted SQLite and optional real PostgreSQL deployment integration."""
import os
import uuid
from unittest.mock import patch

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import Settings
from app.db.database import create_database, initialize_database
from app.db.migrations import migration_config
from app.main import create_app
from app.models import (
    Base, Concept, ConceptDependency, CurriculumUnit, Exercise, ExerciseAttempt,
    ReviewSchedule, StudentConceptState, StudySession,
)


@pytest.fixture(params=['sqlite', 'postgresql'])
def persisted_url(request, tmp_path):
    if request.param == 'sqlite':
        yield f"sqlite:///{tmp_path / 'deployment.db'}"
        return
    url = os.getenv('ATLAS_TEST_POSTGRES_URL')
    if not url:
        pytest.skip('ATLAS_TEST_POSTGRES_URL ausente: integração PostgreSQL requer serviço real')
    engine, _ = create_database(url)
    assert engine.dialect.name == 'postgresql', 'URL de teste precisa apontar para PostgreSQL real'
    schema = 'atlas_test_' + uuid.uuid4().hex
    # Never drop application tables: each test owns only its randomly named schema.
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated_url = engine.url.update_query_dict({'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    try:
        yield isolated_url
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def upgrade(url, monkeypatch):
    monkeypatch.setenv('ATLAS_DATABASE_URL', url)
    command.upgrade(migration_config(), 'head')


def test_migrated_real_bootstrap_answer_and_restart_preserve_all_learning(persisted_url, monkeypatch):
    upgrade(persisted_url, monkeypatch)
    engine, _ = create_database(persisted_url)
    with engine.connect() as connection:
        assert set(Base.metadata.tables) <= set(inspect(connection).get_table_names())
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    engine.dispose()
    settings = Settings(database_url=persisted_url, content_mode='real', schema_mode='migrations',
                        cors_origins=('https://atlas.example.com',))
    with TestClient(create_app(settings)) as client:
        assert client.get('/health').status_code == 200
        assert len(client.get('/student/state').json()) == 40
        with client.app.state.session_factory() as db:
            counts = [db.scalar(select(func.count()).select_from(model)) for model in (
                CurriculumUnit, Concept, ConceptDependency, Exercise)]
            assert counts == [9, 40, 32, 28]
            assert {e.origin_type for e in db.scalars(select(Exercise))} == {'ATLAS_AUTHORED_DIAGNOSTIC'}
        started = client.post('/sessions/start', json={'student_id': 1, 'available_minutes': 20})
        assert started.status_code == 201, started.text
        session = started.json()
        current = session['current_activity']
        with client.app.state.session_factory() as db:
            exercise = db.get(Exercise, current['exercise']['id'])
            correct = exercise.answer_spec['correct_index']
        answered = client.post(f"/sessions/{session['id']}/answer", json={
            'activity_id': current['id'], 'answer': correct, 'hints_used': 0, 'response_time': 10})
        assert answered.status_code == 200, answered.text
        assert answered.json()['feedback']['correct'] is True
        assert answered.json()['decision']['action'] == 'INSERT_CONFIRMATION'
        assert 'answer_spec' not in answered.text
        measured = next(s for s in client.get('/student/state').json() if s['concept_id'] == current['concept_id'])
        assert measured['mastery'] is not None and measured['evidence_count'] == 1
        with client.app.state.session_factory() as db:
            state = db.get(StudentConceptState, (1, current['concept_id']))
            snapshot = (state.mastery, state.evidence_confidence, state.evidence_count, state.next_review_at)
            assert snapshot[-1].tzinfo is not None
    # A new engine and new app prove persistence, not in-process caching.
    upgrade(persisted_url, monkeypatch)
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get('/health').status_code == 200
        restored = restarted.get(f"/sessions/{session['id']}").json()
        assert restored['current_activity']['id'] == answered.json()['session']['current_activity']['id']
        with restarted.app.state.session_factory() as db:
            state = db.get(StudentConceptState, (1, current['concept_id']))
            assert snapshot == (state.mastery, state.evidence_confidence, state.evidence_count, state.next_review_at)
            attempt = db.scalar(select(ExerciseAttempt))
            assert attempt.correct and attempt.is_independent and attempt.occurred_at.tzinfo is not None
            review = db.scalar(select(ReviewSchedule))
            assert review.due_at == state.next_review_at
            assert db.get(StudySession, session['id']).used_minutes > 0
            assert db.scalar(select(func.count()).select_from(Exercise)) == 28
            assert db.scalar(select(func.count()).select_from(ExerciseAttempt)) == 1


def test_baseline_adopts_existing_current_sqlite_without_losing_state(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'existing.db'}"
    with TestClient(create_app(Settings(database_url=url, content_mode='real'))) as client:
        session = client.post('/sessions/start', json={'student_id': 1, 'available_minutes': 20}).json()
        current = session['current_activity']
        with client.app.state.session_factory() as db:
            answer = db.get(Exercise, current['exercise']['id']).answer_spec['correct_index']
        assert client.post(f"/sessions/{session['id']}/answer", json={
            'activity_id': current['id'], 'answer': answer, 'hints_used': 0,
            'response_time': 10}).status_code == 200
        before = client.get('/student/state').json()
    upgrade(url, monkeypatch)
    with TestClient(create_app(Settings(database_url=url, content_mode='real', schema_mode='migrations'))) as client:
        assert client.get(f"/sessions/{session['id']}").status_code == 200
        after = client.get('/student/state').json()
        assert [(s['mastery'], s['evidence_count'], s['next_review_at']) for s in after] == [
            (s['mastery'], s['evidence_count'], s['next_review_at']) for s in before]


def test_baseline_upgrades_known_additive_sqlite_columns(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine, _ = create_database(url)
    initialize_database(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE exercises DROP COLUMN provenance')
        connection.exec_driver_sql('ALTER TABLE exercises DROP COLUMN origin_type')
        connection.exec_driver_sql('ALTER TABLE study_sessions DROP COLUMN used_minutes')
    engine.dispose()
    upgrade(url, monkeypatch)
    engine, _ = create_database(url)
    assert {'origin_type', 'provenance'} <= {c['name'] for c in inspect(engine).get_columns('exercises')}
    assert 'used_minutes' in {c['name'] for c in inspect(engine).get_columns('study_sessions')}
    engine.dispose()


def test_migration_mode_refuses_unversioned_schema(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'unversioned.db'}", schema_mode='migrations')
    with pytest.raises(RuntimeError, match='alembic upgrade head'):
        with TestClient(create_app(settings)):
            pass


def test_baseline_adds_legacy_concept_references_without_rebuilding_rows(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'legacy-concept.db'}"
    engine, _ = create_database(url)
    with engine.begin() as connection:
        connection.exec_driver_sql('''CREATE TABLE subjects (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL UNIQUE)''')
        connection.exec_driver_sql("INSERT INTO subjects VALUES (1, 'Legacy')")
        connection.exec_driver_sql('''CREATE TABLE concepts (
            id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL REFERENCES subjects(id),
            slug VARCHAR(100) NOT NULL, name VARCHAR(200) NOT NULL, description TEXT NOT NULL,
            difficulty FLOAT NOT NULL, importance FLOAT NOT NULL, estimated_minutes INTEGER NOT NULL,
            created_at DATETIME NOT NULL)''')
        connection.exec_driver_sql("INSERT INTO concepts VALUES (1, 1, 'legacy', 'Legacy', '', 0.5, 0.5, 20, '2026-10-08')")
    engine.dispose()
    upgrade(url, monkeypatch)
    engine, _ = create_database(url)
    with engine.connect() as connection:
        assert connection.exec_driver_sql('SELECT id, unit_id, parent_concept_id FROM concepts').one() == (1, None, None)
        references = inspect(connection).get_foreign_keys('concepts')
        assert {'unit_id', 'parent_concept_id'} <= {f['constrained_columns'][0] for f in references}
    engine.dispose()


def test_health_returns_503_without_database_details(settings):
    with TestClient(create_app(settings)) as client:
        with patch('sqlalchemy.orm.Session.execute', side_effect=OperationalError('private SQL', {}, Exception('private host'))):
            response = client.get('/health')
            assert response.status_code == 503
            assert response.json() == {'detail': 'Banco de dados indisponível'}


def test_postgres_url_aliases_choose_psycopg_without_connecting():
    for url in ('postgres://user@localhost/atlas', 'postgresql://user@localhost/atlas',
                'postgresql+psycopg://user@localhost/atlas'):
        engine, _ = create_database(url)
        assert engine.dialect.name == 'postgresql'
        assert engine.dialect.driver == 'psycopg'
        engine.dispose()


def test_postgres_defaults_to_migrations_in_environment(monkeypatch):
    monkeypatch.setenv('ATLAS_DATABASE_URL', 'postgresql://user@localhost/atlas')
    monkeypatch.delenv('ATLAS_SCHEMA_MODE', raising=False)
    assert Settings.from_env().schema_mode == 'migrations'
    monkeypatch.setenv('ATLAS_SCHEMA_MODE', 'invalid')
    with pytest.raises(ValueError, match='ATLAS_SCHEMA_MODE'):
        Settings.from_env()
