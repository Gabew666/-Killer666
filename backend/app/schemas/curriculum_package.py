"""Declarative, versioned curriculum input; no student estimates live here."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import ExerciseType


Key = str
Probability = float


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Provenance(Item):
    source_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    source_page: int | None = Field(default=None, ge=1)


class SubjectItem(Item):
    key: Key = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    provenance: Provenance | None = None


class UnitItem(Item):
    key: Key = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    position: int = Field(ge=0)
    provenance: Provenance | None = None


class ConceptItem(Item):
    key: Key = Field(min_length=1, max_length=100)
    unit_key: Key
    parent_key: Key | None = None
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    importance: Probability = Field(ge=0, le=1, allow_inf_nan=False)
    difficulty: Probability = Field(ge=0, le=1, allow_inf_nan=False)
    estimated_minutes: int = Field(gt=0)
    learning_objectives: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


class DependencyItem(Item):
    concept_key: Key
    prerequisite_key: Key
    dependency_strength: Probability = Field(default=1, gt=0, le=1, allow_inf_nan=False)
    is_essential: bool = False
    provenance: Provenance | None = None


class CoverageItem(Item):
    concept_key: Key
    weight: Probability = Field(gt=0, le=1, allow_inf_nan=False)
    provenance: Provenance | None = None


class AssessmentItem(Item):
    key: Key = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date
    importance: Probability = Field(default=1, ge=0, le=1, allow_inf_nan=False)
    coverage: list[CoverageItem] = Field(min_length=1)
    provenance: Provenance | None = None


class ExerciseItem(Item):
    key: Key = Field(min_length=1, max_length=100)
    concept_key: Key
    exercise_type: ExerciseType
    prompt: str = Field(min_length=1)
    options: list[str] | None = None
    answer_spec: dict[str, Any]
    explanation: str = Field(min_length=1)
    difficulty: Probability = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    error_map: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance | None = None


class ExplanationItem(Item):
    key: Key = Field(min_length=1, max_length=100)
    concept_key: Key
    text: str = Field(min_length=1)
    provenance: Provenance | None = None


class CurriculumPackage(Item):
    package_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    content_status: Literal["DEMONSTRATION", "DRAFT", "VALIDATED"]
    subject: SubjectItem
    units: list[UnitItem] = Field(min_length=1)
    concepts: list[ConceptItem] = Field(min_length=1)
    dependencies: list[DependencyItem] = Field(default_factory=list)
    assessments: list[AssessmentItem] = Field(default_factory=list)
    exercises: list[ExerciseItem] = Field(default_factory=list)
    explanations: list[ExplanationItem] = Field(default_factory=list)
