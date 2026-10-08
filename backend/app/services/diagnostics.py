"""Versioned ATLAS-authored diagnosis, tied only to institutional concept IDs."""

import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.content import REAL_PACKAGE_ID
from app.models import Concept, CurriculumItemRecord, Exercise
from app.schemas.curriculum_package import ExerciseItem
from app.services.curriculum.package import validate_rubric

ATLAS_AUTHORED_DIAGNOSTIC = "ATLAS_AUTHORED_DIAGNOSTIC"

# Referências às chaves do currículo real; não são enunciados nem questões oficiais.
DIAGNOSTIC_TARGET_KEYS = (
    "fundamentos-ia-simbolica", "formulacao-de-problemas-ia", "espaco-de-estados",
    "logica-proposicional", "logica-de-predicados", "bfs", "dfs", "busca-heuristica",
    "a-star", "representacao-de-conhecimento", "inferencia-logica",
    "agentes-inteligentes", "redes-semanticas", "frames",
)


def _concept_record(db: Session, key: str) -> CurriculumItemRecord:
    record = db.scalar(select(CurriculumItemRecord).where(
        CurriculumItemRecord.package_id == REAL_PACKAGE_ID,
        CurriculumItemRecord.item_type == "concept",
        CurriculumItemRecord.item_key == key))
    if record is None or record.object_id is None or db.get(Concept, record.object_id) is None:
        raise ValueError(f"Conceito fora do currículo institucional real: {key}")
    return record


def register_atlas_diagnostic(db: Session, payload: ExerciseItem | dict[str, Any],
                              *, diagnostic_version: str | None = None) -> Exercise:
    """Record authored content without changing the institutional package or learner state."""
    try:
        item = ExerciseItem.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    if item.concept_key not in DIAGNOSTIC_TARGET_KEYS:
        raise ValueError("Conceito fora do escopo do diagnóstico inicial real")
    if item.provenance is not None:
        raise ValueError("Proveniência diagnóstica é derivada do currículo real, não informada manualmente")
    validate_rubric(item.exercise_type, item.answer_spec, item.options)
    record = _concept_record(db, item.concept_key)
    source = record.provenance
    if not source or not all(source.get(key) for key in (
            "source_id", "source_name", "source_type", "source_reference")):
        raise ValueError("Conceito real sem proveniência institucional suficiente")
    slug = f"atlas-diagnostic:{item.key}"
    if len(slug) > 120:
        raise ValueError("Identificador de questão diagnóstica inválido")
    diagnoses: dict[str, Any] = {}
    for answer, diagnosis in item.error_map.items():
        if not isinstance(diagnosis, dict):
            raise ValueError("Diagnóstico de erro inválido")
        involved = diagnosis.get("concepts_involved", [])
        if not isinstance(involved, list):
            raise ValueError("Conceitos do diagnóstico de erro inválidos")
        diagnoses[answer] = {**diagnosis, "concepts_involved": [
            _concept_record(db, key).object_id for key in involved]}
    provenance = {
        **source,
        "concept_key": item.concept_key,
        "authored_by": "ATLAS",
        "curriculum_package_id": REAL_PACKAGE_ID,
        "curriculum_version": record.latest_version,
    }
    if diagnostic_version is not None:
        provenance["diagnostic_version"] = diagnostic_version
    values = dict(
        concept_id=record.object_id, slug=slug, exercise_type=item.exercise_type,
        prompt=item.prompt, options=item.options, answer_spec=item.answer_spec,
        explanation=item.explanation, difficulty=item.difficulty, error_map=diagnoses,
        origin_type=ATLAS_AUTHORED_DIAGNOSTIC, provenance=provenance,
    )
    existing = db.scalar(select(Exercise).where(Exercise.slug == slug))
    if existing is not None:
        if any(getattr(existing, key) != value for key, value in values.items()):
            raise ValueError(f"Questão diagnóstica imutável alterada: {item.key}; publique nova versão com nova chave")
        return existing
    exercise = Exercise(**values)
    db.add(exercise)
    db.flush()
    return exercise


DIAGNOSTIC_PACKAGE_PATH = Path(__file__).resolve().parents[2] / "content/diagnostics/ia_simbolica_v0.1.json"


class DiagnosticPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_type: Literal["ATLAS_AUTHORED_DIAGNOSTIC"]
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    curriculum_package_id: Literal["uniasselvi-ia-simbolica-2026-2"]
    description: str = Field(min_length=1)
    questions: list[ExerciseItem]


def validate_diagnostic_package(payload: dict[str, Any]) -> DiagnosticPackage:
    """Validate every question before any database mutation."""
    package = DiagnosticPackage.model_validate(payload)
    keys = [item.key for item in package.questions]
    if len(set(keys)) != len(keys):
        raise ValueError("Chave diagnóstica duplicada")
    counts = Counter(item.concept_key for item in package.questions)
    if set(counts) != set(DIAGNOSTIC_TARGET_KEYS) or any(count < 2 for count in counts.values()):
        raise ValueError("Diagnóstico exige ao menos duas questões por conceito prioritário")
    for item in package.questions:
        if item.provenance is not None:
            raise ValueError("Proveniência diagnóstica não pode ser informada manualmente")
        if item.exercise_type == "STRUCTURED":
            raise ValueError("STRUCTURED não é suportado neste pacote diagnóstico")
        validate_rubric(item.exercise_type, item.answer_spec, item.options)
    return package


def load_diagnostic_package(db: Session, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    package = validate_diagnostic_package(payload if payload is not None else json.loads(
        DIAGNOSTIC_PACKAGE_PATH.read_text(encoding="utf-8")))
    report = {"version": package.version, "created": 0, "unchanged": 0}
    # A conflict in the last question rolls back all earlier registrations.
    with db.begin_nested():
        for item in package.questions:
            existed = db.scalar(select(Exercise.id).where(Exercise.slug == f"atlas-diagnostic:{item.key}"))
            register_atlas_diagnostic(db, item, diagnostic_version=package.version)
            report["unchanged" if existed is not None else "created"] += 1
    return report


def real_diagnostic_exercises(db: Session) -> dict[int, list[int]]:
    """Require independent confirmation questions before starting a real diagnostic."""
    records = {key: _concept_record(db, key) for key in DIAGNOSTIC_TARGET_KEYS}
    by_concept: dict[int, list[int]] = {record.object_id: [] for record in records.values()}
    for exercise in db.scalars(select(Exercise).where(
            Exercise.origin_type == ATLAS_AUTHORED_DIAGNOSTIC).order_by(Exercise.difficulty, Exercise.id)):
        if exercise.concept_id in by_concept:
            by_concept[exercise.concept_id].append(exercise.id)
    missing = [key for key, record in records.items() if len(by_concept[record.object_id]) < 2]
    if missing:
        covered = len(DIAGNOSTIC_TARGET_KEYS) - len(missing)
        raise ValueError(
            f"Currículo real carregado, mas faltam exercícios diagnósticos autorais do ATLAS: "
            f"{covered}/{len(DIAGNOSTIC_TARGET_KEYS)} conceitos prioritários cobertos"
        )
    return by_concept
