from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.time import as_utc, elapsed_days
from app.models import (
    AttemptKind, Concept, Exercise, ExerciseAttempt, LearningEvent, ReviewSchedule,
    SessionActivity, Student, StudentConceptState, StudySession,
)
from app.schemas.domain import AttemptInput, AttemptSummary, Evidence, SessionPlan, StateData
from app.services.curriculum import assessments_data, concepts_data, dependencies_data, states_data
from app.services.evaluation import DeterministicEvaluator
from app.services.knowledge_graph import KnowledgeGraph
from app.services.mastery import MasteryEngine
from app.services.planner import AdaptivePlanner
from app.services.repetition import ReviewDecision, ReviewScheduler


def require_student(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise ValueError("Aluno inexistente")
    return student


def get_state(db: Session, student_id: int, concept_id: int) -> tuple[StudentConceptState, StateData]:
    require_student(db, student_id)
    if db.get(Concept, concept_id) is None:
        raise ValueError("Conceito inexistente")
    state = db.get(StudentConceptState, (student_id, concept_id))
    if state is None:
        state = StudentConceptState(student_id=student_id, concept_id=concept_id)
        db.add(state)
        db.flush()
    return state, StateData.model_validate(state, from_attributes=True)


def apply_state(record: StudentConceptState, data: StateData) -> None:
    for name, value in data.model_dump().items():
        setattr(record, name, value)


class LearningService:
    """O chamador controla begin/commit/rollback; nenhum commit parcial oculto."""

    def __init__(self, mastery: MasteryEngine | None = None, scheduler: ReviewScheduler | None = None):
        self.mastery = mastery or MasteryEngine()
        self.scheduler = scheduler or ReviewScheduler()
        self.evaluator = DeterministicEvaluator()

    def record_attempt(self, db: Session, student_id: int, exercise_id: int, data: AttemptInput,
                       now: datetime, activity_id: int | None = None) -> ExerciseAttempt:
        require_student(db, student_id)
        exercise = db.get(Exercise, exercise_id)
        if exercise is None:
            raise ValueError("Exercício inexistente")
        now = as_utc(now)
        if activity_id is not None:
            activity = db.get(SessionActivity, activity_id)
            session = db.get(StudySession, activity.session_id) if activity else None
            if not activity or activity.exercise_id != exercise_id or not session or session.student_id != student_id:
                raise ValueError("Atividade não pertence ao aluno/exercício")
            if session.status == "COMPLETED":
                raise ValueError("Sessão já finalizada")
        result = self.evaluator.evaluate(exercise, data.answer)
        record, state = get_state(db, student_id, exercise.concept_id)
        if state.last_seen_at and now < as_utc(state.last_seen_at):
            raise ValueError("Tentativa anterior à última exposição")
        previous = db.scalar(select(ExerciseAttempt).where(
            ExerciseAttempt.student_id == student_id, ExerciseAttempt.exercise_id == exercise_id
        ).order_by(ExerciseAttempt.attempt_number.desc()).limit(1))
        number = previous.attempt_number + 1 if previous else 1
        enough_spacing = (
            state.times_attempted > 0 and state.last_seen_at is not None
            and elapsed_days(state.last_seen_at, now) >= self.mastery.config.independence_hours / 24
            and (previous is None or elapsed_days(previous.occurred_at, now) >= self.mastery.config.independence_hours / 24)
        )
        kind = AttemptKind.DELAYED_RECALL if enough_spacing else (AttemptKind.RETRY if previous else AttemptKind.FIRST_ATTEMPT)
        independent = kind != AttemptKind.RETRY and data.hints_used == 0
        updated = self.mastery.update(state, Evidence(
            correct=result.correct, score=result.score, difficulty=exercise.difficulty,
            hints_used=data.hints_used, attempt_number=number, attempt_kind=kind,
            independent=independent, self_confidence=data.self_confidence, occurred_at=now,
        ))
        review = self._review(db, student_id, exercise.concept_id)
        decision = self.scheduler.schedule(
            ReviewDecision(review.stage, review.due_at) if review else None, now,
            correct=result.correct, independent=independent, delayed=kind == AttemptKind.DELAYED_RECALL,
        )
        self._save_review(db, student_id, exercise.concept_id, review, decision, now)
        updated.next_review_at = decision.due_at
        updated = self.mastery.at_time(updated, now)
        apply_state(record, updated)
        attempt = ExerciseAttempt(
            student_id=student_id, exercise_id=exercise_id, activity_id=activity_id,
            attempt_kind=kind.value, answer=data.answer, correct=result.correct, score=result.score,
            error_type=result.error_type, concepts_involved=result.concepts_involved,
            evaluator_confidence=result.confidence, feedback=result.feedback, hints_used=data.hints_used,
            attempt_number=number, response_time=data.response_time, self_confidence=data.self_confidence,
            is_independent=independent, occurred_at=now,
        )
        db.add(attempt)
        db.flush()
        db.add(LearningEvent(student_id=student_id, concept_id=exercise.concept_id, attempt_id=attempt.id,
            event_type="EXERCISE_ATTEMPT", occurred_at=now,
            payload={"kind": kind.value, "mastery_before": state.mastery, "mastery_after": updated.mastery,
                     "evidence_count": updated.evidence_count, "evidence_confidence": updated.evidence_confidence,
                     "is_independent": independent, "next_review_at": decision.due_at.isoformat()}))
        db.flush()
        return attempt

    def record_exposure(self, db: Session, student_id: int, concept_id: int, now: datetime) -> StateData:
        record, state = get_state(db, student_id, concept_id)
        now = as_utc(now)
        if state.last_seen_at and now < as_utc(state.last_seen_at):
            raise ValueError("Exposição anterior à última exposição")
        state.times_seen += 1
        state.last_seen_at = now
        review = self._review(db, student_id, concept_id)
        if review is None:
            decision = self.scheduler.schedule(None, now, correct=False, independent=False, delayed=False)
            self._save_review(db, student_id, concept_id, None, decision, now)
            state.next_review_at = decision.due_at
        state = self.mastery.at_time(state, now)
        apply_state(record, state)
        db.add(LearningEvent(student_id=student_id, concept_id=concept_id, event_type="EXPOSURE",
                             occurred_at=now, payload={"mastery_changed": False}))
        db.flush()
        return state

    @staticmethod
    def _review(db: Session, student_id: int, concept_id: int) -> ReviewSchedule | None:
        return db.scalar(select(ReviewSchedule).where(ReviewSchedule.student_id == student_id,
                                                      ReviewSchedule.concept_id == concept_id))

    @staticmethod
    def _save_review(db: Session, student_id: int, concept_id: int, review: ReviewSchedule | None,
                     decision: ReviewDecision, now: datetime) -> None:
        if review is None:
            review = ReviewSchedule(student_id=student_id, concept_id=concept_id)
            db.add(review)
        review.stage = decision.stage
        review.due_at = decision.due_at
        review.updated_at = now


def generate_plan(db: Session, student_id: int, minutes: int, now: datetime, settings: Settings) -> SessionPlan:
    require_student(db, student_id)
    graph = KnowledgeGraph(concepts_data(db), dependencies_data(db))
    attempts = [AttemptSummary(concept_id=c, correct=a.correct, occurred_at=a.occurred_at)
                for a, c in db.execute(select(ExerciseAttempt, Exercise.concept_id)
                                      .join(Exercise, Exercise.id == ExerciseAttempt.exercise_id)
                                      .where(ExerciseAttempt.student_id == student_id))]
    exercises: dict[int, list[int]] = {}
    for exercise in db.scalars(select(Exercise).order_by(Exercise.difficulty, Exercise.id)):
        exercises.setdefault(exercise.concept_id, []).append(exercise.id)
    return AdaptivePlanner(graph, timezone=settings.timezone).plan(
        student_id, minutes, states_data(db, student_id), assessments_data(db), attempts, now, exercises)


def persist_plan(db: Session, plan: SessionPlan) -> StudySession:
    require_student(db, plan.student_id)
    session = StudySession(student_id=plan.student_id, available_minutes=plan.available_minutes,
                           planned_minutes=plan.planned_minutes, created_at=plan.generated_at,
                           status="PLANNED", plan_snapshot=plan.model_dump(mode="json"))
    db.add(session)
    db.flush()
    for index, activity in enumerate(plan.activities):
        db.add(SessionActivity(session_id=session.id, position=index, concept_id=activity.concept_id,
                               exercise_id=activity.exercise_id, activity_type=activity.activity_type.value,
                               estimated_minutes=activity.estimated_minutes, instructions=activity.instructions))
    db.flush()
    return session
