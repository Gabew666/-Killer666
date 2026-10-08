from datetime import timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import (
    Assessment, AssessmentConcept, Base, Concept, ConceptDependency, Exercise,
    ExerciseAttempt, LearningEvent, ReviewSchedule, SessionActivity, StudentConceptState, StudySession,
)
from app.schemas.domain import AttemptInput, DependencyData, StateData
from app.seed import seed_database
from app.services.curriculum import add_dependency, concepts_data, dependencies_data, states_data
from app.services.evaluation import DeterministicEvaluator
from app.services.knowledge_graph import KnowledgeGraph
from app.services.learning import LearningService, generate_plan, persist_plan
from app.services.mastery import MasteryEngine


def exercise(db, slug="heuristica-1"):
    return db.scalar(select(Exercise).where(Exercise.slug == slug))


def answer(value=1, hints=0, confidence=.8):
    return AttemptInput(answer=value, hints_used=hints, response_time=32.5, self_confidence=confidence)


def test_seed_idempotent_and_preserves_progress_and_edited_content(db, now):
    counts = {t.name: db.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables}
    chosen = exercise(db)
    chosen.prompt = "Conteúdo revisado pelo usuário"
    LearningService().record_attempt(db, 1, chosen.id, answer(), now)
    db.commit()
    seed_database(db)
    db.commit()
    assert chosen.prompt == "Conteúdo revisado pelo usuário"
    assert db.get(StudentConceptState, (1, chosen.concept_id)).evidence_count == 1
    for name in ["concepts", "concept_dependencies", "exercises", "assessments", "assessment_concepts", "students"]:
        assert db.scalar(select(func.count()).select_from(Base.metadata.tables[name])) == counts[name]
    assert counts["concepts"] == 30 and counts["exercises"] == 33
    assert counts["assessment_concepts"] == 7
    KnowledgeGraph(concepts_data(db), dependencies_data(db))


def test_h_five_retries_are_one_independent_evidence_even_after_reopen(db, now):
    chosen = exercise(db)
    engine = db.get_bind()
    service = LearningService()
    first = service.record_attempt(db, 1, chosen.id, answer(), now)
    first_mastery = db.get(StudentConceptState, (1, chosen.concept_id)).mastery
    db.commit()
    for index in range(1, 5):
        with Session(engine) as reopened:
            attempt = service.record_attempt(reopened, 1, chosen.id, answer(), now + timedelta(minutes=index))
            assert attempt.attempt_kind == "RETRY"
            assert attempt.attempt_number == index + 1
            assert not attempt.is_independent
            reopened.commit()
    db.expire_all()
    state = db.get(StudentConceptState, (1, chosen.concept_id))
    assert first.attempt_kind == "FIRST_ATTEMPT"
    assert state.times_attempted == 5
    assert state.times_correct == 5
    assert state.evidence_count == 1
    assert state.evidence_confidence < .2
    assert state.mastery == first_mastery
    assert state.stability_days == 1
    assert state.self_confidence == .8
    assert db.scalar(select(func.count()).select_from(LearningEvent)) == 5


def test_i_delayed_recall_improves_retention_stability_and_confidence(db, now):
    chosen = exercise(db)
    service = LearningService()
    service.record_attempt(db, 1, chosen.id, answer(), now)
    db.commit()
    initial = states_data(db, 1)[chosen.concept_id]
    later = now + timedelta(days=3)
    before = MasteryEngine().at_time(initial, later)
    assert before.retention < .1
    attempt = service.record_attempt(db, 1, chosen.id, answer(), later)
    db.commit()
    after = states_data(db, 1)[chosen.concept_id]
    assert attempt.attempt_kind == "DELAYED_RECALL" and attempt.is_independent
    assert after.evidence_count == 2
    assert after.retention == 1
    assert after.stability_days >= 4.5
    assert after.evidence_confidence > initial.evidence_confidence + .09
    assert after.mastery > initial.mastery
    assert MasteryEngine().at_time(after, later + timedelta(days=1)).retention > .7
    assert after.next_review_at == later + timedelta(days=3)


def test_delayed_new_question_on_same_concept_is_recall(db, now):
    service = LearningService()
    service.record_attempt(db, 1, exercise(db).id, answer(), now)
    other = exercise(db, "heuristica-2")
    attempt = service.record_attempt(db, 1, other.id, answer(0), now + timedelta(days=3))
    assert attempt.attempt_kind == "DELAYED_RECALL"
    assert attempt.attempt_number == 1
    assert attempt.is_independent


def test_recent_explanation_prevents_false_delayed_recall(db, now):
    service = LearningService()
    chosen = exercise(db)
    service.record_attempt(db, 1, chosen.id, answer(), now)
    later = now + timedelta(days=3)
    service.record_exposure(db, 1, chosen.concept_id, later)
    attempt = service.record_attempt(db, 1, chosen.id, answer(), later + timedelta(minutes=1))
    assert attempt.attempt_kind == "RETRY"
    assert db.get(StudentConceptState, (1, chosen.concept_id)).evidence_count == 1


