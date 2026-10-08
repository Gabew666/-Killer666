"""Pure validation of an entire curriculum package before persistence."""

from collections import Counter
from typing import Any

import networkx as nx
from pydantic import ValidationError

from app.models import ExerciseType
from app.schemas.curriculum_package import CurriculumPackage
from app.services.evaluation import numeric


class CurriculumValidationError(ValueError):
    pass


def _unique(values: list[str], label: str) -> None:
    duplicates = sorted(key for key, count in Counter(values).items() if count > 1)
    if duplicates:
        raise CurriculumValidationError(f"{label} duplicado: {', '.join(duplicates)}")


def validate_rubric(kind: str, spec: dict[str, Any], options: list[str] | None) -> None:
    if kind == ExerciseType.MULTIPLE_CHOICE:
        if not options or len(options) < 2 or any(not x.strip() for x in options):
            raise CurriculumValidationError("MULTIPLE_CHOICE exige ao menos duas opções")
        if type(spec.get("correct_index")) is not int or not 0 <= spec["correct_index"] < len(options):
            raise CurriculumValidationError("correct_index inválido")
    elif kind == ExerciseType.TRUE_FALSE:
        if type(spec.get("value")) is not bool:
            raise CurriculumValidationError("TRUE_FALSE exige value booleano")
    elif kind == ExerciseType.SHORT_EXACT:
        accepted = spec.get("accepted")
        if not isinstance(accepted, list) or not accepted or any(not isinstance(x, str) or not x.strip() for x in accepted):
            raise CurriculumValidationError("SHORT_EXACT exige accepted não vazio")
    elif kind == ExerciseType.NUMERIC:
        try:
            if numeric(spec["tolerance"] if "tolerance" in spec else 0) < 0:
                raise ValueError("tolerance negativo")
            numeric(spec["value"])
        except (KeyError, ValueError) as exc:
            raise CurriculumValidationError("NUMERIC exige value finito e tolerance não negativa") from exc
    elif kind == ExerciseType.STRUCTURED:
        fields = spec.get("fields")
        if not isinstance(fields, dict) or not fields:
            raise CurriculumValidationError("STRUCTURED exige fields não vazio")
        for name, rule in fields.items():
            if not name or not isinstance(rule, dict) or rule.get("type") == ExerciseType.STRUCTURED:
                raise CurriculumValidationError("Campo STRUCTURED inválido")
            validate_rubric(rule.get("type"), rule, rule.get("options"))
    else:
        raise CurriculumValidationError(f"Tipo de exercício desconhecido: {kind}")


class CurriculumValidator:
    def validate(self, payload: CurriculumPackage | dict[str, Any]) -> CurriculumPackage:
        try:
            package = CurriculumPackage.model_validate(payload)
        except ValidationError as exc:
            raise CurriculumValidationError(str(exc)) from exc

        for label, values in (
            ("unidade", [x.key for x in package.units]),
            ("conceito", [x.key for x in package.concepts]),
            ("avaliação", [x.key for x in package.assessments]),
            ("exercício", [x.key for x in package.exercises]),
            ("explicação", [x.key for x in package.explanations]),
            ("posição de unidade", [str(x.position) for x in package.units]),
        ):
            _unique(values, label)
        concept_keys = {x.key for x in package.concepts}
        unit_keys = {x.key for x in package.units}
        graph = nx.DiGraph()
        graph.add_nodes_from(concept_keys)
        for concept in package.concepts:
            if concept.unit_key not in unit_keys:
                raise CurriculumValidationError(f"Unidade inexistente: {concept.unit_key}")
            if concept.parent_key:
                if concept.parent_key not in concept_keys:
                    raise CurriculumValidationError(f"Subconceito com pai inexistente: {concept.parent_key}")
                graph.add_edge(concept.parent_key, concept.key)
            if any(not objective.strip() for objective in concept.learning_objectives):
                raise CurriculumValidationError(f"Objetivo vazio: {concept.key}")
        _unique([f"{x.concept_key}:{x.prerequisite_key}" for x in package.dependencies], "dependência")
        for dependency in package.dependencies:
            if dependency.concept_key not in concept_keys or dependency.prerequisite_key not in concept_keys:
                raise CurriculumValidationError("Dependência referencia conceito inexistente")
            graph.add_edge(dependency.prerequisite_key, dependency.concept_key)
        if not nx.is_directed_acyclic_graph(graph):
            raise CurriculumValidationError("Ciclo no currículo")
        for assessment in package.assessments:
            if assessment.end_date < assessment.start_date:
                raise CurriculumValidationError(f"Datas inválidas na avaliação {assessment.key}")
            _unique([x.concept_key for x in assessment.coverage], "cobertura da avaliação")
            if any(x.concept_key not in concept_keys for x in assessment.coverage):
                raise CurriculumValidationError(f"Avaliação {assessment.key} referencia conceito inexistente")
        for exercise in package.exercises:
            if exercise.concept_key not in concept_keys:
                raise CurriculumValidationError(f"Exercício {exercise.key} sem conceito válido")
            if len(f"{package.package_id}:{exercise.key}") > 120:
                raise CurriculumValidationError("Identificador de exercício muito longo")
            validate_rubric(exercise.exercise_type, exercise.answer_spec, exercise.options)
            for diagnosis in exercise.error_map.values():
                involved = diagnosis.get("concepts_involved", []) if isinstance(diagnosis, dict) else None
                if not isinstance(involved, list) or any(not isinstance(key, str) or key not in concept_keys for key in involved):
                    raise CurriculumValidationError(f"Diagnóstico do exercício {exercise.key} referencia conceito inexistente")
        for explanation in package.explanations:
            if explanation.concept_key not in concept_keys:
                raise CurriculumValidationError(f"Explicação {explanation.key} sem conceito válido")
        return package
