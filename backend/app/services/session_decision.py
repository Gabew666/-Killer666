"""Decisões determinísticas após uma resposta; sem acesso a banco ou LLM."""
from dataclasses import dataclass

from app.models import ActivityType, ExerciseAttempt, SessionActivity
from app.schemas.domain import PlannedActivity, StateData


@dataclass(frozen=True)
class SessionDecision:
    action: str
    reason: str
    activities: tuple[PlannedActivity, ...] = ()
    skip_feedback: bool = False


class SessionDecisionEngine:
    def decide(self, activity: SessionActivity, attempt: ExerciseAttempt, state: StateData,
               remaining_minutes: int, concept_name: str, concept_description: str,
               fresh_exercise_id: int | None = None,
               weak_prerequisite: tuple[int, str, str, int | None] | None = None,
               scheduled_confirmation: bool = False) -> SessionDecision:
        if remaining_minutes <= 3:
            return SessionDecision("FEEDBACK_AND_SUMMARY", "Tempo curto: concluir feedback e síntese; revisão já agendada.")
        if attempt.correct and attempt.hints_used > 0:
            if fresh_exercise_id and remaining_minutes >= 4:
                return SessionDecision("INSERT_CONFIRMATION", "Acerto com dica é prática assistida; confirmar sem dica em questão distinta.",
                    (self._activity(activity, concept_name, ActivityType.RECALL, 4,
                                    "Confirme sem dicas e sem consultar a resposta anterior.", fresh_exercise_id),), True)
            if scheduled_confirmation:
                return SessionDecision("CONTINUE_TO_CONFIRMATION", "Acerto com dica: usar a próxima questão já planejada como confirmação independente.",
                                       skip_feedback=True)
            return SessionDecision("SCHEDULE_CONFIRMATION", "Acerto com dica não cria evidência independente; confirmar em revisão futura.",
                                   skip_feedback=True)
        mode = activity.strategy or "diagnostic"
        if mode == "diagnostic" or activity.decision_after:
            if attempt.correct and attempt.is_independent:
                if state.evidence_count < 3 and fresh_exercise_id and remaining_minutes >= 4:
                    return SessionDecision("INSERT_CONFIRMATION", "Diagnóstico correto, mas evidência ainda insuficiente; confirmar em outra questão.",
                        (self._activity(activity, concept_name, ActivityType.RECALL, 4,
                                        "Confirme a compreensão sem consulta em questão diferente.", fresh_exercise_id),), True)
                if state.evidence_count < 3 and scheduled_confirmation:
                    return SessionDecision("CONTINUE_TO_CONFIRMATION", "Diagnóstico correto com pouca evidência; próxima questão distinta já está no plano.",
                                           skip_feedback=True)
                return SessionDecision("ADVANCE", "Diagnóstico correto e independente; permitir avanço e manter revisão agendada.",
                                       skip_feedback=True)
            return self._remediate(activity, remaining_minutes, concept_name, concept_description,
                                   "Erro no diagnóstico: explicar antes de praticar novamente.", fresh_exercise_id)
        if mode == "review":
            if attempt.correct and attempt.is_independent and attempt.attempt_kind == "DELAYED_RECALL":
                return SessionDecision("ADVANCE_REVIEW", "Recuperação tardia independente correta; revisão e retenção atualizadas.",
                                       skip_feedback=True)
            if not attempt.correct:
                return self._remediate(activity, remaining_minutes, concept_name, concept_description,
                                       "Erro em revisão: inserir explicação curta e nova prática.", fresh_exercise_id)
            return SessionDecision("KEEP_REVIEW", "Acerto antes do vencimento ou repetido; revisão não avançou.",
                                   skip_feedback=True)
        if not attempt.correct:
            if mode == "practice" and weak_prerequisite is not None and remaining_minutes >= 8:
                prereq_id, name, description, exercise_id = weak_prerequisite
                return SessionDecision("INSERT_PREREQUISITE_REMEDIATION", f"Erro em prática e base fraca conhecida: revisar {name}.", (
                    self._activity(activity, name, ActivityType.EXPLANATION, 3, description,
                                   concept_id=prereq_id),
                    self._activity(activity, name, ActivityType.GUIDED_EXERCISE, 5,
                                   "Pratique a base antes de retomar o conceito alvo.", exercise_id, prereq_id),
                ))
            return self._remediate(activity, remaining_minutes, concept_name, concept_description,
                                   "Erro em prática: revisar o conceito e aplicar novamente.", fresh_exercise_id)
        return SessionDecision("ADVANCE", "Resposta correta independente; continuar a sessão.", skip_feedback=True)

    @staticmethod
    def _activity(source: SessionActivity, name: str, kind: ActivityType, minutes: int,
                  instructions: str, exercise_id: int | None = None,
                  concept_id: int | None = None) -> PlannedActivity:
        return PlannedActivity(concept_id=concept_id or source.concept_id, concept=name,
                               activity_type=kind, estimated_minutes=minutes, instructions=instructions,
                               block=source.position, mode="bridge" if concept_id and concept_id != source.concept_id else "learn",
                               exercise_id=exercise_id)

    def _remediate(self, activity: SessionActivity, remaining: int, name: str, description: str,
                   reason: str, fresh_exercise_id: int | None) -> SessionDecision:
        if remaining < 6:
            return SessionDecision("FEEDBACK_AND_SUMMARY", reason + " Tempo restante insuficiente para uma prática nova.")
        additions = [
            self._activity(activity, name, ActivityType.EXPLANATION, 3, description),
            self._activity(activity, name, ActivityType.GUIDED_EXERCISE, 3,
                           "Resolva com apoio e registre dicas usadas.", activity.exercise_id),
        ]
        if fresh_exercise_id and remaining >= 10:
            additions.append(self._activity(activity, name, ActivityType.RECALL, 4,
                "Após a prática guiada, tente uma questão diferente sem dicas.", fresh_exercise_id))
        return SessionDecision("INSERT_GUIDED_PRACTICE", reason, tuple(additions))
