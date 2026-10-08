from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, text

from app.models import Subject
from app.schemas.domain import (
    PlanRequest, SessionAdvanceRequest, SessionAnswerRequest, SessionFinishRequest,
    SessionPlan, StateData,
)
from app.services.curriculum import assessments_data, concepts_data, dependencies_data, states_data
from app.services.learning import generate_plan, require_student
from app.services.mastery import MasteryEngine
from app.services.session_runtime import SessionConflict, SessionNotFound, SessionRuntime

router = APIRouter()


@router.get("/health")
def health(request: Request):
    with request.app.state.session_factory() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok", "phase": 1,
            "timezone": request.app.state.settings.timezone,
            "content_mode": request.app.state.settings.content_mode}


@router.get("/subjects")
def subjects(request: Request):
    with request.app.state.session_factory() as db:
        return [{"id": s.id, "name": s.name} for s in db.scalars(select(Subject).order_by(Subject.id))]


@router.get("/subjects/{subject_id}/concepts")
def concepts(subject_id: int, request: Request):
    with request.app.state.session_factory() as db:
        if db.get(Subject, subject_id) is None:
            raise HTTPException(404, "Disciplina inexistente")
        return [c for c in concepts_data(db) if c.subject_id == subject_id]


@router.get("/dependencies")
def dependencies(request: Request):
    with request.app.state.session_factory() as db:
        return dependencies_data(db)


@router.get("/assessments")
def assessments(request: Request):
    with request.app.state.session_factory() as db:
        return assessments_data(db)


@router.get("/student/state")
def student_state(request: Request, student_id: int = 1):
    now: datetime = request.app.state.clock()
    with request.app.state.session_factory() as db:
        try:
            require_student(db, student_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        states = states_data(db, student_id)
        result = []
        engine = MasteryEngine()
        for concept in concepts_data(db):
            state = engine.at_time(states.get(concept.id, StateData(concept_id=concept.id)), now)
            result.append(state.model_dump(mode="json") | {
                "concept": concept.name,
                "low_evidence": state.evidence_count < 3 or state.evidence_confidence < .35,
                "mastery_interpretation": "NOT_DIAGNOSED" if state.mastery is None else
                    ("Estimativa com pouca evidência" if state.evidence_confidence < .35 else "Estimativa heurística"),
            })
        return result


@router.post("/sessions/plan", response_model=SessionPlan)
def plan_session(data: PlanRequest, request: Request):
    with request.app.state.session_factory() as db:
        try:
            return generate_plan(db, data.student_id, data.available_minutes,
                                 request.app.state.clock(), request.app.state.settings)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


@router.post("/sessions/start", status_code=201)
def start_session(data: PlanRequest, request: Request):
    now = request.app.state.clock()
    runtime = SessionRuntime()
    try:
        with request.app.state.session_factory.begin() as db:
            plan = generate_plan(db, data.student_id, data.available_minutes, now, request.app.state.settings)
            study = runtime.start(db, plan, now)
            return runtime.public_view(db, study)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/sessions/{session_id}")
def get_session(session_id: int, request: Request):
    runtime = SessionRuntime()
    with request.app.state.session_factory() as db:
        try:
            return runtime.public_view(db, runtime.require_session(db, session_id))
        except SessionNotFound as exc:
            raise HTTPException(404, str(exc)) from exc


@router.post("/sessions/{session_id}/answer")
def answer_session(session_id: int, data: SessionAnswerRequest, request: Request):
    runtime = SessionRuntime()
    try:
        with request.app.state.session_factory.begin() as db:
            study, attempt, decision = runtime.answer(db, session_id, data.activity_id,
                data.attempt(), request.app.state.clock(), data.actual_minutes)
            return {"session": runtime.public_view(db, study),
                    "feedback": {"correct": attempt.correct, "score": attempt.score,
                                 "error_type": attempt.error_type,
                                 "message": "Resposta correta." if attempt.correct else "Resposta incorreta; revise o conceito.",
                                 "attempt_kind": attempt.attempt_kind,
                                 "is_independent": attempt.is_independent},
                    "decision": {"action": decision.action, "reason": decision.reason,
                                 "remaining_minutes": runtime.remaining(study)}}
    except SessionNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except SessionConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/sessions/{session_id}/advance")
def advance_session(session_id: int, data: SessionAdvanceRequest, request: Request):
    runtime = SessionRuntime()
    try:
        with request.app.state.session_factory.begin() as db:
            study = runtime.advance(db, session_id, data.activity_id, request.app.state.clock(), data.actual_minutes)
            return runtime.public_view(db, study)
    except SessionNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except SessionConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/sessions/{session_id}/finish")
def finish_session(session_id: int, request: Request, data: SessionFinishRequest | None = None):
    runtime = SessionRuntime()
    try:
        with request.app.state.session_factory.begin() as db:
            study = runtime.finish(db, session_id, request.app.state.clock(), data.abandon if data else False)
            return runtime.public_view(db, study)
    except SessionNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except SessionConflict as exc:
        raise HTTPException(409, str(exc)) from exc
