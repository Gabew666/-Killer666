"""Future ATLAS-authored diagnosis, tied only to institutional concept IDs."""

from typing import Any

from pydantic import ValidationError
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


def register_atlas_diagnostic(db: Session, payload: ExerciseItem | dict[str, Any]) -> Exercise:
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
    if len(slug) > 120 or db.scalar(select(Exercise.id).where(Exercise.slug == slug)) is not None:
        raise ValueError("Identificador de questão diagnóstica inválido ou duplicado")
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
    exercise = Exercise(
        concept_id=record.object_id, slug=slug, exercise_type=item.exercise_type,
        prompt=item.prompt, options=item.options, answer_spec=item.answer_spec,
        explanation=item.explanation, difficulty=item.difficulty, error_map=diagnoses,
        origin_type=ATLAS_AUTHORED_DIAGNOSTIC, provenance=provenance,
    )
    db.add(exercise)
    db.flush()
    return exercise


def real_diagnostic_exercises(db: Session) -> dict[int, list[int]]:
    """Require one authored question per target before starting a real diagnostic."""
    records = {key: _concept_record(db, key) for key in DIAGNOSTIC_TARGET_KEYS}
    by_concept: dict[int, list[int]] = {record.object_id: [] for record in records.values()}
    for exercise in db.scalars(select(Exercise).where(
            Exercise.origin_type == ATLAS_AUTHORED_DIAGNOSTIC).order_by(Exercise.difficulty, Exercise.id)):
        if exercise.concept_id in by_concept:
            by_concept[exercise.concept_id].append(exercise.id)
    missing = [key for key, record in records.items() if not by_concept[record.object_id]]
    if missing:
        covered = len(DIAGNOSTIC_TARGET_KEYS) - len(missing)
        raise ValueError(
            f"Currículo real carregado, mas faltam exercícios diagnósticos autorais do ATLAS: "
            f"{covered}/{len(DIAGNOSTIC_TARGET_KEYS)} conceitos prioritários cobertos"
        )
    return by_concept
