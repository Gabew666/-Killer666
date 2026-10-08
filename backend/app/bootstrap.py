"""Choose exactly one initial content source without touching learner progress."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.content import REAL_CURRICULUM_PATH, REAL_PACKAGE_ID
from app.models import (
    Assessment, Concept, ConceptDependency, CurriculumItemRecord, CurriculumPackageRecord,
    CurriculumUnit, Exercise, Student, Subject,
)
from app.seed import seed_database
from app.services.curriculum import CurriculumImporter, CurriculumValidator
from app.services.diagnostics import load_diagnostic_package


class ContentModeConflict(ValueError):
    pass


def _owned_ids(db: Session, kind: str) -> set[int]:
    return {object_id for object_id in db.scalars(select(CurriculumItemRecord.object_id).where(
        CurriculumItemRecord.package_id == REAL_PACKAGE_ID,
        CurriculumItemRecord.item_type == kind)) if object_id is not None}


def _assert_real_isolated(db: Session) -> None:
    foreign_packages = db.scalar(select(CurriculumPackageRecord.id).where(
        CurriculumPackageRecord.package_id != REAL_PACKAGE_ID).limit(1))
    if foreign_packages is not None:
        raise ContentModeConflict("Modo real requer banco separado: há outro CurriculumPackage importado")
    for model, kind in (
        (Subject, "subject"), (CurriculumUnit, "unit"), (Concept, "concept"),
        (ConceptDependency, "dependency"), (Assessment, "assessment"),
    ):
        existing = set(db.scalars(select(model.id)))
        if existing - _owned_ids(db, kind):
            raise ContentModeConflict(
                f"Modo real requer banco separado: há {model.__tablename__} fora do currículo institucional"
            )
    concept_ids = _owned_ids(db, "concept")
    package_exercises = _owned_ids(db, "exercise")
    concept_records = {record.object_id: record for record in db.scalars(select(CurriculumItemRecord).where(
        CurriculumItemRecord.package_id == REAL_PACKAGE_ID,
        CurriculumItemRecord.item_type == "concept"))}
    for exercise in db.scalars(select(Exercise)):
        if exercise.id in package_exercises:
            continue
        provenance = exercise.provenance or {}
        source = concept_records.get(exercise.concept_id)
        institutional = source.provenance if source else None
        if (exercise.concept_id not in concept_ids
                or exercise.origin_type != "ATLAS_AUTHORED_DIAGNOSTIC"
                or provenance.get("authored_by") != "ATLAS"
                or provenance.get("concept_key") != (source.item_key if source else None)
                or provenance.get("curriculum_package_id") != REAL_PACKAGE_ID
                or not institutional
                or provenance.get("source_id") != institutional.get("source_id")):
            raise ContentModeConflict("Modo real encontrou exercício sem proveniência diagnóstica válida")


def bootstrap_content(db: Session, mode: str) -> None:
    """Caller owns the transaction; failures leave curriculum and student state intact."""
    if mode == "provisional":
        real_imported = db.scalar(select(CurriculumPackageRecord.id).where(
            CurriculumPackageRecord.package_id == REAL_PACKAGE_ID).limit(1))
        real_subject = db.scalar(select(Subject.id).where(
            Subject.name == "Inteligência Artificial Simbólica").limit(1))
        if real_imported is not None or real_subject is not None:
            raise ContentModeConflict("Modo provisional não pode usar banco com currículo real")
        seed_database(db)
        return
    if mode != "real":
        raise ValueError("ATLAS_CONTENT_MODE deve ser provisional ou real")
    payload = json.loads(REAL_CURRICULUM_PATH.read_text(encoding="utf-8"))
    package = CurriculumValidator().validate(payload)
    if package.package_id != REAL_PACKAGE_ID:
        raise ContentModeConflict("package_id do currículo real inesperado")
    _assert_real_isolated(db)
    CurriculumImporter().import_package(db, package)
    load_diagnostic_package(db)
    _assert_real_isolated(db)
    if db.get(Student, 1) is None:
        db.add(Student(id=1, name="Aluno 1"))
    db.flush()
