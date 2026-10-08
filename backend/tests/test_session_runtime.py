from datetime import timedelta
import sqlite3

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

from app.db.database import create_database, initialize_database
from app.main import create_app
from app.models import (
    Concept, Exercise, ExerciseAttempt, LearningEvent, ReviewSchedule,
    SessionActivity, StudentConceptState, StudySession,
)
from app.schemas.domain import AttemptInput, ConceptData, SessionPlan
from app.services.planner.session_builder import SessionBuilder
from app.services.session_runtime import SessionRuntime
from app.runtime_example import run_example


def _exercise(db, slug="heuristica-1"):
    return db.scalar(select(Exercise).where(Exercise.slug == slug))


def _plan(db, now, minutes=40, slug="heuristica", strategy="diagnostic", include_astar=False):
    concept = db.scalar(select(Concept).where(Concept.slug == slug))
    ids = list(db.scalars(select(Exercise.id).where(Exercise.concept_id == concept.id).order_by(Exercise.id)))
    activities = SessionBuilder().build(ConceptData.model_validate(concept, from_attributes=True),
                                        8 if strategy == "diagnostic" else 20, 1, strategy, ids)
    if include_astar:
        target = db.scalar(select(Concept).where(Concept.slug == "astar"))
        target_ids = list(db.scalars(select(Exercise.id).where(Exercise.concept_id == target.id).order_by(Exercise.id)))
        activities += SessionBuilder().build(ConceptData.model_validate(target, from_attributes=True),
                                             8, 2, "diagnostic", target_ids)
    used = sum(a.estimated_minutes for a in activities)
    return SessionPlan(student_id=1, available_minutes=minutes, planned_minutes=used,
                       reserve_minutes=minutes - used, generated_at=now, activities=activities,
                       ranking=[], notes=[])


def _answer(activity_id, value, hints=0, actual=None):
    return {"activity_id": activity_id, "answer": value, "hints_used": hints,
            "response_time": 12.5, "self_confidence": .6, "actual_minutes": actual}


def test_s_diagnostic_correct_independent_updates_evidence_and_advances(db, now):
    runtime = SessionRuntime()
    study = runtime.start(db, _plan(db, now), now)
    first = db.get(SessionActivity, study.current_activity_id)
    _, attempt, decision = runtime.answer(db, study.id, first.id, AttemptInput(
        answer=1, response_time=12.5), now)
    db.commit()
    assert attempt.correct and attempt.is_independent
    assert decision.action == "INSERT_CONFIRMATION"
    state = db.get(StudentConceptState, (1, first.concept_id))
    assert state.evidence_count == 1 and state.mastery is not None
    assert study.current_activity_id != first.id
    assert db.get(SessionActivity, study.current_activity_id).is_conditional
    assert db.get(SessionActivity, study.current_activity_id).exercise_id != first.exercise_id
    assert db.get(ReviewSchedule, db.scalar(select(ReviewSchedule.id))).due_at == now + timedelta(days=1)
    assert any(e.payload.get("decision") == "INSERT_CONFIRMATION" for e in db.scalars(select(LearningEvent)))


def test_t_diagnostic_error_inserts_explanation_guided_and_later_retry(db, now):
    runtime = SessionRuntime()
    study = runtime.start(db, _plan(db, now, include_astar=True), now)
    first_id = study.current_activity_id
    _, attempt, decision = runtime.answer(db, study.id, first_id, AttemptInput(
        answer=0, response_time=15), now)
    db.commit()
    assert not attempt.correct and decision.action == "INSERT_GUIDED_PRACTICE"
    assert [a.activity_type for a in decision.activities][:2] == ["EXPLANATION", "GUIDED_EXERCISE"]
    current = db.get(SessionActivity, study.current_activity_id)
    assert current.activity_type == "EXPLANATION" and current.is_conditional
    assert current.adaptation_reason == decision.reason
    assert study.used_minutes <= study.available_minutes


