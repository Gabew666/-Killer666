import json
from collections import Counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.main import create_app
from app.models import Exercise, ExerciseAttempt, StudentConceptState
from app.services.diagnostics import (
    ATLAS_AUTHORED_DIAGNOSTIC, DIAGNOSTIC_PACKAGE_PATH, DIAGNOSTIC_TARGET_KEYS,
    load_diagnostic_package, validate_diagnostic_package,
    real_diagnostic_exercises,
)


def payload():
    return json.loads(DIAGNOSTIC_PACKAGE_PATH.read_text(encoding='utf-8'))


@pytest.fixture
def real_client(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'diagnostic.db'}", content_mode='real')
    with TestClient(create_app(settings)) as client:
        yield client


def test_bank_has_two_distinct_mobile_questions_per_target():
    package = validate_diagnostic_package(payload())
    assert package.version == '0.1.0'
    assert package.content_type == ATLAS_AUTHORED_DIAGNOSTIC
    assert Counter(q.concept_key for q in package.questions) == dict.fromkeys(DIAGNOSTIC_TARGET_KEYS, 2)
    for key in DIAGNOSTIC_TARGET_KEYS:
        first, second = [q for q in package.questions if q.concept_key == key]
        assert first.prompt != second.prompt
        assert 0.3 <= first.difficulty <= 0.5
        assert 0.5 <= second.difficulty <= 0.7
    assert all(q.provenance is None and q.exercise_type != 'STRUCTURED' for q in package.questions)


@pytest.mark.parametrize('invalid', ['rubric', 'duplicate', 'missing', 'provenance', 'structured'])
def test_invalid_package_does_not_write_any_question(real_client, invalid):
    content = payload()
    last = content['questions'][-1]
    if invalid == 'rubric':
        last['answer_spec'] = {'value': 'not numeric'}
    elif invalid == 'duplicate':
        last['key'] = content['questions'][0]['key']
    elif invalid == 'missing':
        last['concept_key'] = 'inventado'
    elif invalid == 'provenance':
        last['provenance'] = {'source_id': 'falso', 'source_name': 'Falso',
                              'source_type': 'BOOK', 'source_reference': 'Falso'}
    else:
        last['exercise_type'] = 'STRUCTURED'
    with real_client.app.state.session_factory.begin() as db:
        with pytest.raises(ValueError):
            load_diagnostic_package(db, content)
        assert db.scalar(select(func.count()).select_from(Exercise)) == 28
        assert db.scalar(select(func.count()).select_from(StudentConceptState)) == 0


def test_reload_is_unchanged_and_conflict_rolls_back_prior_insert(real_client):
    with real_client.app.state.session_factory.begin() as db:
        assert load_diagnostic_package(db) == {'version': '0.1.0', 'created': 0, 'unchanged': 28}
        content = payload()
        content['questions'][0]['key'] = 'new-question-before-conflict'
        content['questions'][-1]['prompt'] += ' Alteração indevida.'
        with pytest.raises(ValueError, match='imutável alterada'):
            load_diagnostic_package(db, content)
        assert db.scalar(select(func.count()).select_from(Exercise)) == 28
        assert db.scalar(select(Exercise).where(Exercise.slug.like('%new-question-before-conflict'))) is None
        original = payload()['questions'][-1]
        saved = db.scalar(select(Exercise).where(Exercise.slug == f"atlas-diagnostic:{original['key']}"))
        assert saved.prompt == original['prompt']


def test_one_question_per_concept_is_not_enough_for_confirmation(real_client):
    with real_client.app.state.session_factory.begin() as db:
        question = db.scalar(select(Exercise).order_by(Exercise.id))
        db.delete(question)
        db.flush()
        with pytest.raises(ValueError, match='13/14'):
            real_diagnostic_exercises(db)


def test_real_session_correct_answer_uses_second_question_and_preserves_learning_on_reload(real_client):
    client = real_client
    assert len(client.get('/subjects').json()) == 1
    assert len(client.get('/student/state').json()) == 40
    start = client.post('/sessions/start', json={'student_id': 1, 'available_minutes': 20})
    assert start.status_code == 201, start.text
    session = start.json()
    first = session['current_activity']
    assert first['strategy'] == 'diagnostic'
    assert first['exercise']
    with client.app.state.session_factory() as db:
        exercises = list(db.scalars(select(Exercise)))
        assert len(exercises) == 28
        assert {e.origin_type for e in exercises} == {ATLAS_AUTHORED_DIAGNOSTIC}
        assert Counter(e.provenance['concept_key'] for e in exercises) == dict.fromkeys(DIAGNOSTIC_TARGET_KEYS, 2)
        question = db.get(Exercise, first['exercise']['id'])
        assert question.provenance['authored_by'] == 'ATLAS'
        assert question.provenance['diagnostic_version'] == '0.1.0'
        assert all(key in question.provenance for key in ('curriculum_package_id', 'curriculum_version',
                   'source_id', 'source_name', 'source_reference', 'source_page'))
        answer = question.answer_spec['correct_index']
    response = client.post(f"/sessions/{session['id']}/answer", json={
        'activity_id': first['id'], 'answer': answer, 'hints_used': 0, 'response_time': 15})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['feedback']['correct'] is True
    assert result['decision']['action'] == 'INSERT_CONFIRMATION'
    assert result['decision']['reason']
    second = result['session']['current_activity']
    assert second['concept_id'] == first['concept_id']
    assert second['exercise']['id'] != first['exercise']['id']
    assert result['session']['remaining_minutes'] < 20
    for public in (start, response, client.get(f"/sessions/{session['id']}")):
        assert all(key not in public.text for key in ('answer_spec', 'correct_index', 'provenance', 'error_map'))
    with client.app.state.session_factory.begin() as db:
        state = db.get(StudentConceptState, (1, first['concept_id']))
        assert state.mastery is not None and state.evidence_count == 1
        before = (state.mastery, state.evidence_count, state.evidence_confidence, state.retention)
        assert db.scalar(select(func.count()).select_from(ExerciseAttempt)) == 1
        load_diagnostic_package(db)
        db.refresh(state)
        assert before == (state.mastery, state.evidence_count, state.evidence_confidence, state.retention)
        assert db.scalar(select(func.count()).select_from(ExerciseAttempt)) == 1
    with client.app.state.session_factory() as db:
        question = db.get(Exercise, second['exercise']['id'])
        spec = question.answer_spec
        correct = (spec.get('correct_index') if question.exercise_type == 'MULTIPLE_CHOICE'
                   else spec['accepted'][0] if question.exercise_type == 'SHORT_EXACT'
                   else spec['value'])
    confirmed = client.post(f"/sessions/{session['id']}/answer", json={
        'activity_id': second['id'], 'answer': correct, 'hints_used': 0, 'response_time': 20})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()['feedback']['correct'] is True
    with client.app.state.session_factory() as db:
        assert db.get(StudentConceptState, (1, first['concept_id'])).evidence_count == 2
