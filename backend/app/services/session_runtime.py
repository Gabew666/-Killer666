"""Máquina de estados da sessão, persistência e aplicação de decisões pedagógicas."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import as_utc
from app.models import (
    Concept, ConceptDependency, Exercise, ExerciseAttempt, LearningEvent,
    SessionActivity, StudentConceptState, StudySession,
)
from app.schemas.domain import AttemptInput, SessionPlan, StateData
from app.services.learning import LearningService, get_state, persist_plan
from app.services.session_decision import SessionDecision, SessionDecisionEngine


class SessionNotFound(ValueError):
    pass


class SessionConflict(ValueError):
    pass


class SessionRuntime:
    def __init__(self, learning: LearningService | None = None,
                 decisions: SessionDecisionEngine | None = None):
        self.learning = learning or LearningService()
        self.decisions = decisions or SessionDecisionEngine()

    def start(self, db: Session, plan: SessionPlan, now: datetime) -> StudySession:
        if not plan.activities:
            raise ValueError("Plano sem atividades disponíveis")
        study = persist_plan(db, plan)
        study.status = "IN_PROGRESS"
        study.started_at = as_utc(now)
        self._activate_next(db, study, now)
        self._event(db, study, "SESSION_STARTED", now, {"planned_minutes": study.planned_minutes})
        db.flush()
        return study

    def answer(self, db: Session, session_id: int, activity_id: int, data: AttemptInput,
               now: datetime, actual_minutes: int | None = None) -> tuple[StudySession, ExerciseAttempt, SessionDecision]:
        study, current = self._require_current(db, session_id, activity_id)
        if current.exercise_id is None:
            raise SessionConflict("Atividade atual não possui exercício; use /advance")
        spent = self._spent(study, current, actual_minutes)
        attempt = self.learning.record_attempt(db, study.student_id, current.exercise_id, data,
                                               now, activity_id=current.id)
        self._complete(study, current, spent, actual_minutes, now)
        concept = db.get(Concept, current.concept_id)
        if concept is None:
            raise SessionConflict("Atividade sem conceito válido")
        state = self.learning.mastery.at_time(get_state(db, study.student_id, concept.id)[1], now)
        fresh = self._fresh_exercise(db, study.student_id, concept.id, study.id)
        weak = self._weak_prerequisite(db, study.student_id, concept.id)
        scheduled_confirmation = any(a.concept_id == concept.id and a.exercise_id is not None
                                     and a.exercise_id != current.exercise_id
                                     for a in self._pending(db, study))
        decision = self.decisions.decide(current, attempt, state, self.remaining(study),
                                         concept.name, concept.description, fresh, weak, scheduled_confirmation)
        study.adaptation_reason = decision.reason
        skipped = []
        if decision.skip_feedback:
            for activity in self._pending(db, study):
                if activity.execution_order > current.execution_order and activity.strategy == current.strategy \
                        and activity.activity_type == "ERROR_REVIEW" and self._same_block(activity, current):
                    self._skip(activity, now, decision.reason)
                    skipped.append(activity.id)
        inserted = self._insert(db, study, current, decision, now)
        skipped.extend(self._fit_budget(db, study, now))
        self._activate_next(db, study, now)
        self._refresh_planned(db, study)
        self._event(db, study, "SESSION_DECISION", now, {
            "attempt_id": attempt.id, "activity_id": current.id, "decision": decision.action,
            "reason": decision.reason, "remaining_minutes": self.remaining(study),
            "inserted_activity_ids": inserted, "skipped_activity_ids": skipped,
        })
        db.flush()
        return study, attempt, decision

    def advance(self, db: Session, session_id: int, activity_id: int, now: datetime,
                actual_minutes: int | None = None) -> StudySession:
        study, current = self._require_current(db, session_id, activity_id)
        if current.exercise_id is not None:
            raise SessionConflict("Exercício requer resposta em /answer")
        spent = self._spent(study, current, actual_minutes)
        if current.concept_id is not None and current.activity_type in ("EXPLANATION", "EXAMPLE", "GUIDED_EXERCISE"):
            self.learning.record_exposure(db, study.student_id, current.concept_id, now)
        self._complete(study, current, spent, actual_minutes, now)
        skipped = self._fit_budget(db, study, now)
        self._activate_next(db, study, now)
        self._refresh_planned(db, study)
        self._event(db, study, "SESSION_ACTIVITY_COMPLETED", now, {
            "activity_id": current.id, "remaining_minutes": self.remaining(study),
            "skipped_activity_ids": skipped,
        })
        db.flush()
        return study

    def finish(self, db: Session, session_id: int, now: datetime, abandon: bool = False) -> StudySession:
        study = self.require_session(db, session_id)
        if study.status in ("COMPLETED", "ABANDONED"):
            raise SessionConflict("Sessão já encerrada")
        if study.status == "PLANNED" and not abandon:
            raise SessionConflict("Sessão ainda não iniciada")
        for activity in self._activities(db, study):
            if activity.status in ("PLANNED", "IN_PROGRESS"):
                self._skip(activity, now, "Sessão abandonada" if abandon else "Sessão finalizada antes desta atividade")
        study.current_activity_id = None
        study.status = "ABANDONED" if abandon else "COMPLETED"
        study.completed_at = as_utc(now)
        self._refresh_planned(db, study)
        self._event(db, study, "SESSION_FINISHED", now, {
            "status": study.status, "used_minutes": study.used_minutes,
            "remaining_minutes": self.remaining(study),
        })
        db.flush()
        return study

    @staticmethod
    def require_session(db: Session, session_id: int) -> StudySession:
        study = db.get(StudySession, session_id)
        if study is None:
            raise SessionNotFound("Sessão inexistente")
        return study

    @staticmethod
    def remaining(study: StudySession) -> int:
        return study.available_minutes - (study.used_minutes or 0)

    def public_view(self, db: Session, study: StudySession) -> dict:
        activities = self._activities(db, study)
        current = next((a for a in activities if a.id == study.current_activity_id), None)
        current_data = None
        if current is not None:
            current_data = self._public_activity(current, include_content=True, db=db)
        decisions = [event.payload for event in db.scalars(select(LearningEvent).where(
            LearningEvent.student_id == study.student_id,
            LearningEvent.event_type == "SESSION_DECISION").order_by(LearningEvent.id))
                     if event.payload.get("session_id") == study.id]
        return {
            "id": study.id, "student_id": study.student_id, "status": study.status,
            "available_minutes": study.available_minutes, "planned_minutes": study.planned_minutes,
            "used_minutes": study.used_minutes or 0, "actual_minutes": study.actual_minutes,
            "strategy": study.strategy, "adaptation_reason": study.adaptation_reason,
            "remaining_minutes": self.remaining(study), "planned_at": study.planned_at or study.created_at,
            "started_at": study.started_at, "completed_at": study.completed_at,
            "current_activity": current_data,
            "activities": [self._public_activity(a) for a in activities], "decisions": decisions,
        }

    @staticmethod
    def _public_activity(activity: SessionActivity, include_content: bool = False, db: Session | None = None) -> dict:
        data = {
            "id": activity.id, "concept_id": activity.concept_id, "activity_type": activity.activity_type,
            "strategy": activity.strategy, "status": activity.status,
            "estimated_minutes": activity.estimated_minutes, "actual_minutes": activity.actual_minutes,
            "executed": bool(activity.executed), "is_conditional": bool(activity.is_conditional),
            "adaptation_reason": activity.adaptation_reason,
            "planned_at": activity.planned_at, "started_at": activity.started_at,
            "completed_at": activity.completed_at,
        }
        if include_content:
            data["instructions"] = activity.instructions
            data["exercise"] = None
            if activity.exercise_id is not None and db is not None:
                exercise = db.get(Exercise, activity.exercise_id)
                data["exercise"] = {"id": exercise.id, "type": exercise.exercise_type,
                                    "prompt": exercise.prompt, "options": exercise.options}
        return data

    def _require_current(self, db: Session, session_id: int, activity_id: int) -> tuple[StudySession, SessionActivity]:
        study = self.require_session(db, session_id)
        if study.status != "IN_PROGRESS":
            raise SessionConflict("Sessão não está em andamento")
        if study.current_activity_id != activity_id:
            raise SessionConflict("Atividade não é a atual ou já foi respondida")
        activity = db.get(SessionActivity, activity_id)
        if activity is None or activity.session_id != study.id or activity.status != "IN_PROGRESS":
            raise SessionConflict("Atividade não está em andamento")
        return study, activity

    @staticmethod
    def _spent(study: StudySession, activity: SessionActivity, actual: int | None) -> int:
        if actual is not None and (type(actual) is not int or actual < 0):
            raise ValueError("actual_minutes deve ser inteiro não negativo")
        spent = activity.estimated_minutes if actual is None else actual
        if spent > SessionRuntime.remaining(study):
            raise SessionConflict("Tempo da atividade excede o restante da sessão")
        return spent

    @staticmethod
    def _complete(study: StudySession, activity: SessionActivity, spent: int,
                  actual: int | None, now: datetime) -> None:
        activity.status = "COMPLETED"
        activity.executed = True
        activity.completed_at = as_utc(now)
        activity.actual_minutes = actual
        study.used_minutes = (study.used_minutes or 0) + spent
        if actual is not None:
            study.actual_minutes = (study.actual_minutes or 0) + actual
        study.current_activity_id = None

    @staticmethod
    def _skip(activity: SessionActivity, now: datetime, reason: str) -> None:
        activity.status = "SKIPPED"
        activity.executed = False
        activity.completed_at = as_utc(now)
        activity.actual_minutes = None
        activity.adaptation_reason = reason

    @staticmethod
    def _same_block(candidate: SessionActivity, current: SessionActivity) -> bool:
        return candidate.block_index is not None and candidate.block_index == current.block_index

    def _activities(self, db: Session, study: StudySession) -> list[SessionActivity]:
        return list(db.scalars(select(SessionActivity).where(SessionActivity.session_id == study.id)
                               .order_by(SessionActivity.execution_order, SessionActivity.position)))

    def _pending(self, db: Session, study: StudySession) -> list[SessionActivity]:
        return [a for a in self._activities(db, study) if a.status == "PLANNED"]

    def _activate_next(self, db: Session, study: StudySession, now: datetime) -> None:
        for activity in self._pending(db, study):
            if activity.estimated_minutes > self.remaining(study):
                self._skip(activity, now, "Tempo restante menor que a duração prevista")
                continue
            activity.status = "IN_PROGRESS"
            activity.started_at = as_utc(now)
            study.current_activity_id = activity.id
            return
        study.current_activity_id = None

    def _fit_budget(self, db: Session, study: StudySession, now: datetime) -> list[int]:
        skipped = []
        pending = self._pending(db, study)
        overflow = sum(a.estimated_minutes for a in pending) - self.remaining(study)
        for activity in reversed(pending):
            if overflow <= 0:
                break
            self._skip(activity, now, "Atividade substituída para respeitar o tempo disponível")
            skipped.append(activity.id)
            overflow -= activity.estimated_minutes
        return skipped

    def _refresh_planned(self, db: Session, study: StudySession) -> None:
        future = sum(a.estimated_minutes for a in self._activities(db, study)
                     if a.status in ("PLANNED", "IN_PROGRESS"))
        study.planned_minutes = (study.used_minutes or 0) + future

    def _insert(self, db: Session, study: StudySession, current: SessionActivity,
                decision: SessionDecision, now: datetime) -> list[int]:
        if not decision.activities:
            return []
        if sum(a.estimated_minutes for a in decision.activities) > self.remaining(study):
            raise SessionConflict("Decisão excedeu o orçamento da sessão")
        existing = self._activities(db, study)
        next_orders = [a.execution_order for a in existing if a.status == "PLANNED"
                       and a.execution_order is not None and a.execution_order > current.execution_order]
        upper = min(next_orders) if next_orders else current.execution_order + 1
        gap = (upper - current.execution_order) / (len(decision.activities) + 1)
        if gap <= 0:
            raise SessionConflict("Ordem de atividades inválida")
        position = max(a.position for a in existing) + 1
        inserted = []
        for index, planned in enumerate(decision.activities):
            item = SessionActivity(
                session_id=study.id, position=position + index,
                block_index=current.block_index,
                execution_order=current.execution_order + gap * (index + 1),
                concept_id=planned.concept_id, exercise_id=planned.exercise_id,
                activity_type=planned.activity_type.value, estimated_minutes=planned.estimated_minutes,
                instructions=planned.instructions, planned_at=as_utc(now), status="PLANNED",
                strategy=planned.mode, executed=False, is_conditional=True,
                adaptation_reason=decision.reason, decision_after=False,
            )
            db.add(item)
            db.flush()
            inserted.append(item.id)
        return inserted

    @staticmethod
    def _event(db: Session, study: StudySession, event_type: str, now: datetime, payload: dict) -> None:
        db.add(LearningEvent(student_id=study.student_id, concept_id=None, event_type=event_type,
                             occurred_at=as_utc(now), payload={"session_id": study.id, **payload}))

    @staticmethod
    def _fresh_exercise(db: Session, student_id: int, concept_id: int, session_id: int) -> int | None:
        attempted = set(db.scalars(select(ExerciseAttempt.exercise_id).where(
            ExerciseAttempt.student_id == student_id)))
        scheduled = set(db.scalars(select(SessionActivity.exercise_id).where(
            SessionActivity.session_id == session_id,
            SessionActivity.status.in_(("PLANNED", "IN_PROGRESS")),
            SessionActivity.exercise_id.is_not(None))))
        return db.scalar(select(Exercise.id).where(Exercise.concept_id == concept_id,
                                                   Exercise.id.not_in(attempted | scheduled)).order_by(Exercise.difficulty, Exercise.id))

    @staticmethod
    def _weak_prerequisite(db: Session, student_id: int, concept_id: int) -> tuple[int, str, str, int | None] | None:
        candidates = []
        for dependency in db.scalars(select(ConceptDependency).where(ConceptDependency.concept_id == concept_id)):
            state = db.get(StudentConceptState, (student_id, dependency.prerequisite_concept_id))
            if state is None or state.mastery is None or state.mastery >= .6:
                continue
            concept = db.get(Concept, dependency.prerequisite_concept_id)
            exercise_id = db.scalar(select(Exercise.id).where(Exercise.concept_id == concept.id).order_by(Exercise.id))
            candidates.append((state.mastery, (concept.id, concept.name, concept.description, exercise_id)))
        return min(candidates, key=lambda item: item[0])[1] if candidates else None
