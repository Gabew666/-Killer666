from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.config import ReviewConfig
from app.models import AttemptKind, Exercise
from app.schemas.domain import AssessmentData, ConceptData, DependencyData, Evidence, StateData
from app.services.evaluation import DeterministicEvaluator
from app.services.knowledge_graph import KnowledgeGraph
from app.services.mastery import MasteryEngine
from app.services.planner import AdaptivePlanner
from app.services.planner.exam import ExamPriority
from app.services.repetition import ReviewDecision, ReviewScheduler


def concept(id, name, subject=1):
    return ConceptData(id=id, name=name, subject_id=subject, importance=1)


def graph():
    return KnowledgeGraph([concept(1, "BFS"), concept(2, "Função heurística"), concept(3, "A*")],
                          [DependencyData(concept_id=3, prerequisite_concept_id=2)])


def states(now, bfs=.9, heuristic=.25, astar=.3):
    return {i: StateData(concept_id=i, mastery=m, evidence_count=12, evidence_confidence=.8,
                         last_seen_at=now, stability_days=14)
            for i, m in [(1, bfs), (2, heuristic), (3, astar)]}


def exam(now, weights):
    return AssessmentData(id=1, name="IA Simbólica", subject_id=1,
                          start_date=(now + timedelta(days=2)).date(),
                          end_date=(now + timedelta(days=6)).date(), concept_weights=weights)


def evidence(now, **kwargs):
    values = dict(correct=True, score=1, difficulty=.8, hints_used=0, attempt_number=1,
                  attempt_kind=AttemptKind.FIRST_ATTEMPT, independent=True, occurred_at=now)
    return Evidence(**(values | kwargs))


def test_a_heuristic_has_higher_priority_than_mastered_bfs(now):
    planner = AdaptivePlanner(graph(), timezone="UTC")
    ranked = {r.concept_id: r for r in planner.plan(1, 40, states(now), [], [], now).ranking}
    assert ranked[2].score > ranked[1].score


def test_b_exam_boost_outweighs_larger_unrelated_gap(now):
    g = KnowledgeGraph([concept(1, "IA Simbólica"), concept(2, "Matemática", 2)], [])
    current = {1: StateData(concept_id=1, mastery=.5), 2: StateData(concept_id=2, mastery=.2)}
    ranks = AdaptivePlanner(g, timezone="UTC").rank(current, [exam(now, {1: 1})], [], now)
    assert ranks[0].concept_id == 1
    assert ranks[1].components["exam_urgency"] == 0


def test_c_weak_prerequisite_precedes_dependent(now):
    plan = AdaptivePlanner(graph(), timezone="UTC").plan(1, 40, states(now, heuristic=.1, astar=.2), [], [], now)
    concepts = [a.concept_id for a in plan.activities]
    assert concepts.index(2) < concepts.index(3)


def test_d_mastered_overdue_concept_returns_for_review(now):
    current = states(now)
    current[1].next_review_at = now - timedelta(days=10)
    current[1].mastery = .85
    plan = AdaptivePlanner(graph(), timezone="UTC").plan(1, 20, current, [], [], now)
    assert plan.activities[0].concept_id == 1
    assert plan.activities[0].mode == "review"


@pytest.mark.parametrize("minutes", [10, 20, 30, 35, 40, 60, 90, 120, 240])
def test_e_plan_respects_time_and_margin(now, minutes):
    plan = AdaptivePlanner(graph(), timezone="UTC").plan(1, minutes, states(now), [], [], now)
    assert sum(a.estimated_minutes for a in plan.activities) == plan.planned_minutes
    assert plan.planned_minutes <= int(minutes * .92)
    assert plan.reserve_minutes + plan.planned_minutes == minutes
    assert plan.planned_minutes > 0


def test_f_high_mastery_with_one_evidence_stays_uncertain(now):
    result = MasteryEngine().update(StateData(concept_id=1, mastery=.85), evidence(now))
    assert result.mastery == .85
    assert result.evidence_count == 1
    assert result.evidence_confidence < .2
    assert result.status != "MASTERED"


