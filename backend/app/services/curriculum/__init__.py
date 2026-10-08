from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assessment, AssessmentConcept, Concept, ConceptDependency, StudentConceptState
from app.schemas.domain import AssessmentData, ConceptData, DependencyData, StateData
from app.services.knowledge_graph import KnowledgeGraph


def concepts_data(db: Session) -> list[ConceptData]:
    return [ConceptData.model_validate(c, from_attributes=True) for c in db.scalars(select(Concept).order_by(Concept.id))]


def dependencies_data(db: Session) -> list[DependencyData]:
    return [DependencyData.model_validate(d, from_attributes=True) for d in db.scalars(select(ConceptDependency))]


def states_data(db: Session, student_id: int) -> dict[int, StateData]:
    return {s.concept_id: StateData.model_validate(s, from_attributes=True)
            for s in db.scalars(select(StudentConceptState).where(StudentConceptState.student_id == student_id))}


def assessments_data(db: Session) -> list[AssessmentData]:
    scopes: dict[int, dict[int, float]] = {}
    for link in db.scalars(select(AssessmentConcept)):
        scopes.setdefault(link.assessment_id, {})[link.concept_id] = link.weight
    return [AssessmentData(
        id=a.id, name=a.name, subject_id=a.subject_id, start_date=a.start_date,
        end_date=a.end_date, importance=a.importance, concept_weights=scopes.get(a.id, {}),
    ) for a in db.scalars(select(Assessment))]


def add_dependency(db: Session, dependency: DependencyData) -> ConceptDependency:
    graph = KnowledgeGraph(concepts_data(db), dependencies_data(db))
    graph.add_dependency(dependency)
    record = ConceptDependency(**dependency.model_dump())
    db.add(record)
    db.flush()
    return record


def set_assessment_scope(db: Session, assessment_id: int, weights: dict[int, float]) -> None:
    if db.get(Assessment, assessment_id) is None:
        raise ValueError("Avaliação inexistente")
    if not weights or any(not 0 < w <= 1 for w in weights.values()):
        raise ValueError("Escopo precisa de conceitos com pesos em (0,1]")
    for concept_id in weights:
        if db.get(Concept, concept_id) is None:
            raise ValueError("Conceito inexistente no escopo")
    # A substituição é explícita neste serviço; seed usa somente inserções ausentes.
    for old in db.scalars(select(AssessmentConcept).where(AssessmentConcept.assessment_id == assessment_id)):
        db.delete(old)
    db.flush()
    db.add_all([AssessmentConcept(assessment_id=assessment_id, concept_id=c, weight=w) for c, w in weights.items()])
    db.flush()
