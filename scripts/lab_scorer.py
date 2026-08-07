"""Fase de labs — scorer de integridade (anti-viés-de-confirmação).

O risco central desta fase: quem construiu o engine constrói os labs e planta só
o que o engine acerta → labs passam → falsa confiança. Este scorer existe pra
tornar isso IMPOSSÍVEL de esconder:

  1. GROUND TRUTH INDEPENDENTE — cada lab declara os caminhos de ataque reais
     (`ground_truth.json`), derivados da intenção do ambiente, NUNCA da saída do
     engine. O scorer compara a saída do engine contra essa verdade.
  2. PLANTS FORA DE COBERTURA — caminhos marcados `in_coverage: false` são os que
     o engine DEVE errar hoje (limite de arquitetura conhecido). Miss deles é
     ESPERADO e registrado, não mascarado.
  3. CONTROLE NEGATIVO — lab com `true_paths: []`: qualquer hipótese é falso
     positivo. Mede FP real.
  4. HELD-OUT — labs `held_out: true` nunca devem ser usados pra ajustar o engine;
     o scorer os separa e (por padrão) não os roda, pra não contaminar.
  5. GUARDA DE PERFEIÇÃO SUSPEITA — um suite de desafio com recall 1.0, 0 FP e
     ZERO plants fora-de-cobertura é ALERTADO como provável viés de confirmação,
     não celebrado.

Métrica é de HYPOTHESIS COVERAGE (o engine ENXERGA o caminho?), não de prova —
prova exige execução em AWS real, que vem quando os labs forem aplicados. Um lab
cujo caminho o engine nem gera como hipótese nunca vai provar nada, então cobrir
a hipótese é o piso necessário e o que dá pra medir offline.

Uso:
  python scripts/lab_scorer.py labs/           # roda os labs não-held-out
  python scripts/lab_scorer.py labs/ --held-out  # roda SÓ os held-out (medição final)
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml  # noqa: E402

from core.capability_graph import CapabilityGraph  # noqa: E402


@dataclass
class LabResult:
    name: str
    layer: str
    challenge: bool
    covered_found: list = field(default_factory=list)      # in_coverage achado (bom)
    covered_missed: list = field(default_factory=list)     # in_coverage NÃO achado (RUIM)
    ooc_missed: list = field(default_factory=list)         # out-of-coverage não achado (esperado)
    ooc_found: list = field(default_factory=list)          # out-of-coverage achado (surpresa boa)
    false_positives: list = field(default_factory=list)    # hipótese sem caminho verdadeiro (BUG)
    expected_fp: list = field(default_factory=list)         # FP por limite conhecido, declarado em false_paths
    out_of_scope: list = field(default_factory=list)        # hipótese sobre recurso fora do lab (conta compartilhada)

    @property
    def recall(self) -> float:
        denom = len(self.covered_found) + len(self.covered_missed)
        return len(self.covered_found) / denom if denom else 1.0


import re as _re

_SM_SUFFIX = _re.compile(r"^(arn:aws:secretsmanager:[^:]*:[^:]*:secret:.+)-[A-Za-z0-9]{6}$")


def _norm(arn: str) -> str:
    """Normaliza o sufixo aleatório de 6 chars que o Secrets Manager anexa ao ARN:
    o terraform/policy usa COM sufixo, o discovery guarda SEM. Sem isso os pares
    (entry, secret) não casariam entre ground_truth e saída do engine."""
    m = _SM_SUFFIX.match(arn)
    return m.group(1) if m else arn


def _pair(entry: str, target: str) -> tuple[str, str]:
    return (_norm(entry), _norm(target))


def score_lab(lab_dir: Path, scope_arns: set[str] | None = None) -> LabResult:
    meta = yaml.safe_load((lab_dir / "lab.yaml").read_text())
    env = json.loads((lab_dir / "env.discovery.json").read_text())
    gt = json.loads((lab_dir / "ground_truth.json").read_text())
    true_paths = gt.get("true_paths", [])
    # Escopo de conta compartilhada: num account com outros recursos (outros labs),
    # o discovery vê tudo. Uma hipótese cujo entry OU target está FORA do escopo do
    # lab não é FP deste lab — é outro caminho da conta. scope_arns (os ARNs que o
    # lab criou) restringe a contagem de FP; ausente = comportamento antigo (conta
    # limpa). Os caminhos do ground_truth entram no escopo automaticamente.
    scope_norm: set[str] | None = None
    if scope_arns is not None:
        scope_norm = {_norm(a) for a in scope_arns}
        for p in true_paths + gt.get("false_paths", []):
            scope_norm.add(_norm(p["entry"])); scope_norm.add(_norm(p["target"]))
    # false_paths: caminhos que o engine ERRADAMENTE reporta por limite conhecido
    # (ex.: SCP-cego no grafo). FP esperado e declarado — simétrico ao in_coverage:false.
    false_paths = gt.get("false_paths", [])

    graph = CapabilityGraph.build(env)
    entries = sorted(
        r["identifier"] for r in env["resources"] if r["resource_type"] == "identity.user"
    )
    hyps = graph.derive_all_hypotheses(entries)
    engine_pairs = {_pair(h.entry_identity, h.target) for h in hyps}
    truth_pairs = {_pair(p["entry"], p["target"]) for p in true_paths}
    false_pairs = {_pair(p["entry"], p["target"]) for p in false_paths}

    res = LabResult(name=meta["name"], layer=meta.get("layer", "C"),
                    challenge=bool(meta.get("challenge", False)))

    for p in true_paths:
        found = _pair(p["entry"], p["target"]) in engine_pairs
        if p.get("in_coverage", True):
            (res.covered_found if found else res.covered_missed).append(p)
        else:
            (res.ooc_found if found else res.ooc_missed).append(p)

    for h in hyps:
        pair = _pair(h.entry_identity, h.target)
        if pair in truth_pairs:
            continue
        # fora do escopo do lab (outro recurso da conta) → nem TP nem FP deste lab
        if scope_norm is not None and (_norm(h.entry_identity) not in scope_norm or _norm(h.target) not in scope_norm):
            res.out_of_scope.append({"entry": h.entry_identity, "target": h.target, "class": h.attack_class})
            continue
        entry = {"entry": h.entry_identity, "target": h.target, "class": h.attack_class}
        if pair in false_pairs:
            res.expected_fp.append(entry)   # FP conhecido/declarado — não é bug
        else:
            res.false_positives.append(entry)  # FP inesperado — bug
    return res


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    root = Path(args[0]) if args else Path("labs")
    want_held_out = "--held-out" in flags

    lab_dirs = sorted(d for d in root.iterdir() if (d / "lab.yaml").exists())
    results: list[LabResult] = []
    for d in lab_dirs:
        meta = yaml.safe_load((d / "lab.yaml").read_text())
        if bool(meta.get("held_out", False)) != want_held_out:
            continue
        results.append(score_lab(d))

    if not results:
        print(f"nenhum lab {'held-out' if want_held_out else 'de dev'} em {root}/")
        return

    print(f"{'lab':32} {'layer':5} {'recall':>7} {'FP':>4} {'miss(cov)':>9} {'miss(ooc)':>9} {'ooc_hit':>8}")
    print("-" * 84)
    total_fp = total_cov_miss = total_ooc_plants = challenge_labs = 0
    perfect_challenge = 0
    for r in results:
        print(f"{r.name:32} {r.layer:5} {r.recall:>7.2f} {len(r.false_positives):>4} "
              f"{len(r.covered_missed):>9} {len(r.ooc_missed):>9} {len(r.ooc_found):>8}")
        total_fp += len(r.false_positives)
        total_cov_miss += len(r.covered_missed)
        total_ooc_plants += len(r.ooc_missed) + len(r.ooc_found)
        if r.challenge:
            challenge_labs += 1
            if r.recall == 1.0 and not r.false_positives:
                perfect_challenge += 1

    print("\n=== integridade ===")
    # Misses ESPERADOS (fora de cobertura): registrados, não mascarados
    for r in results:
        for p in r.ooc_missed:
            print(f"  [miss esperado] {r.name}: {p.get('id','?')} — {p.get('limitation','fora de cobertura')}")
    # Misses INESPERADOS (deveria achar e não achou): BUG
    for r in results:
        for p in r.covered_missed:
            print(f"  [MISS INESPERADO] {r.name}: {p.get('id','?')} {p['entry']} → {p['target']} — o engine devia achar")
    # FPs esperados (limite conhecido, declarado em false_paths) — registrados, não bug
    for r in results:
        for fp in r.expected_fp:
            print(f"  [FP esperado] {r.name}: {fp['entry']} → {fp['target']} [{fp['class']}] — limite conhecido (SCP-cego etc.)")
    # Falsos positivos INESPERADOS = bug
    if total_fp:
        for r in results:
            for fp in r.false_positives:
                print(f"  [FALSO POSITIVO] {r.name}: {fp['entry']} → {fp['target']} [{fp['class']}]")

    # Guarda de perfeição suspeita
    print()
    if total_ooc_plants == 0 and challenge_labs > 0:
        print("  ⚠ ALERTA: labs de desafio sem NENHUM plant fora-de-cobertura — "
              "provável viés de confirmação (só planta o que o engine acerta).")
    if challenge_labs and perfect_challenge == challenge_labs and total_ooc_plants == 0:
        print("  ⚠ ALERTA: todos os labs de desafio deram recall 1.0 / 0 FP e não há "
              "plant fora-de-cobertura — isso é sinal de labs fáceis, não de engine perfeito.")
    if total_cov_miss == 0 and total_fp == 0 and total_ooc_plants > 0:
        print("  ✓ suite tem plants fora-de-cobertura e o engine acertou o que devia — "
              "integridade preservada (misses esperados registrados acima).")
    print(f"\n  labs: {len(results)} | FP total: {total_fp} | miss inesperado: {total_cov_miss} "
          f"| plants fora-de-cobertura: {total_ooc_plants}")


if __name__ == "__main__":
    main()
