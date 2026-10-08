from datetime import datetime
import math

from app.core.config import MasteryConfig
from app.core.time import as_utc, elapsed_days
from app.models import AttemptKind
from app.schemas.domain import Evidence, StateData


class MasteryEngine:
    def __init__(self, config: MasteryConfig = MasteryConfig()):
        self.config = config

    def retention_at(self, state: StateData, now: datetime) -> float:
        return math.exp(-elapsed_days(state.last_seen_at, now) / state.stability_days)

    def confidence(self, count: int, delayed_count: int) -> float:
        return (1 - math.exp(-count / self.config.confidence_scale)) * (0.8 + 0.2 * min(delayed_count / 3, 1))

    def at_time(self, state: StateData, now: datetime) -> StateData:
        result = state.model_copy(deep=True)
        result.retention = self.retention_at(result, now)
        result.retention_calculated_at = as_utc(now)
        result.status = self.status(result, now)
        return result

    @staticmethod
    def status(state: StateData, now: datetime) -> str:
        if state.mastery is None:
            return "NOT_DIAGNOSED"
        if state.next_review_at and as_utc(state.next_review_at) <= as_utc(now):
            return "REVIEW_DUE"
        if state.mastery < 0.4:
            return "WEAK"
        if state.mastery >= 0.8 and state.evidence_confidence >= 0.7 and state.evidence_count >= 5:
            return "MASTERED"
        return "DEVELOPING" if state.mastery >= 0.6 else "LEARNING"

    def update(self, state: StateData, evidence: Evidence) -> StateData:
        now = as_utc(evidence.occurred_at)
        if state.last_seen_at and now < as_utc(state.last_seen_at):
            raise ValueError("Evidência anterior à última exposição")
        result = state.model_copy(deep=True)
        elapsed = elapsed_days(state.last_seen_at, now)
        delayed = evidence.attempt_kind == AttemptKind.DELAYED_RECALL
        if delayed and elapsed < self.config.independence_hours / 24:
            raise ValueError("Recuperação tardia sem intervalo mínimo")
        independent = evidence.independent and evidence.hints_used == 0 and evidence.attempt_kind != AttemptKind.RETRY
        if independent:
            old = state.mastery if state.mastery is not None else self.config.prior
            historical = state.independent_correct / state.evidence_count if state.evidence_count else 0.5
            alpha = self.config.alpha * (0.8 + 0.2 * historical) * (1.25 if delayed else 1)
            spacing = self.config.immediate_weight + (1 - self.config.immediate_weight) * min(elapsed / 3, 1)
            difficulty = 0.7 + 0.55 * evidence.difficulty
            if evidence.correct:
                target = min(1.0, difficulty * spacing)
                result.mastery = old + alpha * max(0.0, target - old)
                if delayed:
                    result.stability_days = min(90.0, max(state.stability_days * 1.8, elapsed * 1.5))
            else:
                declared = evidence.self_confidence if evidence.self_confidence is not None else 0.5
                result.mastery = old * (1 - alpha * (1 + 0.25 * declared))
                result.stability_days = max(0.5, state.stability_days * 0.6)
            result.mastery = min(1.0, max(0.0, result.mastery))
            result.evidence_count += 1
            result.delayed_evidence_count += int(delayed)
            result.independent_correct += int(evidence.correct)
            result.last_independent_at = now
            result.evidence_confidence = self.confidence(result.evidence_count, result.delayed_evidence_count)
            total = state.difficulty_attempt_weight + difficulty
            result.difficulty_success_rate = (
                state.difficulty_success_rate * state.difficulty_attempt_weight + difficulty * evidence.score
            ) / total
            result.difficulty_attempt_weight = total
        result.times_attempted += 1
        result.times_correct += int(evidence.correct)
        result.times_seen += 1
        result.last_seen_at = now
        result.last_attempt_at = now
        if evidence.correct:
            result.last_correct_at = now
        if evidence.self_confidence is not None:
            result.self_confidence = evidence.self_confidence
        return self.at_time(result, now)
