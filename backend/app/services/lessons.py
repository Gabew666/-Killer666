"""Conteúdo de estudo estruturado, autoral do ATLAS e ancorado no material institucional."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.content import REAL_PACKAGE_ID
from app.models import CurriculumItemRecord

LESSON_PACKAGE_PATH = Path(__file__).resolve().parents[2] / "content/lessons/ia_simbolica_v0.2.json"


class WorkedExample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1)
    steps: list[str] = Field(min_length=2)
    takeaway: str = Field(min_length=1)


class LessonCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    concept_key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=2)
    worked_example: WorkedExample
    common_mistakes: list[str] = Field(min_length=1)
    quick_check: str = Field(min_length=1)


class LessonPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_type: Literal["ATLAS_STUDY_GUIDE"]
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    curriculum_package_id: Literal["uniasselvi-ia-simbolica-2026-2"]
    source_name: str = Field(min_length=1)
    source_type: Literal["INSTITUTIONAL_MATERIAL"]
    basis_note: str = Field(min_length=1)
    lessons: list[LessonCard] = Field(min_length=1)


@lru_cache(maxsize=1)
def lesson_package() -> LessonPackage:
    payload = json.loads(LESSON_PACKAGE_PATH.read_text(encoding="utf-8"))
    package = LessonPackage.model_validate(payload)
    keys = [lesson.concept_key for lesson in package.lessons]
    if len(keys) != len(set(keys)):
        raise ValueError("Guia de estudo contém conceito duplicado")
    return package


@lru_cache(maxsize=1)
def _by_key() -> dict[str, LessonCard]:
    return {lesson.concept_key: lesson for lesson in lesson_package().lessons}


def lesson_for_concept(db: Session, concept_id: int | None) -> dict[str, Any] | None:
    if concept_id is None:
        return None
    record = db.scalar(select(CurriculumItemRecord).where(
        CurriculumItemRecord.package_id == REAL_PACKAGE_ID,
        CurriculumItemRecord.item_type == "concept",
        CurriculumItemRecord.object_id == concept_id,
    ))
    if record is None:
        return None
    lesson = _by_key().get(record.item_key)
    if lesson is None:
        return None
    package = lesson_package()
    return lesson.model_dump(mode="json") | {
        "source": {
            "name": package.source_name,
            "type": package.source_type,
            "reference": lesson.source_reference,
            "basis_note": package.basis_note,
            "version": package.version,
        }
    }
