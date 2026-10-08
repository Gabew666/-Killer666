from collections.abc import Iterable

import networkx as nx

from app.schemas.domain import ConceptData, DependencyData, StateData


class KnowledgeGraph:
    def __init__(self, concepts: Iterable[ConceptData], dependencies: Iterable[DependencyData]):
        self.concepts = {c.id: c for c in concepts}
        self.graph = nx.DiGraph()
        self.graph.add_nodes_from(self.concepts)
        for dep in dependencies:
            self.add_dependency(dep)

    def add_dependency(self, dep: DependencyData) -> None:
        source, target = dep.prerequisite_concept_id, dep.concept_id
        if source not in self.concepts or target not in self.concepts:
            raise ValueError("Conceito ou pré-requisito inexistente")
        if source == target:
            raise ValueError("Auto-dependência inválida")
        if self.graph.has_edge(source, target):
            raise ValueError("Dependência duplicada")
        self.graph.add_edge(source, target, strength=dep.dependency_strength, essential=dep.is_essential)
        if not nx.is_directed_acyclic_graph(self.graph):
            self.graph.remove_edge(source, target)
            raise ValueError("A dependência introduz um ciclo")

    def ancestors(self, concept_id: int) -> set[int]:
        return nx.ancestors(self.graph, concept_id)

    def descendants(self, concept_id: int) -> set[int]:
        return nx.descendants(self.graph, concept_id)

    def prerequisites(self, concept_id: int) -> list[int]:
        return sorted(self.graph.predecessors(concept_id))

    def weak_prerequisites(self, concept_id: int, states: dict[int, StateData], threshold: float) -> list[int]:
        return [p for p in self.prerequisites(concept_id)
                if states.get(p) is None or states[p].mastery is None or states[p].mastery < threshold]

    def hard_blockers(self, concept_id: int, states: dict[int, StateData], threshold: float) -> list[int]:
        result = []
        # Um hard gate essencial não desaparece só porque está mais de uma aresta acima.
        for node in self.ancestors(concept_id) | {concept_id}:
            for source in self.prerequisites(node):
                edge = self.graph.edges[source, node]
                state = states.get(source)
                if edge["essential"] and (state is None or state.mastery is None or state.mastery < threshold):
                    result.append(source)
        return sorted(set(result))
