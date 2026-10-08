import json

import networkx as nx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.bootstrap import ContentModeConflict
from app.core.config import Settings
from app.core.content import REAL_CURRICULUM_PATH, REAL_PACKAGE_ID
from app.db.database import create_database
from app.main import create_app
from app.models import (
    Assessment, Concept, ConceptDependency, CurriculumPackageRecord, CurriculumUnit,
    Exercise, ReviewSchedule, StudentConceptState, StudySession, Subject,
)
from app.services.curriculum import CurriculumValidator
from app.services.diagnostics import (
    ATLAS_AUTHORED_DIAGNOSTIC, DIAGNOSTIC_TARGET_KEYS, register_atlas_diagnostic,
)


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def _settings(tmp_path, mode="real"):
    return Settings(database_url=f"sqlite:///{tmp_path / 'real.db'}", content_mode=mode)


def _question(key):
    # Synthetic test data only. No question is added to the actual curriculum package.
    return {"key": f"teste-{key}", "concept_key": key, "exercise_type": "TRUE_FALSE",
            "prompt": f"TESTE — enunciado sintético para {key}", "answer_spec": {"value": True},
            "explanation": "TESTE — correção sintética", "difficulty": 0.3}


def test_content_mode_env_is_explicit_and_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("ATLAS_CONTENT_MODE", "real")
    assert Settings.from_env().content_mode == "real"
    monkeypatch.setenv("ATLAS_CONTENT_MODE", "unknown")
    with pytest.raises(ValueError, match="ATLAS_CONTENT_MODE"):
        Settings.from_env()


def test_seed_command_refuses_real_mode_before_opening_database(monkeypatch, tmp_path):
    from app.seed.__main__ import main as seed_main

    path = tmp_path / "should-not-exist.db"
    monkeypatch.setenv("ATLAS_CONTENT_MODE", "real")
    monkeypatch.setenv("ATLAS_DATABASE_URL", f"sqlite:///{path}")
    with pytest.raises(SystemExit, match="seed provisório"):
        seed_main()
    assert not path.exists()


def test_real_package_validates_without_writing_student_state(db):
    before = _count(db, StudentConceptState)
    package = CurriculumValidator().validate(json.loads(REAL_CURRICULUM_PATH.read_text(encoding="utf-8")))
    assert (package.package_id, package.version, package.content_status) == (
        REAL_PACKAGE_ID, "0.1.0", "DRAFT")
    assert (len(package.units), len(package.concepts), len(package.dependencies)) == (9, 40, 32)
    assert package.assessments == [] and package.exercises == []
    graph = nx.DiGraph((item.prerequisite_key, item.concept_key) for item in package.dependencies)
    assert nx.is_directed_acyclic_graph(graph)
    assert len(DIAGNOSTIC_TARGET_KEYS) == 14
    assert set(DIAGNOSTIC_TARGET_KEYS) <= {concept.key for concept in package.concepts}
    assert _count(db, StudentConceptState) == before


