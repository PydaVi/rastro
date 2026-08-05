"""Bloco 14 — loop de verificação de remediação.

Recomputa o CapabilityGraph substituindo a policy de UM principal por uma
versão proposta (hipotética), sem nenhuma chamada AWS — reaproveita o mesmo
_compute_capability_graph (Bloco 7) que o discovery real usa, só que sobre um
snapshot em memória com a policy trocada. Confirma se um caminho fecha E se a
mudança abre um caminho novo em outro lugar — a pergunta que uma "prova de
ataque" isolada nunca responde.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

from core.capability_graph import CapabilityGraph
from core.graph_diff import GraphDiff, diff_capability_graphs
from operations.discovery import _compute_capability_graph

# Campos que _compute_capability_graph calcula. Precisam ser limpos antes de
# recomputar: a função só GRAVA um campo quando o resultado novo é não-vazio
# (pra preservar anotação manual de fixture — ver docstring dela em
# discovery.py) — sem essa limpeza, remover uma permissão nunca zeraria um
# readable_by/assumable_by antigo, e verify_remediation reportaria "fechou"
# mesmo quando na verdade nunca recomputou nada.
_CAPABILITY_GRAPH_FIELDS = ("readable_by", "assumable_by", "createkey_by", "mutable_by")


def _strip_capability_annotations(resources: list[dict]) -> None:
    for resource in resources:
        meta = resource.get("metadata")
        if not meta:
            continue
        for field_name in _CAPABILITY_GRAPH_FIELDS:
            meta.pop(field_name, None)


@dataclass(frozen=True)
class RemediationResult:
    target_principal: str
    diff: GraphDiff
    closed_edges_from_principal: int
    newly_opened_edges: int

    @property
    def remediation_effective(self) -> bool:
        """True se a mudança fechou pelo menos uma aresta a partir do
        principal alvo e não abriu nenhuma aresta nova em lugar nenhum do
        grafo — a segunda condição é o que separa isto de uma prova de
        ataque isolada, que nunca checa se a correção abriu outro caminho."""
        return self.closed_edges_from_principal > 0 and self.newly_opened_edges == 0


def verify_remediation(
    discovery_snapshot: dict,
    *,
    target_principal: str,
    proposed_policy_permissions: list[dict],
) -> RemediationResult:
    """Recomputa o grafo com a policy proposta e diffa contra o original.

    proposed_policy_permissions substitui INTEIRAMENTE o
    metadata.policy_permissions do target_principal (mesmo formato do
    discovery.json: list[{"source": ..., "statements": [...]}]) — sem merge
    parcial, porque uma correção de política real é sempre a política
    inteira nova, não um patch.

    Zero chamada AWS: roda inteiramente sobre o snapshot já coletado.
    """
    original_resources = discovery_snapshot.get("resources", [])

    # Recomputa os dois lados do MESMO jeito, a partir de policy_permissions
    # — não confia no que já estiver pré-computado no snapshot de entrada
    # (que pode nem existir, se o snapshot não veio de run_foundation_discovery).
    # Sem isso, um snapshot de teste ou parcial faz o "original" e o
    # "proposto" ficarem em bases diferentes e o diff mente.
    original_working = copy.deepcopy(original_resources)
    _strip_capability_annotations(original_working)
    _compute_capability_graph(original_working)
    original_graph = CapabilityGraph.build({
        "resources": original_working,
        "governance": discovery_snapshot.get("governance"),
    })

    proposed_resources = copy.deepcopy(original_resources)
    _strip_capability_annotations(proposed_resources)
    found = False
    for resource in proposed_resources:
        if resource.get("identifier") == target_principal:
            resource.setdefault("metadata", {})["policy_permissions"] = proposed_policy_permissions
            found = True
    if not found:
        raise ValueError(f"target_principal {target_principal!r} não encontrado no discovery snapshot")

    _compute_capability_graph(proposed_resources)
    proposed_graph = CapabilityGraph.build({
        "resources": proposed_resources,
        "governance": discovery_snapshot.get("governance"),
    })

    diff = diff_capability_graphs(original_graph, proposed_graph)

    removed_pairs = (
        diff.removed_can_read + diff.removed_can_assume + diff.removed_can_create_key
        + [(identity, resource_arn) for (identity, resource_arn, _action) in diff.removed_can_mutate]
    )
    closed_from_principal = sum(1 for (identity, _target) in removed_pairs if identity == target_principal)

    return RemediationResult(
        target_principal=target_principal,
        diff=diff,
        closed_edges_from_principal=closed_from_principal,
        newly_opened_edges=diff.added_total,
    )
