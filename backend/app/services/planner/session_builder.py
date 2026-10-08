"""Composição de blocos segundo evidência observada, independente do ranking."""
from datetime import datetime
from typing import Literal

from app.core.time import as_utc, elapsed_days
from app.models import ActivityType
from app.schemas.domain import AttemptSummary, ConceptData, PlannedActivity, StateData

Strategy = Literal["diagnostic", "learn", "review", "practice"]


class SessionBuilder:
    def choose(self, state: StateData, attempts: list[AttemptSummary], now: datetime) -> Strategy:
        if state.mastery is None or state.evidence_count < 3 or state.evidence_confidence < .35:
            return "diagnostic"
        if state.next_review_at and as_utc(state.next_review_at) <= as_utc(now):
            return "review"
        if state.retention < .6 and state.mastery >= .6:
            return "review"
        assisted_recently = any(a.hints_used > 0 and a.concept_id == state.concept_id
                                and as_utc(a.occurred_at) <= as_utc(now)
                                and elapsed_days(a.occurred_at, now) <= 7 for a in attempts)
        if state.mastery < .6 or state.mastery * state.retention < .45 or (assisted_recently and state.mastery < .8):
            return "learn"
        return "practice"

    @staticmethod
    def _minutes(total: int, weights: list[float]) -> list[int]:
        if total < len(weights):
            raise ValueError("Bloco menor que o número de atividades")
        result = [1] * len(weights)
        leftover = total - len(weights)
        fractional = [leftover * weight / sum(weights) for weight in weights]
        for i, value in enumerate(fractional):
            result[i] += int(value)
        for index in sorted(range(len(weights)), key=lambda i: fractional[i] - int(fractional[i]), reverse=True)[:total - sum(result)]:
            result[index] += 1
        return result

    def build(self, concept: ConceptData, minutes: int, block: int, strategy: Strategy,
              exercise_ids: list[int]) -> list[PlannedActivity]:
        first = exercise_ids[0] if exercise_ids else None
        second = exercise_ids[1] if len(exercise_ids) > 1 else first
        if strategy == "diagnostic":
            # A explicação é decisão posterior à correção; não presumir desconhecimento.
            parts = [
                (ActivityType.RECALL, "Responda sem consulta para medir o ponto de partida. Registre confiança e dicas usadas.", first),
                (ActivityType.ERROR_REVIEW, "Confira a resposta e identifique o tipo de erro, se houver.", None),
                (ActivityType.SUMMARY, "Após a avaliação, replaneje o tempo restante: acerto independente sugere avanço; erro ou dica pede explicação e prática guiada.", None),
            ]
            weights = [6, 2, 1]
        elif strategy == "learn":
            parts = [
                (ActivityType.RECALL, "Recupere o que já sabe; localize a lacuna antes de ler.", None),
                (ActivityType.EXPLANATION, concept.description, None),
                (ActivityType.GUIDED_EXERCISE, "Aplique a regra passo a passo com apoio da explicação; registre as dicas usadas.", first if len(exercise_ids) > 1 else None),
                (ActivityType.INDEPENDENT_EXERCISE, "Resolva sem consulta e justifique os passos.", second),
                (ActivityType.ERROR_REVIEW, "Compare com a solução e classifique a dificuldade encontrada.", None),
                (ActivityType.SUMMARY, "Explique a ideia central de memória e registre uma dúvida.", None),
            ]
            weights = [1, 3, 2, 4, 2, 1]
        elif strategy == "review":
            parts = [
                (ActivityType.RECALL, "Recupere o conceito sem consultar anotações e responda à questão.", first),
            ]
            weights = [5]
            if len(exercise_ids) > 1:
                parts.append((ActivityType.QUIZ, "Teste a aplicação em uma segunda questão.", exercise_ids[1]))
                weights.append(3)
            parts.extend([
                (ActivityType.ERROR_REVIEW, "Verifique erros antes de decidir se precisa de nova explicação.", None),
                (ActivityType.SUMMARY, "Resuma de memória e verifique o próximo vencimento da revisão.", None),
            ])
            weights.extend([2, 1])
        else:
            parts = [
                (ActivityType.RECALL, "Faça recuperação rápida de memória antes da aplicação.", None),
                (ActivityType.INDEPENDENT_EXERCISE, "Resolva sem consulta, explicando seu raciocínio.", first),
                (ActivityType.ERROR_REVIEW, "Compare a solução e investigue eventuais erros.", None),
                (ActivityType.SUMMARY, "Registre uma síntese curta e a próxima dúvida.", None),
            ]
            weights = [2, 6, 2, 1]
        allocations = self._minutes(minutes, weights)
        return [PlannedActivity(concept_id=concept.id, concept=concept.name, activity_type=kind,
                                estimated_minutes=duration, instructions=instructions, block=block,
                                mode=strategy, exercise_id=exercise_id,
                                decision_after=strategy == "diagnostic" and index == 0)
                for index, ((kind, instructions, exercise_id), duration) in enumerate(zip(parts, allocations))]
