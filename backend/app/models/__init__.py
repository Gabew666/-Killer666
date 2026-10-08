from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.core.time import as_utc, utc_now


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return as_utc(value).replace(tzinfo=None) if value is not None else None

    def process_result_value(self, value, dialect):
        return as_utc(value) if value is not None else None


class Base(DeclarativeBase):
    pass


class ExerciseType(StrEnum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    SHORT_EXACT = "SHORT_EXACT"
    NUMERIC = "NUMERIC"
    STRUCTURED = "STRUCTURED"


class AttemptKind(StrEnum):
    FIRST_ATTEMPT = "FIRST_ATTEMPT"
    RETRY = "RETRY"
    DELAYED_RECALL = "DELAYED_RECALL"


class ActivityType(StrEnum):
    RECALL = "RECALL"
    EXPLANATION = "EXPLANATION"
    EXAMPLE = "EXAMPLE"
    GUIDED_EXERCISE = "GUIDED_EXERCISE"
    INDEPENDENT_EXERCISE = "INDEPENDENT_EXERCISE"
    QUIZ = "QUIZ"
    CODE_EXERCISE = "CODE_EXERCISE"
    ERROR_REVIEW = "ERROR_REVIEW"
    SUMMARY = "SUMMARY"
    MOCK_EXAM = "MOCK_EXAM"
    BREAK = "BREAK"


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (
        UniqueConstraint("subject_id", "slug"),
        CheckConstraint("difficulty BETWEEN 0 AND 1"),
        CheckConstraint("importance BETWEEN 0 AND 1"),
        CheckConstraint("estimated_minutes > 0"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    slug: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[float] = mapped_column(Float, default=0.5)
    importance: Mapped[float] = mapped_column(Float, default=0.7)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=20)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class ConceptDependency(Base):
    __tablename__ = "concept_dependencies"
    __table_args__ = (
        UniqueConstraint("concept_id", "prerequisite_concept_id"),
        CheckConstraint("concept_id != prerequisite_concept_id"),
        CheckConstraint("dependency_strength > 0 AND dependency_strength <= 1"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"))
    prerequisite_concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"))
    dependency_strength: Mapped[float] = mapped_column(Float, default=1.0)
    # Somente configuração explícita pode tornar uma relação hard gate.
    is_essential: Mapped[bool] = mapped_column(default=False)


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("subject_id", "name", "start_date"),
        CheckConstraint("end_date >= start_date"),
        CheckConstraint("importance BETWEEN 0 AND 1"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    importance: Mapped[float] = mapped_column(Float, default=1.0)


class AssessmentConcept(Base):
    __tablename__ = "assessment_concepts"
    __table_args__ = (CheckConstraint("weight > 0 AND weight <= 1"),)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class StudentConceptState(Base):
    __tablename__ = "student_concept_states"
    __table_args__ = (
        CheckConstraint("mastery IS NULL OR mastery BETWEEN 0 AND 1"),
        CheckConstraint("retention BETWEEN 0 AND 1"),
        CheckConstraint("self_confidence IS NULL OR self_confidence BETWEEN 0 AND 1"),
        CheckConstraint("evidence_confidence BETWEEN 0 AND 1"),
        CheckConstraint("evidence_count >= 0"),
        CheckConstraint("stability_days > 0"),
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), primary_key=True)
    mastery: Mapped[float | None] = mapped_column(Float, nullable=True)
    retention: Mapped[float] = mapped_column(Float, default=1.0)
    retention_calculated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    self_confidence: Mapped[float | None] = mapped_column(Float)
    evidence_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    delayed_evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    stability_days: Mapped[float] = mapped_column(Float, default=1.0)
    times_seen: Mapped[int] = mapped_column(Integer, default=0)
    times_attempted: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    independent_correct: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_correct_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_independent_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    difficulty_success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty_attempt_weight: Mapped[float] = mapped_column(Float, default=0.0)
    next_review_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(20), default="NOT_DIAGNOSED")


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (CheckConstraint("available_minutes > 0"), CheckConstraint("planned_minutes <= available_minutes"))
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    available_minutes: Mapped[int] = mapped_column(Integer)
    planned_minutes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(20), default="PLANNED")
    plan_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (CheckConstraint("difficulty BETWEEN 0 AND 1"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    exercise_type: Mapped[str] = mapped_column(String(30))
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list[str] | None] = mapped_column(JSON)
    answer_spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[float] = mapped_column(Float, default=0.5)
    # Chave da resposta -> hipótese de erro e conceitos para investigar.
    error_map: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SessionActivity(Base):
    __tablename__ = "session_activities"
    __table_args__ = (UniqueConstraint("session_id", "position"), CheckConstraint("estimated_minutes > 0"))
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("study_sessions.id"))
    concept_id: Mapped[int | None] = mapped_column(ForeignKey("concepts.id"))
    exercise_id: Mapped[int | None] = mapped_column(ForeignKey("exercises.id"))
    position: Mapped[int] = mapped_column(Integer)
    activity_type: Mapped[str] = mapped_column(String(30))
    estimated_minutes: Mapped[int] = mapped_column(Integer)
    instructions: Mapped[str] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"
    __table_args__ = (
        UniqueConstraint("student_id", "exercise_id", "attempt_number"),
        CheckConstraint("score BETWEEN 0 AND 1"),
        CheckConstraint("hints_used >= 0"),
        CheckConstraint("attempt_number > 0"),
        CheckConstraint("response_time >= 0"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("session_activities.id"))
    attempt_kind: Mapped[str] = mapped_column(String(30))
    answer: Mapped[Any] = mapped_column(JSON)
    correct: Mapped[bool] = mapped_column()
    score: Mapped[float] = mapped_column(Float)
    error_type: Mapped[str | None] = mapped_column(String(30))
    concepts_involved: Mapped[list[int]] = mapped_column(JSON)
    evaluator_confidence: Mapped[float] = mapped_column(Float)
    feedback: Mapped[str] = mapped_column(Text)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    attempt_number: Mapped[int] = mapped_column(Integer)
    response_time: Mapped[float] = mapped_column(Float)  # segundos, declarados pelo cliente
    self_confidence: Mapped[float | None] = mapped_column(Float)
    is_independent: Mapped[bool] = mapped_column(default=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class ReviewSchedule(Base):
    __tablename__ = "review_schedules"
    __table_args__ = (UniqueConstraint("student_id", "concept_id"), CheckConstraint("stage >= 0"))
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"))
    stage: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class LearningEvent(Base):
    __tablename__ = "learning_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    concept_id: Mapped[int | None] = mapped_column(ForeignKey("concepts.id"))
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("exercise_attempts.id"), unique=True)
    event_type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