def test_real_mode_empty_database_restart_preserves_progress_and_frontend_contract(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["content_mode"] == "real"
        subjects = client.get("/subjects").json()
        assert subjects == [{"id": 1, "name": "Inteligência Artificial Simbólica"}]
        states = client.get("/student/state").json()
        assert len(states) == 40
        assert all(state["mastery"] is None and state["status"] == "NOT_DIAGNOSED" for state in states)
        assert all({"concept_id", "concept", "mastery", "evidence_count",
                    "evidence_confidence", "next_review_at"} <= state.keys() for state in states)
        response = client.post("/sessions/start", json={"student_id": 1, "available_minutes": 20})
        assert response.status_code == 422
        assert "faltam exercícios diagnósticos" in response.json()["detail"]
    engine, factory = create_database(settings.database_url)
    with factory.begin() as db:
        assert (_count(db, Subject), _count(db, CurriculumUnit), _count(db, Concept),
                _count(db, ConceptDependency), _count(db, Assessment), _count(db, Exercise)) == (1, 9, 40, 32, 0, 0)
        expected_units = {item["key"] for item in json.loads(REAL_CURRICULUM_PATH.read_text(encoding="utf-8"))["units"]}
        assert set(db.scalars(select(CurriculumUnit.key))) == expected_units
        assert _count(db, CurriculumPackageRecord) == 1
        assert _count(db, StudySession) == 0 and _count(db, StudentConceptState) == 0
        assert db.scalar(select(Subject).where(Subject.name == "IA Simbólica")) is None
        concept = db.scalar(select(Concept).where(Concept.slug == "bfs"))
        state = StudentConceptState(student_id=1, concept_id=concept.id, mastery=0.71, retention=0.8,
                                    evidence_count=4, evidence_confidence=0.6, status="DEVELOPING")
        review = ReviewSchedule(student_id=1, concept_id=concept.id, stage=2, due_at=client.app.state.clock())
        db.add_all([state, review])
    engine.dispose()
    with TestClient(create_app(settings)) as client:
        assert len(client.get("/student/state").json()) == 40
    engine, factory = create_database(settings.database_url)
    with factory() as db:
        assert (_count(db, Subject), _count(db, CurriculumUnit), _count(db, Concept),
                _count(db, ConceptDependency), _count(db, CurriculumPackageRecord)) == (1, 9, 40, 32, 1)
        saved = db.get(StudentConceptState, (1, concept.id))
        assert (saved.mastery, saved.retention, saved.evidence_count, saved.evidence_confidence) == (0.71, 0.8, 4, 0.6)
        assert db.scalar(select(ReviewSchedule).where(ReviewSchedule.concept_id == concept.id)).stage == 2
    engine.dispose()


def test_content_modes_refuse_silent_mixing(tmp_path):
    provisional = _settings(tmp_path, "provisional")
    with TestClient(create_app(provisional)) as client:
        assert len(client.get("/student/state").json()) == 30
    engine, factory = create_database(provisional.database_url)
    with factory.begin() as db:
        first = db.scalar(select(Concept).order_by(Concept.id))
        db.add(StudentConceptState(student_id=1, concept_id=first.id, mastery=0.6,
                                   retention=0.7, evidence_count=2, evidence_confidence=0.2,
                                   status="DEVELOPING"))
    engine.dispose()
    with pytest.raises(ContentModeConflict, match="banco separado"):
        with TestClient(create_app(_settings(tmp_path))):
            pass
    engine, factory = create_database(provisional.database_url)
    with factory() as db:
        assert _count(db, Concept) == 30 and _count(db, CurriculumPackageRecord) == 0
        assert {origin for origin in db.scalars(select(Exercise.origin_type))} == {"PROVISIONAL_SEED"}
        assert db.get(StudentConceptState, (1, first.id)).mastery == 0.6
    engine.dispose()


def test_provisional_cannot_boot_real_database(tmp_path):
    with TestClient(create_app(_settings(tmp_path))):
        pass
    with pytest.raises(ContentModeConflict, match="não pode usar banco"):
        with TestClient(create_app(_settings(tmp_path, "provisional"))):
            pass


def test_authored_diagnostics_use_only_real_concepts_and_derive_source(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)):
        pass
    engine, factory = create_database(settings.database_url)
    with factory.begin() as db:
        with pytest.raises(ValueError, match="fora do escopo"):
            register_atlas_diagnostic(db, _question("conceito-inexistente"))
        exercise = register_atlas_diagnostic(db, _question("bfs"))
        assert exercise.origin_type == ATLAS_AUTHORED_DIAGNOSTIC
        assert exercise.provenance["authored_by"] == "ATLAS"
        assert exercise.provenance["concept_key"] == "bfs"
        assert exercise.provenance["source_id"]
        assert exercise.provenance["source_name"]
        assert exercise.provenance["source_reference"]
        assert exercise.provenance["source_page"] == 130
        assert _count(db, StudentConceptState) == 0
    engine.dispose()
    with TestClient(create_app(settings)) as client:
        response = client.post("/sessions/start", json={"student_id": 1, "available_minutes": 20})
        assert response.status_code == 422
        assert "1/14" in response.json()["detail"]


def test_real_diagnostic_can_start_when_all_targets_have_authored_test_questions(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)):
        pass
    engine, factory = create_database(settings.database_url)
    with factory.begin() as db:
        for key in DIAGNOSTIC_TARGET_KEYS:
            register_atlas_diagnostic(db, _question(key))
        assert _count(db, Exercise) == 14
        assert _count(db, StudentConceptState) == 0
    engine.dispose()
    with TestClient(create_app(settings)) as client:
        result = client.post("/sessions/start", json={"student_id": 1, "available_minutes": 20})
        assert result.status_code == 201, result.text
        session = result.json()
        current = session["current_activity"]
        assert current["exercise"] is not None
        with client.app.state.session_factory() as db:
            planned_keys = {db.get(Concept, activity["concept_id"]).slug
                            for activity in session["activities"] if activity["concept_id"] is not None}
            assert planned_keys and planned_keys <= set(DIAGNOSTIC_TARGET_KEYS)
            assert db.get(Exercise, current["exercise"]["id"]).origin_type == ATLAS_AUTHORED_DIAGNOSTIC
        assert "answer_spec" not in result.text
        assert "provenance" not in result.text
