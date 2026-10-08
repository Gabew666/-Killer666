from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
import unicodedata

from app.models import Exercise, ExerciseType
from app.schemas.domain import EvaluationResult


class SemanticEvaluator(Protocol):
    """Ponto de extensão futuro; nenhuma implementação remota é instanciada."""

    def evaluate(self, prompt: str, answer: str, rubric: dict[str, Any]) -> EvaluationResult: ...


def normalize_exact(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def numeric(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("Resposta numérica esperada")
    try:
        result = Decimal(str(value).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Número inválido") from exc
    if not result.is_finite():
        raise ValueError("Número deve ser finito")
    return result


class DeterministicEvaluator:
    def evaluate(self, exercise: Exercise, answer: Any) -> EvaluationResult:
        score = self._score(exercise.exercise_type, exercise.answer_spec, answer, exercise.options)
        correct = score == 1
        diagnosis = exercise.error_map.get(str(answer), {}) if not correct else {}
        involved = sorted(set([exercise.concept_id] + diagnosis.get("concepts_involved", [])))
        return EvaluationResult(
            correct=correct, score=score,
            error_type=None if correct else diagnosis.get("error_type", "UNKNOWN"),
            concepts_involved=involved,
            # Certeza do gabarito não implica certeza do diagnóstico do erro.
            confidence=1.0 if correct else (0.7 if diagnosis else 0.3),
            feedback=("Correto. " if correct else "Revise a solução. ") + exercise.explanation,
        )

    def _score(self, kind: str, spec: dict, answer: Any, options: list[str] | None = None) -> float:
        if kind == ExerciseType.MULTIPLE_CHOICE:
            if type(answer) is not int or options is None or not 0 <= answer < len(options):
                raise ValueError("Informe o índice de uma alternativa válida")
            return float(answer == spec["correct_index"])
        if kind == ExerciseType.TRUE_FALSE:
            if type(answer) is not bool:
                raise ValueError("Resposta deve ser um booleano")
            return float(answer is spec["value"])
        if kind == ExerciseType.SHORT_EXACT:
            if not isinstance(answer, str):
                raise ValueError("Resposta textual esperada")
            return float(normalize_exact(answer) in {normalize_exact(v) for v in spec["accepted"]})
        if kind == ExerciseType.NUMERIC:
            tolerance = numeric(spec.get("tolerance", 0))
            if tolerance < 0:
                raise ValueError("Tolerância inválida na rubrica")
            return float(abs(numeric(answer) - numeric(spec["value"])) <= tolerance)
        if kind == ExerciseType.STRUCTURED:
            fields = spec["fields"]
            if not isinstance(answer, dict) or set(answer) != set(fields) or not fields:
                raise ValueError("Resposta deve conter exatamente os campos da rubrica")
            scores = [self._score(rule["type"], rule, answer[key], rule.get("options"))
                      for key, rule in fields.items()]
            return sum(scores) / len(scores)
        raise ValueError(f"Tipo de exercício não suportado: {kind}")
