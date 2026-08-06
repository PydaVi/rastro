"""Bloco 16.1 — Validação de escala do engine de hipóteses.

Discovery e geração de hipóteses nunca foram testados contra uma conta grande —
todo fixture de hoje tem 10–46 recursos. Este harness usa o gerador combinatório
(Camada C, `gen_synthetic_environment`) pra montar ambientes de centenas de
recursos e mede, por tamanho, as três coisas que a 16.1 exige confirmar:

  1. discovery (anotação do capability graph) não trava — mede tempo de
     `_compute_capability_graph` (O(principals × recursos), o estágio quadrático)
  2. o volume de hipóteses CRUAS não explode de um jeito que o corte de
     `max_hypotheses` não segure — mede a lista crua ANTES do corte
  3. tempo total dentro de um teto razoável

Mede exatamente o caminho de produção de `run_discovery_driven_assessment`
(fase 1 determinística): CapabilityGraph.build → derive_all_hypotheses →
sort estável → [:max_hypotheses]. Não toca AWS, não usa LLM.
"""
from __future__ import annotations

import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gen_synthetic_environment import generate_environment  # noqa: E402
from core.capability_graph import CapabilityGraph  # noqa: E402
from operations.discovery import _compute_capability_graph  # noqa: E402

MAX_HYPOTHESES = 20


def _confidence_score(conf: str) -> int:
    return {"high": 80, "medium": 50, "low": 20}.get(conf, 20)


def _time(fn):
    t0 = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t0


def run_one(scale: int) -> dict:
    # Gera SEM anotar, pra cronometrar a anotação separado
    # (generate_environment já anota; recompomos o estágio pra medi-lo isolado)
    snap = generate_environment(scale)
    resources = snap["resources"]
    n_res = len(resources)
    n_users = sum(1 for r in resources if r["resource_type"] == "identity.user")
    n_roles = sum(1 for r in resources if r["resource_type"] == "identity.role")

    # (1) estágio de anotação de discovery, isolado e cronometrado
    _, annotate_s = _time(lambda: _compute_capability_graph(resources))

    entry_identities = sorted(
        r["identifier"] for r in resources if r["resource_type"] == "identity.user"
    )

    tracemalloc.start()
    # (2) build + BFS
    graph, build_s = _time(lambda: CapabilityGraph.build(snap))
    raw_hyps, bfs_s = _time(lambda: graph.derive_all_hypotheses(entry_identities))
    # (3) sort estável + corte, exatamente como produção
    def _sort_and_cut():
        raw_hyps.sort(key=lambda h: (0 if h.evaluation_tier == "evaluated" else 1,
                                     -_confidence_score(h.confidence)))
        return raw_hyps[:MAX_HYPOTHESES]
    cut, sort_s = _time(_sort_and_cut)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "scale": scale,
        "resources": n_res,
        "users": n_users,
        "roles": n_roles,
        "annotate_s": annotate_s,
        "build_s": build_s,
        "bfs_s": bfs_s,
        "sort_s": sort_s,
        "raw_hyps": len(raw_hyps),
        "after_cut": len(cut),
        "peak_mb": peak / 1e6,
        "total_s": annotate_s + build_s + bfs_s + sort_s,
    }


def main() -> None:
    scales = [int(a) for a in sys.argv[1:]] or [20, 50, 100, 200, 400]
    rows = [run_one(s) for s in scales]

    hdr = (f"{'scale':>6} {'res':>6} {'users':>6} {'roles':>6} "
           f"{'annot_s':>9} {'bfs_s':>8} {'sort_s':>8} {'raw_hyps':>10} "
           f"{'cut':>5} {'peak_MB':>9} {'total_s':>9}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['scale']:>6} {r['resources']:>6} {r['users']:>6} {r['roles']:>6} "
              f"{r['annotate_s']:>9.3f} {r['bfs_s']:>8.3f} {r['sort_s']:>8.3f} "
              f"{r['raw_hyps']:>10,} {r['after_cut']:>5} {r['peak_mb']:>9.1f} "
              f"{r['total_s']:>9.3f}")

    # Ajuste de crescimento: raw_hyps vs recursos (quadrático esperado)
    print("\nCrescimento de hipóteses cruas (raw_hyps / resources):")
    for r in rows:
        print(f"  scale={r['scale']:>4}  raw_hyps={r['raw_hyps']:>10,}  "
              f"raw/res={r['raw_hyps']/max(1,r['resources']):>8.1f}  "
              f"raw/res^2={r['raw_hyps']/max(1,r['resources']**2):>7.4f}")


if __name__ == "__main__":
    main()
