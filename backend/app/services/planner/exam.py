from datetime import datetime
from zoneinfo import ZoneInfo

import networkx as nx

from app.core.config import PlannerConfig
from app.core.time import as_utc
from app.schemas.domain import AssessmentData
from app.services.knowledge_graph import KnowledgeGraph


class ExamPriority:
    def __init__(self, timezone: str, config: PlannerConfig = PlannerConfig()):
        self.zone = ZoneInfo(timezone)
        self.config = config

    def urgency(self, assessment: AssessmentData, now: datetime) -> float:
        today = as_utc(now).astimezone(self.zone).date()
        if today > assessment.end_date:
            return 0.0
        days = max(0, (assessment.start_date - today).days)
        horizon = self.config.exam_horizon_days
        return assessment.importance * horizon / (horizon + days)

    def for_concept(self, concept_id: int, assessments: list[AssessmentData],
                    graph: KnowledgeGraph, now: datetime) -> tuple[float, float, list[dict]]:
        direct = inherited = 0.0
        sources = []
        for assessment in assessments:
            urgency = self.urgency(assessment, now)
            if not urgency:
                continue
            for tested, weight in assessment.concept_weights.items():
                if tested not in graph.concepts:
                    raise ValueError("Avaliação referencia conceito ausente do grafo")
                if tested == concept_id:
                    distance = 0
                elif tested in graph.descendants(concept_id):
                    distance = nx.shortest_path_length(graph.graph, concept_id, tested)
                else:
                    continue
                value = urgency * weight * self.config.inherited_exam_discount ** distance
                if distance == 0:
                    direct = max(direct, value)
                else:
                    inherited = max(inherited, value)
                sources.append({"assessment_id": assessment.id, "assessment": assessment.name,
                                "tested_concept_id": tested, "weight": weight,
                                "distance": distance, "inherited": distance > 0, "urgency": value})
        return direct, inherited, sources
