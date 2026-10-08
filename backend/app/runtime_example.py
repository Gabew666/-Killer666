"""Execução sintética e reproduzível, isolada do banco do usuário."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import select

from app.core.config import Settings
from app.db.database import create_database, initialize_database
from app.models import Concept, Exercise, ReviewSchedule, SessionActivity, StudentConceptState
from app.schemas.domain import AttemptInput
from app.seed import seed_database
from app.services.learning import generate_plan
from app.services.session_runtime import SessionRuntime


def _correct_answer(kind: str, spec: dict):
    if kind == "MULTIPLE_CHOICE":
        return spec["correct_index"]
    if kind in ("NUMERIC", "TRUE_FALSE"):
        return spec["value"]
    if kind == "SHORT_EXACT":
        return spec["accepted"][0]
    return {key: _correct_answer(rule["type"], rule) for key, rule in spec["fields"].items()}


def run_example() -> dict:
    now = datetime(2026, 10, 11, 22, tzinfo=timezone.utc)
    settings = Settings("sqlite:///:memory:", "America/Sao_Paulo")
    engine, factory = create_database(settings.database_url)
    initialize_database(engine)
    runtime = SessionRuntime()
    with factory() as db:
        seed_database(db)
        # Perfil sintético: bases consolidadas, heurística sem diagnóstico, A* fraco.
        for concept in db.scalars(select(Concept)):
            if concept.slug == "heuristica":
                continue
            db.add(StudentConceptState(student_id=1, concept_id=concept.id,
                mastery=.25 if concept.slug == "astar" else .88, retention=1,
                evidence_count=12, evidence_confidence=.8, independent_correct=10,
                times_attempted=12, times_correct=10, last_seen_at=now,
                stability_days=30, status="DEVELOPING"))
        db.flush()
        plan = generate_plan(db, 1, 40, now, settings)
        study = runtime.start(db, plan, now)
        trace = []
        first_question = True
        for _ in range(40):
            current_id = study.current_activity_id
            if current_id is None:
                break
            activity = db.get(SessionActivity, current_id)
            concept = db.get(Concept, activity.concept_id) if activity.concept_id else None
            before = runtime.remaining(study)
            if activity.exercise_id is not None:
                exercise = db.get(Exercise, activity.exercise_id)
                wrong_first = first_question and concept.slug == "heuristica"
                first_question = False
                response = 0 if wrong_first else _correct_answer(exercise.exercise_type, exercise.answer_spec)
                _, attempt, decision = runtime.answer(db, study.id, activity.id,
                    AttemptInput(answer=response, response_time=15, hints_used=0), now)
                result = {"correct": attempt.correct, "independent": attempt.is_independent,
                          "decision": decision.action, "reason": decision.reason}
            else:
                runtime.advance(db, study.id, activity.id, now)
                result = {}
            trace.append({"concept": concept.name if concept else "Pausa",
                          "activity_type": activity.activity_type,
                          "minutes": activity.estimated_minutes,
                          "remaining_before": before, "remaining_after": runtime.remaining(study), **result})
        else:
            raise RuntimeError("Exemplo excedeu o limite de passos")
        review = db.scalar(select(ReviewSchedule).join(Concept, Concept.id == ReviewSchedule.concept_id)
                           .where(Concept.slug == "heuristica"))
        runtime.finish(db, study.id, now)
        result = {"profile": "Perfil sintético: heurística sem diagnóstico, A* fraco",
                  "available_minutes": 40, "initial_planned_minutes": plan.planned_minutes,
                  "trace": trace, "final_status": study.status,
                  "used_minutes": study.used_minutes,
                  "remaining_minutes": runtime.remaining(study),
                  "heuristic_review_due_at": review.due_at.isoformat() if review else None,
                  "skipped_activities": [
                      {"type": a.activity_type, "reason": a.adaptation_reason}
                      for a in db.scalars(select(SessionActivity).where(
                          SessionActivity.session_id == study.id, SessionActivity.status == "SKIPPED"))],
                 }
        db.rollback()  # Não há efeitos fora do banco sintético em memória.
    engine.dispose()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_example()
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Sessão: {result['used_minutes']}/40 min; revisão de heurística: {result['heuristic_review_due_at']}")
    for step in result["trace"]:
        decision = f" → {step['decision']}" if "decision" in step else ""
        print(f"{step['remaining_before']:2}→{step['remaining_after']:2} min: "
              f"{step['concept']} · {step['activity_type']}{decision}")


if __name__ == "__main__":
    main()
