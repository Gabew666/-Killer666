"""Transactional, additive import of validated curriculum versions."""

from hashlib import sha256
import json
from typing import Any

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Assessment, AssessmentConcept, Concept, ConceptDependency, CurriculumExplanation,
    CurriculumItemRecord, CurriculumPackageRecord, CurriculumUnit, Exercise, Subject,
)
from app.schemas.curriculum_package import CurriculumPackage
from app.services.curriculum.package import CurriculumValidationError, CurriculumValidator


def _hash(payload: Any) -> str:
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


class CurriculumImporter:
    def __init__(self, validator: CurriculumValidator | None = None):
        self.validator = validator or CurriculumValidator()

    def import_package(self, db: Session, payload: CurriculumPackage | dict[str, Any]) -> dict[str, Any]:
        package = self.validator.validate(payload)  # No SQL writes before whole-package validation.
        snapshot = package.model_dump(mode="json")
        digest = _hash(snapshot)
        old_versions = list(db.scalars(select(CurriculumPackageRecord).where(
            CurriculumPackageRecord.package_id == package.package_id)))
        same = next((x for x in old_versions if x.version == package.version), None)
        if same:
            if same.content_hash != digest:
                raise CurriculumValidationError("Versão já importada com conteúdo diferente")
            return {"package_id": package.package_id, "version": package.version,
                    "status": "UNCHANGED", "changes": {}}
        version_tuple = tuple(int(x) for x in package.version.split("."))
        if any(tuple(int(x) for x in old.version.split(".")) >= version_tuple for old in old_versions):
            raise CurriculumValidationError("Versão deve avançar monotonamente")

        changes: dict[str, dict[str, int]] = {}

        def track(kind: str, outcome: str) -> None:
            changes.setdefault(kind, {"created": 0, "updated": 0, "unchanged": 0})[outcome] += 1

        def owned(kind: str, key: str) -> CurriculumItemRecord | None:
            return db.scalar(select(CurriculumItemRecord).where(
                CurriculumItemRecord.package_id == package.package_id,
                CurriculumItemRecord.item_type == kind,
                CurriculumItemRecord.item_key == key))

        def mark(kind: str, key: str, item: Any, object_id: int | None) -> None:
            data = item.model_dump(mode="json")
            current = owned(kind, key)
            outcome = "created" if current is None else ("unchanged" if current.content_hash == _hash(data) else "updated")
            track(kind, outcome)
            if current is None:
                current = CurriculumItemRecord(package_id=package.package_id, item_type=kind, item_key=key,
                                               object_id=object_id, latest_version=package.version,
                                               content_hash=_hash(data), provenance=data.get("provenance"))
                db.add(current)
            else:
                current.object_id = object_id
                current.latest_version = package.version
                current.content_hash = _hash(data)
                current.provenance = data.get("provenance")
            db.flush()

        def conflict(kind: str, key: str) -> None:
            raise CurriculumValidationError(f"{kind} {key} já existe fora do pacote")

        # A savepoint rolls back even a late uniqueness/FK failure; caller owns outer commit.
        with db.begin_nested():
            subject_record = owned("subject", package.subject.key)
            if subject_record:
                subject = db.get(Subject, subject_record.object_id)
                if subject is None:
                    raise CurriculumValidationError("Disciplina do pacote não existe mais")
                if subject.name != package.subject.name:
                    owned_concepts = set(db.scalars(select(CurriculumItemRecord.object_id).where(
                        CurriculumItemRecord.package_id == package.package_id,
                        CurriculumItemRecord.item_type == "concept")))
                    subject_concepts = set(db.scalars(select(Concept.id).where(Concept.subject_id == subject.id)))
                    if subject_concepts - owned_concepts:
                        raise CurriculumValidationError("Disciplina compartilhada não pode ser renomeada pelo pacote")
                another = db.scalar(select(Subject).where(Subject.name == package.subject.name, Subject.id != subject.id))
                if another:
                    conflict("Disciplina", package.subject.name)
                subject.name = package.subject.name
            else:
                subject = db.scalar(select(Subject).where(Subject.name == package.subject.name))
                if subject is None:
                    subject = Subject(name=package.subject.name)
                    db.add(subject)
                    db.flush()
            mark("subject", package.subject.key, package.subject, subject.id)

            units: dict[str, CurriculumUnit] = {}
            for item in package.units:
                record = owned("unit", item.key)
                unit = db.get(CurriculumUnit, record.object_id) if record else None
                if record and unit is None:
                    raise CurriculumValidationError(f"Unidade removida externamente: {item.key}")
                if unit is None:
                    if db.scalar(select(CurriculumUnit).where(CurriculumUnit.subject_id == subject.id, CurriculumUnit.key == item.key)):
                        conflict("Unidade", item.key)
                    unit = CurriculumUnit(subject_id=subject.id, key=item.key)
                    db.add(unit)
                unit.name, unit.description, unit.position = item.name, item.description, item.position
                db.flush()
                units[item.key] = unit
                mark("unit", item.key, item, unit.id)

            concepts: dict[str, Concept] = {}
            for item in package.concepts:
                record = owned("concept", item.key)
                concept = db.get(Concept, record.object_id) if record else None
                if record and concept is None:
                    raise CurriculumValidationError(f"Conceito removido externamente: {item.key}")
                if concept is None:
                    if db.scalar(select(Concept).where(Concept.subject_id == subject.id, Concept.slug == item.key)):
                        conflict("Conceito", item.key)
                    concept = Concept(subject_id=subject.id, slug=item.key)
                    db.add(concept)
                concept.unit_id = units[item.unit_key].id
                concept.name, concept.description = item.name, item.description
                concept.difficulty, concept.importance = item.difficulty, item.importance
                concept.estimated_minutes = item.estimated_minutes
                concept.learning_objectives = item.learning_objectives
                db.flush()
                concepts[item.key] = concept
                mark("concept", item.key, item, concept.id)
            for item in package.concepts:
                concepts[item.key].parent_concept_id = concepts[item.parent_key].id if item.parent_key else None
            db.flush()

            for item in package.dependencies:
                key = f"{item.concept_key}:{item.prerequisite_key}"
                target, prerequisite = concepts[item.concept_key], concepts[item.prerequisite_key]
                record = owned("dependency", key)
                dependency = db.get(ConceptDependency, record.object_id) if record else None
                if record and dependency is None:
                    raise CurriculumValidationError(f"Dependência removida externamente: {key}")
                if dependency is None:
                    if db.scalar(select(ConceptDependency).where(ConceptDependency.concept_id == target.id,
                                                                  ConceptDependency.prerequisite_concept_id == prerequisite.id)):
                        conflict("Dependência", key)
                    dependency = ConceptDependency(concept_id=target.id, prerequisite_concept_id=prerequisite.id)
                    db.add(dependency)
                dependency.dependency_strength = item.dependency_strength
                dependency.is_essential = item.is_essential
                db.flush()
                mark("dependency", key, item, dependency.id)

            for item in package.assessments:
                record = owned("assessment", item.key)
                assessment = db.get(Assessment, record.object_id) if record else None
                if record and assessment is None:
                    raise CurriculumValidationError(f"Avaliação removida externamente: {item.key}")
                if assessment is None:
                    if db.scalar(select(Assessment).where(Assessment.subject_id == subject.id,
                                                          Assessment.name == item.name,
                                                          Assessment.start_date == item.start_date)):
                        conflict("Avaliação", item.key)
                    assessment = Assessment(subject_id=subject.id)
                    db.add(assessment)
                assessment.name, assessment.start_date = item.name, item.start_date
                assessment.end_date, assessment.importance = item.end_date, item.importance
                db.flush()
                mark("assessment", item.key, item, assessment.id)
                for covered in item.coverage:
                    key = f"{item.key}:{covered.concept_key}"
                    link = db.get(AssessmentConcept, (assessment.id, concepts[covered.concept_key].id))
                    if link is None:
                        link = AssessmentConcept(assessment_id=assessment.id, concept_id=concepts[covered.concept_key].id)
                        db.add(link)
                    link.weight = covered.weight
                    db.flush()
                    mark("coverage", key, covered, None)

            for item in package.exercises:
                record = owned("exercise", item.key)
                exercise = db.get(Exercise, record.object_id) if record else None
                if record and exercise is None:
                    raise CurriculumValidationError(f"Exercício removido externamente: {item.key}")
                if exercise is None:
                    slug = f"{package.package_id}:{item.key}"
                    if db.scalar(select(Exercise).where(Exercise.slug == slug)):
                        conflict("Exercício", slug)
                    exercise = Exercise(slug=slug)
                    db.add(exercise)
                exercise.concept_id = concepts[item.concept_key].id
                exercise.exercise_type, exercise.prompt = item.exercise_type, item.prompt
                exercise.options, exercise.answer_spec = item.options, item.answer_spec
                exercise.explanation, exercise.difficulty = item.explanation, item.difficulty
                exercise.origin_type = "CURRICULUM_PACKAGE"
                exercise.provenance = item.provenance.model_dump(mode="json") if item.provenance else None
                exercise.error_map = {key: {**diagnosis, "concepts_involved": [concepts[c].id for c in diagnosis.get("concepts_involved", [])]}
                                      for key, diagnosis in item.error_map.items()}
                db.flush()
                mark("exercise", item.key, item, exercise.id)

            for item in package.explanations:
                record = owned("explanation", item.key)
                explanation = db.get(CurriculumExplanation, record.object_id) if record else None
                if record and explanation is None:
                    raise CurriculumValidationError(f"Explicação removida externamente: {item.key}")
                if explanation is None:
                    if db.scalar(select(CurriculumExplanation).where(CurriculumExplanation.subject_id == subject.id,
                                                                       CurriculumExplanation.key == item.key)):
                        conflict("Explicação", item.key)
                    explanation = CurriculumExplanation(subject_id=subject.id, key=item.key)
                    db.add(explanation)
                explanation.concept_id, explanation.text = concepts[item.concept_key].id, item.text
                db.flush()
                mark("explanation", item.key, item, explanation.id)

            # Older additive versions and the existing seed may still own edges.
            # Validate the resulting database graph, not only the submitted snapshot.
            graph = nx.DiGraph()
            graph.add_nodes_from(db.scalars(select(Concept.id)))
            graph.add_edges_from((edge.prerequisite_concept_id, edge.concept_id)
                                 for edge in db.scalars(select(ConceptDependency)))
            graph.add_edges_from((concept.parent_concept_id, concept.id)
                                 for concept in db.scalars(select(Concept)) if concept.parent_concept_id is not None)
            if not nx.is_directed_acyclic_graph(graph):
                raise CurriculumValidationError("Ciclo no grafo resultante do banco")

            db.add(CurriculumPackageRecord(package_id=package.package_id, version=package.version,
                                           content_hash=digest, content_status=package.content_status,
                                           payload=snapshot))
            db.flush()
        return {"package_id": package.package_id, "version": package.version,
                "status": "IMPORTED", "changes": changes}
