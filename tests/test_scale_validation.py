"""Bloco 16.1 — canário de escala do engine de hipóteses.

Trava (pra não regredir silenciosamente) o resultado da 16.1: depois do teto de
fan-out do pivot (`_MAX_PIVOT_FANOUT`), a geração CRUA de hipóteses do
CapabilityGraph BFS cresce LINEARMENTE no tamanho do ambiente — antes era
quadrática (a 800 recursos: 245k hipóteses → 11.6k; BFS 96s → 2.9s).

A explosão vinha do pivot por credencial varrer TODOS os roles; agora varre só
os top-N por valor de alvo. Se alguém reintroduzir o sweep total (ou subir o
teto sem querer), o crescimento volta a super-linear e estes testes pegam.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gen_synthetic_environment import generate_environment
from core.capability_graph import CapabilityGraph, _MAX_PIVOT_FANOUT


def _graph(scale: int) -> CapabilityGraph:
    snapshot = generate_environment(scale, seed=1337)
    return CapabilityGraph.build(snapshot)


def _entries(scale: int, snapshot: dict) -> list[str]:
    return sorted(
        r["identifier"] for r in snapshot["resources"]
        if r["resource_type"] == "identity.user"
    )


def _raw_hypothesis_count(scale: int) -> int:
    snapshot = generate_environment(scale, seed=1337)
    graph = CapabilityGraph.build(snapshot)
    entries = sorted(
        r["identifier"] for r in snapshot["resources"]
        if r["resource_type"] == "identity.user"
    )
    return len(graph.derive_all_hypotheses(entries))


def test_raw_hypotheses_grow_linearly_after_pivot_fanout_cap() -> None:
    # Determinístico via seed fixa — mesmos números do harness da 16.1.
    raw_10 = _raw_hypothesis_count(10)
    raw_20 = _raw_hypothesis_count(20)

    # Dobrar a escala ~dobra a contagem crua (linear), não ~4x (quadrático).
    # Antes do teto: ratio ~3.7. Depois: ~2.0. A folga de 2.6 separa os regimes
    # com margem — se voltar a quadrático, ratio sobe pra ~4 e o teste pega.
    ratio = raw_20 / raw_10
    assert ratio < 2.6, f"crescimento voltou a super-linear ({ratio:.2f}x) — pivot fan-out explodiu de novo"


def test_pivot_fanout_is_capped_per_extracted_identity() -> None:
    # Ambiente com muito mais roles que o teto: cada pivot de credencial só pode
    # mirar _MAX_PIVOT_FANOUT roles distintos, não todos.
    scale = 40
    snapshot = generate_environment(scale, seed=1337)
    graph = CapabilityGraph.build(snapshot)
    entries = _entries(scale, snapshot)
    hyps = graph.derive_all_hypotheses(entries)

    n_roles = sum(1 for r in snapshot["resources"] if r["resource_type"] == "identity.role")
    assert n_roles > _MAX_PIVOT_FANOUT  # o teste só é significativo se há mais roles que o teto

    # Para cada (entry, recurso intermediário) de pivot, o nº de roles-alvo
    # distintos não passa do teto.
    from collections import defaultdict
    targets_by_pivot: dict[tuple, set] = defaultdict(set)
    for h in hyps:
        if h.intermediate_resource is not None:  # é um pivot (2-hop)
            targets_by_pivot[(h.entry_identity, h.intermediate_resource)].add(h.target)
    assert targets_by_pivot, "esperava ao menos um pivot no ambiente sintético"
    for key, targets in targets_by_pivot.items():
        assert len(targets) <= _MAX_PIVOT_FANOUT, f"{key} mirou {len(targets)} roles > teto {_MAX_PIVOT_FANOUT}"


def test_pivot_prioritizes_high_value_target_roles() -> None:
    # Quando há score de privilégio, o teto mantém os roles de MAIOR valor,
    # não uma fatia arbitrária por ARN.
    user = "arn:aws:iam::123:user/u"
    secret = "arn:aws:secretsmanager:us-east-1:123:secret/s"
    resources = [
        {"resource_type": "secret.secrets_manager", "identifier": secret,
         "metadata": {"readable_by": [user]}},
    ]
    # _MAX_PIVOT_FANOUT + 2 roles; os 2 de maior score devem sobreviver ao corte
    hi1 = "arn:aws:iam::123:role/aaa-low-but-early-arn"  # ARN cedo, score baixo
    hi2 = "arn:aws:iam::123:role/zzz-high-value"          # ARN tarde, score alto
    resources.append({"resource_type": "identity.role", "identifier": hi2,
                      "metadata": {"is_high_value_target": True, "privilege_score": 9000}})
    resources.append({"resource_type": "identity.role", "identifier": hi1,
                      "metadata": {"privilege_score": 1}})
    for i in range(_MAX_PIVOT_FANOUT):
        resources.append({"resource_type": "identity.role",
                          "identifier": f"arn:aws:iam::123:role/mid-{i:02d}",
                          "metadata": {"privilege_score": 100}})

    graph = CapabilityGraph.build({"resources": resources})
    hyps = graph.derive_all_hypotheses([user])
    pivot_targets = {h.target for h in hyps if h.intermediate_resource == secret}

    assert hi2 in pivot_targets  # high-value sobrevive apesar do ARN tardio
    assert len(pivot_targets) <= _MAX_PIVOT_FANOUT
