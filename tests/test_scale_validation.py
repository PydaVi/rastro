"""Bloco 16.1 — canário de escala do engine de hipóteses.

Documenta e trava (pra não regredir silenciosamente) o achado da 16.1: a geração
CRUA de hipóteses do CapabilityGraph BFS cresce QUADRATICAMENTE no tamanho do
ambiente, porque o pivot por leitura de credencial varre TODOS os roles
(`_all_role_arns`), sem gate de assumability. O corte `max_hypotheses` é aplicado
DEPOIS dessa geração, então não protege da explosão.

Quando a 16.4 (ou uma correção do BFS) domar isso, este teste vai virar vermelho
DE PROPÓSITO — é o alvo a ser derrubado, não uma invariante permanente.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gen_synthetic_environment import generate_environment
from core.capability_graph import CapabilityGraph


def _raw_hypothesis_count(scale: int) -> int:
    snapshot = generate_environment(scale, seed=1337)
    graph = CapabilityGraph.build(snapshot)
    entries = sorted(
        r["identifier"] for r in snapshot["resources"]
        if r["resource_type"] == "identity.user"
    )
    return len(graph.derive_all_hypotheses(entries))


def test_raw_hypotheses_grow_quadratically_with_scale() -> None:
    # Determinístico via seed fixa — mesmos números do harness da 16.1.
    raw_10 = _raw_hypothesis_count(10)
    raw_20 = _raw_hypothesis_count(20)

    # Já em escala pequena, dezenas de entries produzem centenas/milhares de
    # hipóteses cruas — muito acima de linear.
    assert raw_10 > 100
    assert raw_20 > 100

    # Dobrar a escala multiplica a contagem crua por ~4 (quadrático), não ~2.
    # Se uma correção futura tornar isso ~linear, este assert cai — é o objetivo.
    ratio = raw_20 / raw_10
    assert ratio > 3.0, f"esperado crescimento quadratico (~4x), veio {ratio:.2f}x"
