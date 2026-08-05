"""Bloco 14 — deriva: diff determinístico entre dois CapabilityGraph.

Compara os quatro tipos de aresta (can_read, can_assume, can_create_key,
can_mutate) entre dois grafos e reporta o que foi adicionado/removido. Puro,
sem I/O, sem AWS — a mesma disciplina do PolicyEvaluator (Bloco 12): roda em
cima de grafos já construídos, nunca chama a conta.

Dois usos:
  - deriva real: comparar dois snapshots de discovery coletados em momentos
    diferentes ("esse caminho não existia na semana passada").
  - verificação de remediação: comparar o grafo original contra um
    recomputado com uma política hipotética (ver operations.remediation).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.capability_graph import CapabilityGraph


@dataclass(frozen=True)
class GraphDiff:
    added_can_read: list[tuple[str, str]] = field(default_factory=list)
    removed_can_read: list[tuple[str, str]] = field(default_factory=list)
    added_can_assume: list[tuple[str, str]] = field(default_factory=list)
    removed_can_assume: list[tuple[str, str]] = field(default_factory=list)
    added_can_create_key: list[tuple[str, str]] = field(default_factory=list)
    removed_can_create_key: list[tuple[str, str]] = field(default_factory=list)
    added_can_mutate: list[tuple[str, str, str]] = field(default_factory=list)
    removed_can_mutate: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def added_total(self) -> int:
        return (
            len(self.added_can_read) + len(self.added_can_assume)
            + len(self.added_can_create_key) + len(self.added_can_mutate)
        )

    @property
    def removed_total(self) -> int:
        return (
            len(self.removed_can_read) + len(self.removed_can_assume)
            + len(self.removed_can_create_key) + len(self.removed_can_mutate)
        )

    @property
    def has_changes(self) -> bool:
        return self.added_total > 0 or self.removed_total > 0


def _pair_edges(edges: dict[str, list[str]]) -> set[tuple[str, str]]:
    return {(identity, target) for identity, targets in edges.items() for target in targets}


def _mutate_edges(edges: dict[str, list[tuple[str, str]]]) -> set[tuple[str, str, str]]:
    return {
        (identity, resource_arn, action)
        for identity, pairs in edges.items()
        for resource_arn, action in pairs
    }


def diff_capability_graphs(old: CapabilityGraph, new: CapabilityGraph) -> GraphDiff:
    """Diff determinístico entre dois grafos — não muta nenhum dos dois."""
    old_read, new_read = _pair_edges(old.can_read), _pair_edges(new.can_read)
    old_assume, new_assume = _pair_edges(old.can_assume), _pair_edges(new.can_assume)
    old_key, new_key = _pair_edges(old.can_create_key), _pair_edges(new.can_create_key)
    old_mutate, new_mutate = _mutate_edges(old.can_mutate), _mutate_edges(new.can_mutate)

    return GraphDiff(
        added_can_read=sorted(new_read - old_read),
        removed_can_read=sorted(old_read - new_read),
        added_can_assume=sorted(new_assume - old_assume),
        removed_can_assume=sorted(old_assume - new_assume),
        added_can_create_key=sorted(new_key - old_key),
        removed_can_create_key=sorted(old_key - new_key),
        added_can_mutate=sorted(new_mutate - old_mutate),
        removed_can_mutate=sorted(old_mutate - new_mutate),
    )
