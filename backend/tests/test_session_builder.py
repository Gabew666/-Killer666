from datetime import timedelta

import pytest

from app.models import ActivityType
from app.schemas.domain import AttemptSummary, ConceptData, StateData
from app.services.planner.session_builder import SessionBuilder


@pytest.fixture
def builder():
    return SessionBuilder()


@pytest.fixture
def concept():
    return ConceptData(id=1, subject_id=1, name="Função heurística", description="h(n) estima o custo restante.")


def observed(now, *, mastery=.7, retention=1, confidence=.8, count=12, due=None):
    return StateData(concept_id=1, mastery=mastery, retention=retention, evidence_confidence=confidence,
                     evidence_count=count, next_review_at=due, last_seen_at=now, stability_days=10)


@pytest.mark.parametrize("state", [
    StateData(concept_id=1),
    StateData(concept_id=1, mastery=.85, evidence_count=1, evidence_confidence=.09),
    StateData(concept_id=1, mastery=.5, evidence_count=5, evidence_confidence=.2),
])
def test_diagnostic_for_unknown_or_low_evidence(builder, concept, now, state):
    assert builder.choose(state, [], now) == "diagnostic"
    block = builder.build(concept, 8, 1, "diagnostic", [101, 102])
    assert [a.activity_type for a in block] == [ActivityType.RECALL, ActivityType.ERROR_REVIEW, ActivityType.SUMMARY]
    assert block[0].exercise_id == 101
    assert not any(a.activity_type == ActivityType.EXPLANATION for a in block)
    assert block[0].decision_after
    assert sum(a.estimated_minutes for a in block) == 8


def test_learning_sequence_uses_explanation_then_practice(builder, concept, now):
    assert builder.choose(observed(now, mastery=.35), [], now) == "learn"
    block = builder.build(concept, 20, 1, "learn", [101, 102])
    assert [a.activity_type for a in block] == [ActivityType.RECALL, ActivityType.EXPLANATION,
        ActivityType.GUIDED_EXERCISE, ActivityType.INDEPENDENT_EXERCISE,
        ActivityType.ERROR_REVIEW, ActivityType.SUMMARY]
    assert block[2].exercise_id == 101 and block[3].exercise_id == 102
    assert not any(a.decision_after for a in block)
    assert sum(a.estimated_minutes for a in block) == 20


def test_assisted_recent_attempt_selects_learning_without_changing_mastery(builder, now):
    state = observed(now, mastery=.7)
    attempt = AttemptSummary(concept_id=1, correct=True, hints_used=1, occurred_at=now - timedelta(days=1))
    assert builder.choose(state, [attempt], now) == "learn"
    assert state.mastery == .7
    assert builder.choose(state, [attempt], now + timedelta(days=8)) == "practice"


def test_review_for_due_or_low_retention(builder, concept, now):
    due = observed(now, mastery=.85, due=now - timedelta(days=2))
    decayed = observed(now, mastery=.85, retention=.3)
    assert builder.choose(due, [], now) == "review"
    assert builder.choose(decayed, [], now) == "review"
    with_two = builder.build(concept, 20, 1, "review", [101, 102])
    assert [a.activity_type for a in with_two] == [ActivityType.RECALL, ActivityType.QUIZ,
                                                  ActivityType.ERROR_REVIEW, ActivityType.SUMMARY]
    assert [a.exercise_id for a in with_two[:2]] == [101, 102]
    with_one = builder.build(concept, 8, 1, "review", [101])
    assert all(a.activity_type != ActivityType.QUIZ for a in with_one)
    assert sum(a.estimated_minutes for a in with_one) == 8


def test_practice_for_observed_retentive_knowledge(builder, concept, now):
    assert builder.choose(observed(now, mastery=.85), [], now) == "practice"
    block = builder.build(concept, 16, 1, "practice", [101])
    assert [a.activity_type for a in block] == [ActivityType.RECALL, ActivityType.INDEPENDENT_EXERCISE,
                                               ActivityType.ERROR_REVIEW, ActivityType.SUMMARY]
    assert block[1].exercise_id == 101
    assert sum(a.estimated_minutes for a in block) == 16


@pytest.mark.parametrize("strategy", ["diagnostic", "learn", "review", "practice"])
@pytest.mark.parametrize("minutes", [8, 11, 16, 20])
def test_every_strategy_fits_exact_block_budget(builder, concept, strategy, minutes):
    block = builder.build(concept, minutes, 1, strategy, [101, 102])
    assert all(a.estimated_minutes > 0 for a in block)
    assert sum(a.estimated_minutes for a in block) == minutes
    assert len({a.block for a in block}) == 1
