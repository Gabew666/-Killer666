from datetime import datetime
import math

from app.core.config import MasteryConfig, PlannerConfig
from app.core.time import as_utc, elapsed_days
from app.models import ActivityType
from app.schemas.domain import (
    AssessmentData, AttemptSummary, ConceptData, PlannedActivity, ScoreExplanation,
    SessionPlan, StateData,
)
from app.services.knowledge_graph import KnowledgeGraph
from app.services.mastery import MasteryEngine
from app.services.planner.exam import ExamPriority


class AdaptivePlanner:
    def __init__(self, graph: KnowledgeGraph, *, timezone: str,
                 config: PlannerConfig = PlannerConfig(), mastery: MasteryEngine | None = None):
        self.graph = graph
        self.config = config
        self.mastery = mastery or MasteryEngine(MasteryConfig())
        self.exam = ExamPriority(timezone, config)

    def rank(self, states: dict[int, StateData], assessments: list[AssessmentData],
             attempts: list[AttemptSummary], now: datetime) -> list[ScoreExplanation]:
        current = {c: self.mastery.at_time(s, now) for c, s in states.items()}
        ranked = [self._score(c, current, assessments, attempts, now) for c in self.graph.concepts.values()]
        return sorted(ranked, key=lambda c: (-c.score, c.concept_id))

    def _effective(self, concept_id: int, states: dict[int, StateData]) -> float:
        state = states.get(concept_id)
        if state is None or state.mastery is None:
            return self.mastery.config.prior
        return state.mastery * state.retention

    def _score(self, concept: ConceptData, states: dict[int, StateData], assessments: list[AssessmentData],
               attempts: list[AttemptSummary], now: datetime) -> ScoreExplanation:
        cfg = self.config
        state = states.get(concept.id, StateData(concept_id=concept.id))
        direct, inherited, sources = self.exam.for_concept(concept.id, assessments, self.graph, now)
        review = 0.0
        if state.next_review_at and as_utc(state.next_review_at) <= as_utc(now):
            review = min(2.0, 1 + elapsed_days(state.next_review_at, now) / 7)
        descendants = self.graph.descendants(concept.id)
        prerequisite_value = min(1.0, sum(
            self.graph.concepts[c].importance * (1 - self._effective(c, states)) for c in descendants
        ) / 3)
        recent = sorted((a for a in attempts if a.concept_id == concept.id and as_utc(a.occurred_at) <= as_utc(now)),
                        key=lambda a: as_utc(a.occurred_at), reverse=True)[:5]
        recent_errors = sum((not a.correct) * math.exp(-elapsed_days(a.occurred_at, now) / 7)
                            for a in recent) / max(1, len(recent))
        prerequisites = self.graph.prerequisites(concept.id)
        total_strength = sum(self.graph.graph.edges[p, concept.id]["strength"] for p in prerequisites)
        prerequisite_gap = 0.0
        for p in prerequisites:
            known = states.get(p, StateData(concept_id=p)).mastery
            known = self.mastery.config.prior if known is None else known
            gap = max(0.0, (cfg.prerequisite_threshold - known) / cfg.prerequisite_threshold)
            prerequisite_gap += gap * self.graph.graph.edges[p, concept.id]["strength"] / total_strength
        effective = self._effective(concept.id, states)
        signals = {
            "exam_urgency": max(direct, inherited), "exam_direct": direct, "exam_inherited": inherited,
            "knowledge_gap": 1 - effective, "review_urgency": review,
            "importance": concept.importance, "prerequisite_value": prerequisite_value,
            "recent_errors": recent_errors,
            "mastery_penalty": effective * state.evidence_confidence if (state.mastery or 0) >= .8 else 0,
            "prerequisite_gap": prerequisite_gap,
        }
        components = {name: signals[name] * getattr(cfg, name) for name in (
            "exam_urgency", "knowledge_gap", "review_urgency", "importance", "prerequisite_value", "recent_errors")}
        components["mastery_penalty"] = -signals["mastery_penalty"] * cfg.mastery_penalty
        components["prerequisite_gap"] = -prerequisite_gap * cfg.prerequisite_gap
        weak = self.graph.weak_prerequisites(concept.id, states, cfg.prerequisite_threshold)
        blocked = self.graph.hard_blockers(concept.id, states, cfg.hard_gate_threshold)
        reasons = []
        if direct:
            reasons.append("Conteúdo explicitamente cobrado em avaliação futura/em andamento")
        if inherited:
            targets = sorted({self.graph.concepts[s["tested_concept_id"]].name for s in sources if s["inherited"]})
            reasons.append("Base necessária para " + ", ".join(targets))
        if review:
            reasons.append("Revisão vencida")
        low = state.evidence_count < 3 or state.evidence_confidence < .35
        if low:
            reasons.append("Pouca evidência: diagnóstico/recuperação recomendado")
        if recent_errors:
            reasons.append("Erros recentes precisam de investigação")
        if weak:
            reasons.append("Soft gating: revisar " + ", ".join(self.graph.concepts[p].name for p in weak))
        if blocked:
            reasons.append("Atividade avançada bloqueada apenas por base explicitamente essencial")
        if not reasons:
            reasons.append("Prioridade por lacuna, importância e retenção estimada")
        return ScoreExplanation(
            concept_id=concept.id, concept=concept.name, score=sum(components.values()),
            components=components, signals=signals, exam_sources=sources,
            reason=". ".join(reasons) + ".", weak_prerequisites=weak,
            hard_blocked_by=blocked, low_evidence=low,
        )

    def plan(self, student_id: int, available_minutes: int, states: dict[int, StateData],
             assessments: list[AssessmentData], attempts: list[AttemptSummary], now: datetime,
             exercises: dict[int, list[int]] | None = None) -> SessionPlan:
        cfg = self.config
        if type(available_minutes) is not int or not cfg.min_minutes <= available_minutes <= cfg.max_minutes:
            raise ValueError(f"Tempo deve estar entre {cfg.min_minutes} e {cfg.max_minutes} minutos")
        ranking = self.rank(states, assessments, attempts, now)
        budget = math.floor(available_minutes * (1 - cfg.time_margin))
        remaining = budget
        activities: list[PlannedActivity] = []
        covered: set[int] = set()
        studied: set[int] = set()
        eligible = [r for r in ranking if not r.hard_blocked_by and (exercises is None or exercises.get(r.concept_id))]
        pending = list(eligible)
        notes = ["Plano estimado: executar atividades não concede domínio automaticamente.",
                 "Escopo e questões iniciais são provisórios, sujeitos aos materiais da instituição."]
        block = 0
        since_break = 0
        while pending and remaining >= 8:
            candidate = pending.pop(0)
            concept_id = candidate.concept_id
            if concept_id in studied:
                continue
            if available_minutes >= 120 and since_break >= 40 and remaining >= 13:
                activities.append(PlannedActivity(concept_id=None, concept="Pausa", activity_type=ActivityType.BREAK,
                    estimated_minutes=5, instructions="Faça uma pausa breve antes do próximo bloco.", block=block + 1, mode="break"))
                remaining -= 5
                since_break = 0
            weak = [p for p in candidate.weak_prerequisites if p not in covered]
            # Não introduzir uma base cuja própria dependência essencial esteja bloqueada.
            bridgeable = {r.concept_id for r in eligible}
            weak.sort(key=lambda p: (states.get(p, StateData(concept_id=p)).mastery or 0, p))
            for prereq in weak:
                if remaining < 13 or prereq not in bridgeable:
                    continue
                block += 1
                activities.extend(self._bridge(prereq, block, exercises))
                covered.add(prereq)
                remaining -= 5
                since_break += 5
            uncovered = [p for p in weak if p not in covered]
            if uncovered:
                notes.append(f"{candidate.concept}: introdução com apoio; bases ainda frágeis: " +
                             ", ".join(self.graph.concepts[p].name for p in uncovered) + ".")
            duration = min(remaining, cfg.block_minutes, max(8, self.graph.concepts[concept_id].estimated_minutes))
            block += 1
            mode = "diagnostic" if candidate.low_evidence else ("review" if candidate.signals["review_urgency"] else "learn")
            activities.extend(self._block(concept_id, duration, block, mode, exercises))
            remaining -= duration
            since_break += duration
            covered.add(concept_id)
            studied.add(concept_id)
            # Após uma base, aproveitar a preparação para um alvo explicitamente cobrado.
            linked = [r for r in pending if r.signals["exam_direct"] >= .5
                      and concept_id in self.graph.ancestors(r.concept_id)]
            if linked:
                next_target = max(linked, key=lambda r: (r.signals["exam_direct"], r.score, -r.concept_id))
                pending.remove(next_target)
                pending.insert(0, next_target)
        if not activities:
            notes.append("Nenhuma atividade elegível com material disponível; revisar currículo e bases essenciais.")
        if remaining >= 8:
            notes.append("Sessão menor que o orçamento: faltam candidatos/material distintos elegíveis.")
        used = sum(a.estimated_minutes for a in activities)
        return SessionPlan(student_id=student_id, available_minutes=available_minutes, planned_minutes=used,
                           reserve_minutes=available_minutes - used, generated_at=as_utc(now),
                           activities=activities, ranking=ranking, notes=list(dict.fromkeys(notes)))

    def _bridge(self, concept_id: int, block: int, exercises: dict[int, list[int]] | None) -> list[PlannedActivity]:
        concept = self.graph.concepts[concept_id]
        exercise = (exercises or {}).get(concept_id, [None])[0]
        parts = [
            (ActivityType.RECALL, 2, f"Sem consulta, explique {concept.name} e identifique uma dúvida.", None),
            (ActivityType.EXPLANATION, 1, concept.description, None),
            (ActivityType.GUIDED_EXERCISE, 2, "Resolva com apoio se necessário; registre dicas, sem tratar retries como evidência nova.", exercise),
        ]
        return [PlannedActivity(concept_id=concept_id, concept=concept.name, activity_type=kind,
                                estimated_minutes=minutes, instructions=text, block=block,
                                mode="bridge", exercise_id=ex) for kind, minutes, text, ex in parts]

    def _block(self, concept_id: int, minutes: int, block: int, mode: str,
               exercises: dict[int, list[int]] | None) -> list[PlannedActivity]:
        concept = self.graph.concepts[concept_id]
        recall = max(1, int(minutes * .2))
        explanation = max(1, int(minutes * .2))
        correction = max(1, int(minutes * .1))
        summary = 1
        practice = minutes - recall - explanation - correction - summary
        ids = (exercises or {}).get(concept_id, [])
        # Com dois itens, diagnóstico antes da explicação e aplicação posterior são distintos.
        first = ids[0] if len(ids) >= 2 else None
        second = ids[1] if len(ids) >= 2 else (ids[0] if ids else None)
        parts = [
            (ActivityType.RECALL, recall, "Antes de consultar a explicação, recupere o conceito e responda ao diagnóstico disponível.", first),
            (ActivityType.EXPLANATION, explanation, concept.description, None),
            (ActivityType.INDEPENDENT_EXERCISE, practice, "Resolva sem consulta; se usar dicas, registre-as. Prefira justificar cada passo.", second),
            (ActivityType.ERROR_REVIEW, correction, "Compare com o feedback. Identifique se a dificuldade está no conceito, cálculo ou pré-requisito.", None),
            (ActivityType.SUMMARY, summary, "Explique a ideia central de memória e anote uma dúvida para a próxima revisão.", None),
        ]
        return [PlannedActivity(concept_id=concept_id, concept=concept.name, activity_type=kind,
                                estimated_minutes=duration, instructions=text, block=block,
                                mode=mode, exercise_id=ex) for kind, duration, text, ex in parts]