def test_g_soft_gating_allows_heuristic_and_astar_in_exam_session(now):
    planner = AdaptivePlanner(graph(), timezone="UTC")
    plan = planner.plan(1, 40, states(now, heuristic=.15, astar=.2), [exam(now, {3: 1})], [], now)
    ids = [a.concept_id for a in plan.activities]
    assert ids.index(2) < ids.index(3)
    ranks = {r.concept_id: r for r in plan.ranking}
    assert ranks[2].score > ranks[3].score
    assert ranks[3].components["prerequisite_gap"] < 0
    assert not ranks[3].hard_blocked_by


def test_j_only_scoped_concepts_get_direct_exam_boost(now):
    planner = AdaptivePlanner(graph(), timezone="UTC")
    ranks = {r.concept_id: r for r in planner.rank(states(now), [exam(now, {3: 1})], [], now)}
    assert ranks[1].components["exam_urgency"] == 0  # BFS é da mesma disciplina, mas fora do escopo.
    assert ranks[2].signals["exam_direct"] == 0
    assert 0 < ranks[2].signals["exam_inherited"] < ranks[3].signals["exam_direct"]
    assert ranks[2].exam_sources[0]["inherited"] is True


def test_score_components_sum_exactly_and_explain_sources(now):
    for ranked in AdaptivePlanner(graph(), timezone="UTC").rank(states(now), [exam(now, {3: 1})], [], now):
        assert ranked.score == pytest.approx(sum(ranked.components.values()))
        assert ranked.reason
        assert set(ranked.components) == {"exam_urgency", "knowledge_gap", "review_urgency", "importance",
                                           "prerequisite_value", "recent_errors", "mastery_penalty", "prerequisite_gap"}


def test_hard_gate_only_when_explicit_and_fallback_has_no_deadlock(now):
    g = graph()
    g.graph.edges[2, 3]["essential"] = True
    plan = AdaptivePlanner(g, timezone="UTC").plan(1, 40, states(now, heuristic=.1), [exam(now, {3: 1})], [], now)
    assert 3 not in [a.concept_id for a in plan.activities]
    assert 2 in [a.concept_id for a in plan.activities]
    assert next(r for r in plan.ranking if r.concept_id == 3).hard_blocked_by == [2]


def test_graph_rejects_cycles_without_corrupting_existing_graph():
    g = graph()
    with pytest.raises(ValueError, match="ciclo"):
        g.add_dependency(DependencyData(concept_id=2, prerequisite_concept_id=3))
    assert g.ancestors(3) == {2}
    with pytest.raises(ValueError, match="duplicada"):
        g.add_dependency(DependencyData(concept_id=3, prerequisite_concept_id=2))
    with pytest.raises(ValueError, match="inexistente"):
        g.add_dependency(DependencyData(concept_id=3, prerequisite_concept_id=999))
    with pytest.raises(ValueError, match="Auto"):
        g.add_dependency(DependencyData(concept_id=1, prerequisite_concept_id=1))


def test_exam_window_and_timezone_are_configurable(now):
    assessment = exam(now, {3: 1})
    at = datetime(2026, 10, 18, 1, tzinfo=timezone.utc)
    assert ExamPriority("UTC").urgency(assessment, at) == 0
    assert ExamPriority("America/Sao_Paulo").urgency(assessment, at) == 1
    assert ExamPriority("Asia/Tokyo").urgency(assessment, at) == 0
    assert ExamPriority("UTC").urgency(assessment, now) < ExamPriority("UTC").urgency(assessment, now + timedelta(days=1))


def test_review_intervals_only_advance_on_due_delayed_independent_recall(now):
    scheduler = ReviewScheduler()
    review = scheduler.schedule(None, now, correct=True, independent=True, delayed=False)
    assert review.due_at == now + timedelta(days=1)
    assert scheduler.schedule(review, now, correct=True, independent=True, delayed=False) == review
    for days in [3, 7, 14, 30, 30]:
        previous_due = review.due_at
        review = scheduler.schedule(review, previous_due, correct=True, independent=True, delayed=True)
        assert review.due_at == previous_due + timedelta(days=days)
    reset = scheduler.schedule(review, review.due_at, correct=False, independent=True, delayed=True)
    assert reset.stage == 0
    assert reset.due_at == review.due_at + timedelta(days=1)


def test_retry_or_hint_does_not_advance_due_review(now):
    review = ReviewDecision(2, now - timedelta(days=1))
    assert ReviewScheduler().schedule(review, now, correct=True, independent=False, delayed=False) == review


