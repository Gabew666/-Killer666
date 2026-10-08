from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import ActivityType, AttemptKind


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConceptData(Schema):
    id: int
    subject_id: int
    name: str
    description: str = ""
    difficulty: float = Field(default=0.5, ge=0, le=1)
    importance: float = Field(default=0.7, ge=0, le=1)
    estimated_minutes: int = Field(default=20, gt=0)


class DependencyData(Schema):
    concept_id: int
    prerequisite_concept_id: int
    dependency_strength: float = Field(default=1, gt=0, le=1)
    is_essential: bool = False


class StateData(Schema):
    concept_id: int
    mastery: float | None = Field(default=None, ge=0, le=1)
    retention: float = Field(default=1, ge=0, le=1)
    retention_calculated_at: datetime | None = None
    self_confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_confidence: float = Field(default=0, ge=0, le=1)
    evidence_count: int = Field(default=0, ge=0)
    delayed_evidence_count: int = Field(default=0, ge=0)
    independent_correct: int = Field(default=0, ge=0)
    stability_days: float = Field(default=1, gt=0)
    times_seen: int = 0
    times_attempted: int = 0
    times_correct: int = 0
    last_seen_at: datetime | None = None
    last_attempt_at: datetime | None = None
    last_correct_at: datetime | None = None
    last_independent_at: datetime | None = None
    difficulty_success_rate: float = 0
    difficulty_attempt_weight: float = 0
    next_review_at: datetime | None = None
    status: str = "NOT_DIAGNOSED"


class AssessmentData(Schema):
    id: int
    name: str
    subject_id: int
    start_date: date
    end_date: date
    importance: float = Field(default=1, ge=0, le=1)
    concept_weights: dict[int, float]

    @model_validator(mode="after")
    def valid_window_and_weights(self):
        if self.end_date < self.start_date:
            raise ValueError("Fim da avaliação anterior ao início")
        if any(not 0 < w <= 1 for w in self.concept_weights.values()):
            raise ValueError("Pesos de avaliação devem estar em (0,1]")
        return self


class AttemptInput(Schema):
    answer: Any
    hints_used: int = Field(default=0, ge=0, le=100)
    response_time: float = Field(ge=0, le=86400, allow_inf_nan=False)
    self_confidence: float | None = Field(default=None, ge=0, le=1)


class Evidence(Schema):
    correct: bool
    score: float = Field(ge=0, le=1)
    difficulty: float = Field(ge=0, le=1)
    hints_used: int = Field(ge=0)
    attempt_number: int = Field(gt=0)
    attempt_kind: AttemptKind
    independent: bool
    self_confidence: float | None = Field(default=None, ge=0, le=1)
    occurred_at: datetime


class EvaluationResult(Schema):
    correct: bool
    score: float
    error_type: str | None
    concepts_involved: list[int]
    confidence: float
    feedback: str


class AttemptSummary(Schema):
    concept_id: int
    correct: bool
    occurred_at: datetime
    hints_used: int = Field(default=0, ge=0)


class ScoreExplanation(Schema):
    concept_id: int
    concept: str
    score: float
    components: dict[str, float]
    signals: dict[str, float]
    exam_sources: list[dict[str, Any]]
    reason: str
    weak_prerequisites: list[int]
    hard_blocked_by: list[int]
    low_evidence: bool


class PlannedActivity(Schema):
    concept_id: int | None
    concept: str
    activity_type: ActivityType
    estimated_minutes: int = Field(gt=0)
    instructions: str
    block: int
    mode: Literal["diagnostic", "review", "learn", "practice", "bridge", "break"]
    exercise_id: int | None = None
    decision_after: bool = False


class SessionPlan(Schema):
    student_id: int
    available_minutes: int
    planned_minutes: int
    reserve_minutes: int
    generated_at: datetime
    activities: list[PlannedActivity]
    ranking: list[ScoreExplanation]
    notes: list[str]


class PlanRequest(Schema):
    student_id: int = Field(default=1, gt=0)
    available_minutes: int = Field(ge=10, le=240, strict=True)


class SessionAnswerRequest(Schema):
    activity_id: int = Field(gt=0)
    answer: Any = Field(...)
    hints_used: int = Field(default=0, ge=0, le=100)
    response_time: float = Field(ge=0, le=86400, allow_inf_nan=False)
    self_confidence: float | None = Field(default=None, ge=0, le=1)
    actual_minutes: int | None = Field(default=None, ge=0, strict=True)

    def attempt(self) -> AttemptInput:
        return AttemptInput(answer=self.answer, hints_used=self.hints_used,
                            response_time=self.response_time, self_confidence=self.self_confidence)


class SessionAdvanceRequest(Schema):
    activity_id: int = Field(gt=0)
    actual_minutes: int | None = Field(default=None, ge=0, strict=True)


class SessionFinishRequest(Schema):
    abandon: bool = False