def test_u_hinted_answer_is_assisted_and_requests_independent_confirmation(db, now):
    runtime = SessionRuntime()
    study = runtime.start(db, _plan(db, now), now)
    first = db.get(SessionActivity, study.current_activity_id)
    _, attempt, decision = runtime.answer(db, study.id, first.id, AttemptInput(
        answer=1, hints_used=1, response_time=20), now)
    state = db.get(StudentConceptState, (1, first.concept_id))
    assert attempt.correct and not attempt.is_independent
    assert state.mastery is None and state.evidence_count == 0
    assert decision.action == "INSERT_CONFIRMATION"
    assert db.get(SessionActivity, study.current_activity_id).exercise_id != first.exercise_id


def test_scheduled_question_is_not_inserted_twice_for_confirmation(db, now):
    runtime = SessionRuntime()
    study = runtime.start(db, _plan(db, now, slug="bfs", strategy="review"), now)
    first = db.get(SessionActivity, study.current_activity_id)
    _, _, decision = runtime.answer(db, study.id, first.id,
        AttemptInput(answer="fila", hints_used=1, response_time=12), now)
    assert decision.action == "CONTINUE_TO_CONFIRMATION"
    assert not decision.activities
    next_activity = db.get(SessionActivity, study.current_activity_id)
    assert next_activity.activity_type == "QUIZ"
    assert next_activity.exercise_id != first.exercise_id


def test_v_correct_delayed_review_advances_interval(db, now):
    exercise = _exercise(db, "bfs-1")
    state = StudentConceptState(student_id=1, concept_id=exercise.concept_id, mastery=.85,
        retention=.5, evidence_count=10, evidence_confidence=.8, independent_correct=8,
        times_seen=10, times_attempted=10, times_correct=8,
        last_seen_at=now - timedelta(days=3), stability_days=10,
        next_review_at=now - timedelta(days=1), status="REVIEW_DUE")
    db.add(state)
    db.add(ReviewSchedule(student_id=1, concept_id=exercise.concept_id,
                          stage=0, due_at=now - timedelta(days=1), updated_at=now - timedelta(days=3)))
    db.flush()
    runtime = SessionRuntime()
    study = runtime.start(db, _plan(db, now, slug="bfs", strategy="review"), now)
    _, attempt, decision = runtime.answer(db, study.id, study.current_activity_id,
        AttemptInput(answer="fila", response_time=20), now)
    db.commit()
    assert attempt.correct and attempt.attempt_kind == "DELAYED_RECALL"
    assert decision.action == "ADVANCE_REVIEW"
    review = db.scalar(select(ReviewSchedule).where(ReviewSchedule.concept_id == exercise.concept_id))
    assert review.stage == 1 and review.due_at == now + timedelta(days=3)
    assert state.stability_days > 10


def test_w_failed_review_inserts_remediation(db, now):
    runtime = SessionRuntime()
    study = runtime.start(db, _plan(db, now, slug="bfs", strategy="review"), now)
    _, _, decision = runtime.answer(db, study.id, study.current_activity_id,
        AttemptInput(answer="pilha", response_time=9), now)
    assert decision.action == "INSERT_GUIDED_PRACTICE"
    assert db.get(SessionActivity, study.current_activity_id).activity_type == "EXPLANATION"


def test_practice_error_with_known_weak_prerequisite_selects_base(db, now):
    heuristic = db.scalar(select(Concept).where(Concept.slug == "heuristica"))
    db.add(StudentConceptState(student_id=1, concept_id=heuristic.id, mastery=.15,
                               evidence_count=6, evidence_confidence=.6, status="WEAK"))
    db.flush()
    runtime = SessionRuntime()
    study = runtime.start(db, _plan(db, now, slug="astar", strategy="practice"), now)
    first = db.get(SessionActivity, study.current_activity_id)
    runtime.advance(db, study.id, first.id, now)
    current = db.get(SessionActivity, study.current_activity_id)
    assert current.exercise_id is not None
    _, _, decision = runtime.answer(db, study.id, current.id, AttemptInput(answer=0, response_time=10), now)
    assert decision.action == "INSERT_PREREQUISITE_REMEDIATION"
    assert db.get(SessionActivity, study.current_activity_id).concept_id == heuristic.id