def test_custom_review_intervals(now):
    result = ReviewScheduler(ReviewConfig((2, 5))).schedule(None, now, correct=True, independent=True, delayed=False)
    assert result.due_at == now + timedelta(days=2)


def test_immediate_and_delayed_correct_evidence_have_different_weight(now):
    engine = MasteryEngine()
    state = StateData(concept_id=1, mastery=.4, last_seen_at=now, evidence_count=1, independent_correct=1)
    immediate = engine.update(state, evidence(now, attempt_number=1))
    delayed = engine.update(state, evidence(now + timedelta(days=3), attempt_number=2, attempt_kind=AttemptKind.DELAYED_RECALL))
    assert delayed.mastery > immediate.mastery
    assert delayed.stability_days > immediate.stability_days
    assert delayed.evidence_confidence > immediate.evidence_confidence


def test_retention_decays_without_changing_mastery(now):
    engine = MasteryEngine()
    state = StateData(concept_id=1, mastery=.85, last_seen_at=now, stability_days=7)
    later = engine.at_time(state, now + timedelta(days=7))
    assert later.retention == pytest.approx(.367879, abs=1e-6)
    assert later.mastery == state.mastery
    assert state.retention == 1  # Pureza: leitura não altera argumento.


def test_hints_and_retries_are_practice_without_mastery_inflation(now):
    state = StateData(concept_id=1, mastery=.4)
    engine = MasteryEngine()
    result = engine.update(state, evidence(now, hints_used=2, independent=False))
    assert result.mastery == .4
    assert result.evidence_count == 0
    assert result.times_correct == 1


def test_unknown_mastery_is_always_not_diagnosed_even_when_review_is_due(now):
    engine = MasteryEngine()
    unknown = StateData(concept_id=1, last_seen_at=now - timedelta(days=5), times_seen=3,
                        next_review_at=now - timedelta(days=2))
    assert engine.at_time(unknown, now).status == "NOT_DIAGNOSED"
    assisted = engine.update(unknown, evidence(now, hints_used=1, independent=False))
    assert assisted.status == "NOT_DIAGNOSED"
    assert assisted.mastery is None and assisted.evidence_count == 0


@pytest.mark.parametrize("kind,spec,answer,correct", [
    ("MULTIPLE_CHOICE", {"correct_index": 1}, 1, True),
    ("MULTIPLE_CHOICE", {"correct_index": 1}, 0, False),
    ("TRUE_FALSE", {"value": False}, False, True),
    ("SHORT_EXACT", {"accepted": ["fila FIFO"]}, "  FILA   fifo ", True),
    ("SHORT_EXACT", {"accepted": ["fila"]}, "uma coisa parecida", False),
    ("NUMERIC", {"value": 3.5, "tolerance": .01}, "3,505", True),
    ("NUMERIC", {"value": 3.5, "tolerance": .01}, 3.6, False),
    ("STRUCTURED", {"fields": {"x": {"type": "NUMERIC", "value": 4}}}, {"x": 4}, True),
])
def test_deterministic_formats(kind, spec, answer, correct):
    exercise = Exercise(concept_id=1, exercise_type=kind, answer_spec=spec, options=["A", "B"],
                        explanation="Solução", error_map={})
    assert DeterministicEvaluator().evaluate(exercise, answer).correct is correct


@pytest.mark.parametrize("answer", [True, "NaN", "inf", "2+2", {"value": 2}])
def test_numeric_rejects_unsafe_or_ambiguous_inputs(answer):
    exercise = Exercise(concept_id=1, exercise_type="NUMERIC", answer_spec={"value": 4}, explanation="4", error_map={})
    with pytest.raises(ValueError):
        DeterministicEvaluator().evaluate(exercise, answer)


def test_structured_partial_score_and_shape_validation():
    exercise = Exercise(concept_id=1, exercise_type="STRUCTURED", options=None,
        answer_spec={"fields": {"a": {"type": "NUMERIC", "value": 1}, "b": {"type": "TRUE_FALSE", "value": False}}},
        explanation="Solução", error_map={})
    result = DeterministicEvaluator().evaluate(exercise, {"a": 1, "b": True})
    assert not result.correct and result.score == .5
    with pytest.raises(ValueError):
        DeterministicEvaluator().evaluate(exercise, {"a": 1})
