import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import (
    Assessment, Concept, CurriculumItemRecord, CurriculumPackageRecord,
    CurriculumUnit, Exercise, ReviewSchedule, Student, StudentConceptState, Subject,
)
from app.services.curriculum import CurriculumImporter, CurriculumValidationError, CurriculumValidator


@pytest.fixture
def package():
    path = Path(__file__).resolve().parents[2] / "examples" / "curriculum_package.example.json"
    return json.loads(path.read_text(encoding="utf-8"))


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_valid_package_and_import_without_replacing_seed(db, package):
    original = (count(db, Subject), count(db, Concept), count(db, Exercise))
    parsed = CurriculumValidator().validate(package)
    assert parsed.content_status == "DEMONSTRATION"
    report = CurriculumImporter().import_package(db, parsed)
    assert report["changes"]["concept"]["created"] == 2
    assert (count(db, Subject), count(db, Concept), count(db, Exercise)) == tuple(x + y for x, y in zip(original, (1, 2, 1)))
    sub = db.scalar(select(Concept).where(Concept.slug == "subtopico-demo"))
    assert sub.parent_concept_id == db.scalar(select(Concept.id).where(Concept.slug == "topico-demo"))
    assert db.get(CurriculumUnit, sub.unit_id).key == "unidade-introdutoria"
    assert sub.learning_objectives
    assert count(db, Assessment) >= 2


@pytest.mark.parametrize("mutation,match", [
    (lambda p: p["concepts"].append(copy.deepcopy(p["concepts"][0])), "conceito duplicado"),
    (lambda p: p["dependencies"][0].update(prerequisite_key="ausente"), "Dependência referencia"),
    (lambda p: p["dependencies"].append({"concept_key": "topico-demo", "prerequisite_key": "subtopico-demo"}), "Ciclo"),
    (lambda p: p["exercises"][0].update(concept_key="ausente"), "Exercício"),
    (lambda p: p["assessments"][0]["coverage"][0].update(concept_key="ausente"), "Avaliação"),
    (lambda p: p["exercises"][0].update(answer_spec={"value": "sim"}), "TRUE_FALSE"),
])
def test_rejects_invalid_package_without_any_write(db, package, mutation, match):
    before = [count(db, model) for model in (Subject, Concept, Exercise, CurriculumPackageRecord, CurriculumItemRecord)]
    mutation(package)
    with pytest.raises(CurriculumValidationError, match=match):
        CurriculumImporter().import_package(db, package)
    assert [count(db, model) for model in (Subject, Concept, Exercise, CurriculumPackageRecord, CurriculumItemRecord)] == before


def test_repeated_import_is_idempotent_and_same_version_is_immutable(db, package):
    importer = CurriculumImporter()
    importer.import_package(db, package)
    before = [count(db, model) for model in (Concept, Exercise, CurriculumPackageRecord, CurriculumItemRecord)]
    assert importer.import_package(db, package)["status"] == "UNCHANGED"
    assert [count(db, model) for model in (Concept, Exercise, CurriculumPackageRecord, CurriculumItemRecord)] == before
    package["concepts"][0]["name"] = "outro"
    with pytest.raises(CurriculumValidationError, match="conteúdo diferente"):
        importer.import_package(db, package)


def test_new_version_preserves_student_mastery_evidence_and_reviews(db, package):
    importer = CurriculumImporter()
    importer.import_package(db, package)
    concept = db.scalar(select(Concept).where(Concept.slug == "topico-demo"))
    student = db.scalar(select(Student).order_by(Student.id))
    state = StudentConceptState(student_id=student.id, concept_id=concept.id, mastery=0.85,
                                retention=0.71, evidence_confidence=0.28, evidence_count=2, status="LEARNING")
    review = ReviewSchedule(student_id=student.id, concept_id=concept.id, stage=2,
                            due_at=datetime(2027, 1, 15, tzinfo=timezone.utc))
    db.add_all([state, review])
    db.flush()
    package["version"] = "0.2.0"
    package["concepts"][0]["description"] = "Descrição revisada."
    package["explanations"][0]["text"] = "DEMONSTRAÇÃO: explicação revisada."
    report = importer.import_package(db, package)
    assert report["changes"]["concept"]["updated"] == 1
    assert report["changes"]["explanation"]["updated"] == 1
    db.refresh(state)
    db.refresh(review)
    assert (state.mastery, state.retention, state.evidence_confidence, state.evidence_count) == (0.85, 0.71, 0.28, 2)
    assert review.stage == 2
    assert concept.description == "Descrição revisada."
    assert count(db, CurriculumPackageRecord) == 2


def test_provenance_and_snapshot_are_preserved(db, package):
    CurriculumImporter().import_package(db, package)
    record = db.scalar(select(CurriculumItemRecord).where(CurriculumItemRecord.item_type == "exercise"))
    assert record.provenance == package["exercises"][0]["provenance"]
    assert record.provenance["source_page"] == 3
    snapshot = db.scalar(select(CurriculumPackageRecord))
    assert snapshot.payload["exercises"][0]["provenance"]["source_reference"] == "Questão fictícia 1"


def test_late_database_conflict_rolls_back_entire_package(db, package):
    seed_subject = db.scalar(select(Subject).where(Subject.name == "IA Simbólica"))
    occupied = db.scalar(select(Concept).where(Concept.subject_id == seed_subject.id))
    package["subject"]["name"] = seed_subject.name
    package["concepts"][1]["key"] = occupied.slug
    package["dependencies"][0]["concept_key"] = occupied.slug
    package["assessments"][0]["coverage"][0]["concept_key"] = occupied.slug
    before = [count(db, model) for model in (Subject, Concept, CurriculumUnit, CurriculumPackageRecord, CurriculumItemRecord)]
    with pytest.raises(CurriculumValidationError, match="já existe fora do pacote"):
        CurriculumImporter().import_package(db, package)
    db.expire_all()
    assert [count(db, model) for model in (Subject, Concept, CurriculumUnit, CurriculumPackageRecord, CurriculumItemRecord)] == before


def test_package_cannot_rename_subject_shared_with_seed(db, package):
    package["subject"]["name"] = "IA Simbólica"
    importer = CurriculumImporter()
    importer.import_package(db, package)
    package["version"] = "0.2.0"
    package["subject"]["name"] = "Outro nome"
    with pytest.raises(CurriculumValidationError, match="compartilhada"):
        importer.import_package(db, package)
    assert db.scalar(select(Subject).where(Subject.name == "IA Simbólica")) is not None
    assert count(db, CurriculumPackageRecord) == 1
