"""Três cenários sintéticos, em banco isolado; não alteram o progresso de Gabriel."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from sqlalchemy import select

from app.db.database import create_database, initialize_database
from app.models import Concept, Exercise
from app.schemas.domain import AttemptSummary, StateData
from app.seed import seed_database
from app.services.curriculum import assessments_data, concepts_data, dependencies_data
from app.services.knowledge_graph import KnowledgeGraph
from app.services.planner import AdaptivePlanner


def examples() -> list[dict]:
    now = datetime(2026, 10, 11, 22, tzinfo=timezone.utc)
    engine, factory = create_database("sqlite:///:memory:")
    initialize_database(engine)
    with factory.begin() as db:
        seed_database(db)
        concepts = concepts_data(db)
        by_slug = {c.slug: c.id for c in db.scalars(select(Concept))}
        graph = KnowledgeGraph(concepts, dependencies_data(db))
        assessments = assessments_data(db)
        exercises: dict[int, list[int]] = {}
        for exercise in db.scalars(select(Exercise).order_by(Exercise.difficulty, Exercise.id)):
            exercises.setdefault(exercise.concept_id, []).append(exercise.id)
    engine.dispose()
    planner = AdaptivePlanner(graph, timezone="America/Sao_Paulo")
    consolidated = {c.id: StateData(
        concept_id=c.id, mastery=.85, evidence_count=18, evidence_confidence=.89,
        independent_correct=16, delayed_evidence_count=3, times_attempted=20,
        times_correct=18, last_seen_at=now, stability_days=30,
    ) for c in concepts}
    weak = {c: s.model_copy(deep=True) for c, s in consolidated.items()}
    weak[by_slug["heuristica"]].mastery = .15
    weak[by_slug["astar"]].mastery = .2
    overdue = {c: s.model_copy(deep=True) for c, s in consolidated.items()}
    for slug in ["bfs", "cnf"]:
        state = overdue[by_slug[slug]]
        state.last_seen_at = now - timedelta(days=14)
        state.next_review_at = now - timedelta(days=7)
        state.stability_days = 20
    cases = [
        ("Sem diagnóstico", "Nenhuma evidência; 20 minutos disponíveis.", 20, {}, []),
        ("Bases frágeis e prova próxima", "Heurística 15%, A* 20%, demais 85%; prova em dois dias; 40 minutos.",
         40, weak, [AttemptSummary(concept_id=by_slug["heuristica"], correct=False, occurred_at=now)]),
        ("Domínio alto com revisões vencidas", "Mastery 85%; BFS e CNF sem exposição há 14 dias, revisão vencida há sete; 60 minutos.",
         60, overdue, []),
    ]
    output = []
    for name, profile, minutes, states, attempts in cases:
        plan = planner.plan(1, minutes, states, assessments, attempts, now, exercises)
        blocks: list[dict] = []
        for activity in plan.activities:
            if not blocks or blocks[-1]["block"] != activity.block:
                blocks.append({"block": activity.block, "concept": activity.concept, "mode": activity.mode,
                               "minutes": 0, "activities": []})
            blocks[-1]["minutes"] += activity.estimated_minutes
            blocks[-1]["activities"].append({"type": activity.activity_type.value,
                                             "minutes": activity.estimated_minutes, "exercise_id": activity.exercise_id})
        output.append({"scenario": name, "profile": profile, "synthetic": True,
                       "current_datetime": now.isoformat(), "timezone": "America/Sao_Paulo",
                       "available_minutes": minutes, "planned_minutes": plan.planned_minutes,
                       "reserve_minutes": plan.reserve_minutes, "blocks": blocks,
                       "top_scores": [s.model_dump(mode="json") for s in plan.ranking[:5]], "notes": plan.notes})
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = examples()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for case in result:
        print(f"{case['scenario']}: {case['planned_minutes']}/{case['available_minutes']} min; reserva {case['reserve_minutes']} min")
        for block in case["blocks"]:
            print(f"  {block['minutes']} min — {block['concept']} ({block['mode']})")
        print("  Ranking: " + "; ".join(f"{s['concept']}: {s['score']:.3f}" for s in case["top_scores"][:3]))


if __name__ == "__main__":
    main()