def test_x_short_remaining_never_inserts_long_block(db, now):
    runtime = SessionRuntime()
    study = runtime.start(db, _plan(db, now, minutes=10), now)
    _, _, decision = runtime.answer(db, study.id, study.current_activity_id, AttemptInput(
        answer=0, response_time=10), now, actual_minutes=9)
    assert decision.action == "FEEDBACK_AND_SUMMARY"
    assert study.used_minutes == 9 and runtime.remaining(study) == 1
    assert study.planned_minutes <= study.available_minutes
    assert all(not a.is_conditional for a in db.scalars(select(SessionActivity)))


def test_y_skipped_conditional_activity_is_not_counted(db, now):
    runtime = SessionRuntime()
    study = runtime.start(db, _plan(db, now), now)
    initial = study.current_activity_id
    runtime.answer(db, study.id, initial, AttemptInput(answer=0, response_time=10), now)
    inserted = list(db.scalars(select(SessionActivity).where(SessionActivity.is_conditional == True)))
    assert inserted
    runtime.finish(db, study.id, now, abandon=True)
    assert study.status == "ABANDONED"
    assert all(a.status == "SKIPPED" and not a.executed and a.actual_minutes is None for a in inserted)
    assert study.used_minutes == db.get(SessionActivity, initial).estimated_minutes
    assert study.actual_minutes is None


def test_z_duplicate_answer_conflicts_without_duplicate_attempt(db, now):
    runtime = SessionRuntime()
    study = runtime.start(db, _plan(db, now), now)
    first = study.current_activity_id
    runtime.answer(db, study.id, first, AttemptInput(answer=1, response_time=10), now)
    from app.services.session_runtime import SessionConflict
    with pytest.raises(SessionConflict):
        runtime.answer(db, study.id, first, AttemptInput(answer=1, response_time=10), now)
    assert db.scalar(select(func.count()).select_from(ExerciseAttempt)) == 1


def test_aa_completed_session_rejects_answers(db, now):
    runtime = SessionRuntime()
    study = runtime.start(db, _plan(db, now), now)
    first = study.current_activity_id
    runtime.finish(db, study.id, now)
    assert study.status == "COMPLETED"
    from app.services.session_runtime import SessionConflict
    with pytest.raises(SessionConflict):
        runtime.answer(db, study.id, first, AttemptInput(answer=1, response_time=10), now)


def test_ab_public_api_omits_answer_key_and_prevents_duplicate(settings, now):
    app = create_app(settings)
    app.state.clock = lambda: now
    with TestClient(app) as client:
        started = client.post("/sessions/start", json={"student_id": 1, "available_minutes": 40})
        assert started.status_code == 201
        session = started.json()
        current = session["current_activity"]
        assert current["exercise"] is not None
        forbidden = ("answer_spec", "correct_index", "error_map", "\"value\": true")
        assert all(key not in started.text for key in forbidden)
        sid = session["id"]
        answer = client.post(f"/sessions/{sid}/answer", json=_answer(current["id"], 0))
        assert answer.status_code == 200
        assert all(key not in answer.text for key in forbidden)
        assert answer.json()["session"]["decisions"][-1]["reason"]
        assert answer.json()["decision"]["remaining_minutes"] < 40
        assert client.post(f"/sessions/{sid}/answer", json=_answer(current["id"], 0)).status_code == 409
        assert client.get(f"/sessions/{sid}").status_code == 200
        next_activity = answer.json()["session"]["current_activity"]
        if next_activity and next_activity["exercise"] is None:
            advanced = client.post(f"/sessions/{sid}/advance", json={"activity_id": next_activity["id"]})
            assert advanced.status_code == 200
        finished = client.post(f"/sessions/{sid}/finish", json={})
        assert finished.status_code == 200 and finished.json()["status"] == "COMPLETED"
        assert client.post(f"/sessions/{sid}/answer", json=_answer(current["id"], 0)).status_code == 409
        assert client.post(f"/sessions/{sid}/finish", json={}).status_code == 409