def test_hint_then_correct_retries_never_create_independent_evidence(db, now):
    service = LearningService()
    chosen = exercise(db)
    for i in range(5):
        service.record_attempt(db, 1, chosen.id, answer(hints=1 if i == 0 else 0), now + timedelta(minutes=i))
    state = db.get(StudentConceptState, (1, chosen.concept_id))
    assert state.evidence_count == 0
    assert state.mastery is None
    assert state.evidence_confidence == 0
    assert state.times_attempted == 5
    assert state.status == "NOT_DIAGNOSED"


def test_error_diagnosis_does_not_modify_unobserved_prerequisite(db, now):
    chosen = exercise(db, "astar-1")
    attempt = LearningService().record_attempt(db, 1, chosen.id, answer(0), now)
    heuristic = exercise(db).concept_id
    assert attempt.error_type == "CONCEPTUAL"
    assert heuristic in attempt.concepts_involved
    assert chosen.concept_id in attempt.concepts_involved
    assert db.get(StudentConceptState, (1, heuristic)) is None


def test_transaction_rollback_removes_attempt_state_review_event(db, now):
    chosen = exercise(db)
    LearningService().record_attempt(db, 1, chosen.id, answer(), now)
    db.rollback()
    for model in [ExerciseAttempt, StudentConceptState, ReviewSchedule, LearningEvent]:
        assert db.scalar(select(func.count()).select_from(model)) == 0


def test_timestamps_roundtrip_utc_and_response_metadata(db, now):
    chosen = exercise(db)
    offset_now = now.astimezone(timezone(timedelta(hours=9)))
    attempt = LearningService().record_attempt(db, 1, chosen.id, answer(), offset_now)
    attempt_id = attempt.id
    db.commit()
    db.expire_all()
    reread = db.get(ExerciseAttempt, attempt_id)
    assert reread.occurred_at == now
    assert reread.occurred_at.utcoffset() == timedelta(0)
    assert reread.response_time == 32.5
    assert reread.hints_used == 0
    assert reread.attempt_number == 1


def test_exposure_never_increases_mastery_or_evidence(db, now):
    chosen = exercise(db)
    service = LearningService()
    for i in range(3):
        state = service.record_exposure(db, 1, chosen.concept_id, now + timedelta(minutes=i))
    assert state.times_seen == 3
    assert state.mastery is None and state.evidence_count == 0
    assert state.next_review_at == now + timedelta(days=1)


def test_planning_and_persisting_a_session_do_not_create_evidence(db, now):
    settings = Settings(database_url="sqlite:///:memory:", timezone="UTC")
    plan = generate_plan(db, 1, 40, now, settings)
    session = persist_plan(db, plan)
    db.commit()
    assert session.plan_snapshot["ranking"][0]["components"]
    assert db.scalar(select(func.count()).select_from(SessionActivity)) == len(plan.activities)
    assert db.scalar(select(func.count()).select_from(StudentConceptState)) == 0
    assert db.scalar(select(func.count()).select_from(ExerciseAttempt)) == 0
    assert all(a.exercise_id for a in db.scalars(select(SessionActivity).where(
        SessionActivity.activity_type.in_(["INDEPENDENT_EXERCISE", "GUIDED_EXERCISE"]))))


def test_curriculum_cycle_rejected_before_persisting(db):
    concepts = {c.slug: c for c in db.scalars(select(Concept))}
    before = db.scalar(select(func.count()).select_from(ConceptDependency))
    with pytest.raises(ValueError, match="ciclo"):
        add_dependency(db, DependencyData(concept_id=concepts["heuristica"].id,
                                           prerequisite_concept_id=concepts["astar"].id))
    assert db.scalar(select(func.count()).select_from(ConceptDependency)) == before


def test_foreign_keys_and_duplicate_review_rejected(db, now):
    db.add(AssessmentConcept(assessment_id=999, concept_id=999, weight=1))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    chosen = exercise(db)
    db.add_all([ReviewSchedule(student_id=1, concept_id=chosen.concept_id, due_at=now, stage=0) for _ in range(2)])
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def correct_answer(kind, spec):
    if kind == "MULTIPLE_CHOICE":
        return spec["correct_index"]
    if kind in ("NUMERIC", "TRUE_FALSE"):
        return spec["value"]
    if kind == "SHORT_EXACT":
        return spec["accepted"][0]
    return {k: correct_answer(rule["type"], rule) for k, rule in spec["fields"].items()}


def test_all_seed_exercises_have_valid_rubrics(db):
    evaluator = DeterministicEvaluator()
    exercises = list(db.scalars(select(Exercise)))
    assert len(exercises) == 33
    assert {e.exercise_type for e in exercises} == {"MULTIPLE_CHOICE", "TRUE_FALSE", "NUMERIC", "SHORT_EXACT", "STRUCTURED"}
    for chosen in exercises:
        result = evaluator.evaluate(chosen, correct_answer(chosen.exercise_type, chosen.answer_spec))
        assert result.correct and result.score == 1, chosen.slug
