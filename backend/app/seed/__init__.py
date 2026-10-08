from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assessment, AssessmentConcept, Concept, ConceptDependency, Exercise, Student, Subject
from app.seed.content import ASSESSMENT_SCOPE, CONCEPTS, EXERCISES
from app.services.curriculum import concepts_data, dependencies_data
from app.services.knowledge_graph import KnowledgeGraph


def seed_database(db: Session) -> None:
    if db.get(Student, 1) is None:
        db.add(Student(id=1, name="Gabriel"))
    subject = db.scalar(select(Subject).where(Subject.name == "IA Simbólica"))
    if subject is None:
        subject = Subject(name="IA Simbólica")
        db.add(subject)
        db.flush()
    concepts = {c.slug: c for c in db.scalars(select(Concept).where(Concept.subject_id == subject.id))}
    for slug, name, description, _deps, difficulty, importance in CONCEPTS:
        if slug not in concepts:
            concept = Concept(subject_id=subject.id, slug=slug, name=name, description=description,
                              difficulty=difficulty, importance=importance, estimated_minutes=20)
            db.add(concept)
            db.flush()
            concepts[slug] = concept
    existing = {(d.prerequisite_concept_id, d.concept_id) for d in db.scalars(select(ConceptDependency))}
    for slug, _name, _description, deps, _difficulty, _importance in CONCEPTS:
        for prereq in deps:
            pair = (concepts[prereq].id, concepts[slug].id)
            if pair not in existing:
                db.add(ConceptDependency(prerequisite_concept_id=pair[0], concept_id=pair[1],
                                         dependency_strength=1.0, is_essential=False))
                existing.add(pair)
    db.flush()
    KnowledgeGraph(concepts_data(db), dependencies_data(db))
    existing_exercises = set(db.scalars(select(Exercise.slug)))
    for slug, questions in EXERCISES.items():
        for question in questions:
            if question["slug"] in existing_exercises:
                continue
            data = dict(question)
            data["error_map"] = {
                key: {"error_type": value["error_type"],
                      "concepts_involved": [concepts[s].id for s in value.get("concept_slugs", [])]}
                for key, value in question["error_map"].items()
            }
            db.add(Exercise(concept_id=concepts[slug].id, origin_type="PROVISIONAL_SEED", **data))
    assessment = db.scalar(select(Assessment).where(
        Assessment.subject_id == subject.id, Assessment.name == "Avaliação de IA Simbólica",
        Assessment.start_date == date(2026, 10, 13)))
    if assessment is None:
        assessment = Assessment(name="Avaliação de IA Simbólica", subject_id=subject.id,
                                start_date=date(2026, 10, 13), end_date=date(2026, 10, 17), importance=1)
        db.add(assessment)
        db.flush()
        db.add_all([AssessmentConcept(assessment_id=assessment.id, concept_id=concepts[s].id, weight=w)
                    for s, w in ASSESSMENT_SCOPE.items()])
    db.flush()