def test_runtime_api_resumes_after_process_restart(settings, now):
    first_app = create_app(settings)
    first_app.state.clock = lambda: now
    with TestClient(first_app) as client:
        started = client.post("/sessions/start", json={"student_id": 1, "available_minutes": 20}).json()
    second_app = create_app(settings)
    second_app.state.clock = lambda: now
    with TestClient(second_app) as client:
        restored = client.get(f"/sessions/{started['id']}").json()
        assert restored["status"] == "IN_PROGRESS"
        assert restored["current_activity"]["id"] == started["current_activity"]["id"]
        answered = client.post(f"/sessions/{started['id']}/answer", json=_answer(
            restored["current_activity"]["id"], 0))
        assert answered.status_code == 200
        assert answered.json()["session"]["used_minutes"] > 0


def test_actual_minutes_are_distinct_from_estimated_and_invalid_answer_rolls_back(db, now):
    runtime = SessionRuntime()
    study = runtime.start(db, _plan(db, now), now)
    current = study.current_activity_id
    with pytest.raises(ValueError):
        runtime.answer(db, study.id, current, AttemptInput(answer=999, response_time=1), now)
    assert db.scalar(select(func.count()).select_from(ExerciseAttempt)) == 0
    assert db.get(SessionActivity, current).status == "IN_PROGRESS"
    runtime.answer(db, study.id, current, AttemptInput(answer=0, response_time=1), now, actual_minutes=2)
    assert study.used_minutes == 2 and study.actual_minutes == 2
    assert db.get(SessionActivity, current).actual_minutes == 2
    assert study.planned_minutes <= study.available_minutes


def test_sqlite_additive_upgrade_preserves_existing_session(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as legacy:
        legacy.executescript("""
            CREATE TABLE study_sessions (id INTEGER PRIMARY KEY, student_id INTEGER,
                available_minutes INTEGER, planned_minutes INTEGER, created_at DATETIME,
                completed_at DATETIME, status VARCHAR(20), plan_snapshot JSON);
            CREATE TABLE session_activities (id INTEGER PRIMARY KEY, session_id INTEGER,
                concept_id INTEGER, exercise_id INTEGER, position INTEGER,
                activity_type VARCHAR(30), estimated_minutes INTEGER, instructions TEXT,
                completed_at DATETIME);
            INSERT INTO study_sessions (id, student_id, available_minutes, planned_minutes,
                created_at, status, plan_snapshot) VALUES (1, 1, 40, 20, '2026-10-11', 'PLANNED', '{}');
        """)
    engine, factory = create_database(f"sqlite:///{path}")
    initialize_database(engine)
    initialize_database(engine)
    with factory() as db:
        study = db.get(StudySession, 1)
        assert study.planned_minutes == 20 and study.status == "PLANNED"
        assert study.started_at is None
    engine.dispose()


def test_full_forty_minute_adaptive_runtime_example():
    result = run_example()
    assert result["final_status"] == "COMPLETED"
    assert result["used_minutes"] <= 40
    assert result["remaining_minutes"] >= 0
    trace = result["trace"]
    first = trace[0]
    assert first["concept"] == "Função heurística" and not first["correct"]
    assert first["decision"] == "INSERT_GUIDED_PRACTICE"
    assert [step["activity_type"] for step in trace[1:3]] == ["EXPLANATION", "GUIDED_EXERCISE"]
    assert trace[2]["correct"]
    assert any(step["concept"] == "A*" for step in trace)
    assert result["heuristic_review_due_at"] is not None
    assert all(step["remaining_after"] <= step["remaining_before"] for step in trace)
