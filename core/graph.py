"""Skill DAG loading and validation.
core/ has no web-framework imports (README, "Architecture"), so this module
only ever raises plain Python exceptions - api/deps.py is responsible for
catching GraphValidationError and turning it into a loud startup failure.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from schemas.models import SkillNode


class GraphValidationError(ValueError):
    """Raised when the skill data doesn't form a valid prerequisite DAG."""


class SkillGraph:
    """A validated, queryable wrapper around the skill prerequisite graph.

    Edges point from prerequisite to dependent (python-basics -> python-oop),
    so topological order and nx.ancestors() both read as "what comes first".
    """

    def __init__(self, nodes: list[SkillNode]) -> None:
        self._nodes: dict[str, SkillNode] = {node.id: node for node in nodes}
        self._graph = nx.DiGraph()
        self._graph.add_nodes_from(self._nodes)
        for node in nodes:
            for prereq_id in node.prerequisites:
                self._graph.add_edge(prereq_id, node.id)
        self.validate()

    @classmethod
    def from_file(cls, path: str | Path) -> SkillGraph:
        raw = json.loads(Path(path).read_text())
        return cls([SkillNode.model_validate(entry) for entry in raw])

    def validate(self) -> None:
        dangling = {
            prereq_id
            for node in self._nodes.values()
            for prereq_id in node.prerequisites
            if prereq_id not in self._nodes
        }
        if dangling:
            raise GraphValidationError(
                f"prerequisites reference unknown skill ids: {sorted(dangling)}"
            )
        if not nx.is_directed_acyclic_graph(self._graph):
            cycle = nx.find_cycle(self._graph)
            raise GraphValidationError(f"skill graph contains a cycle: {cycle}")

    def __contains__(self, skill_id: str) -> bool:
        return skill_id in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    @property
    def skill_ids(self) -> set[str]:
        return set(self._nodes.keys())

    def get(self, skill_id: str) -> SkillNode:
        if skill_id not in self._nodes:
            raise KeyError(f"unknown skill id: {skill_id!r}")
        return self._nodes[skill_id]

    def prerequisites_of(self, skill_id: str) -> set[str]:
        """Direct (non-transitive) prerequisites."""
        return set(self._graph.predecessors(skill_id))

    def ancestors_of(self, skill_id: str) -> set[str]:
        """All prerequisites, transitively - everything that must come first."""
        return nx.ancestors(self._graph, skill_id)

    def unlocks(self, skill_id: str) -> set[str]:
        """Direct (non-transitive) dependents - what becomes learnable next."""
        return set(self._graph.successors(skill_id))
