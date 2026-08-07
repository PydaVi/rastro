"""Fase de labs — roda discovery real contra um lab JÁ APLICADO e pontua a
cobertura de hipótese contra o ground_truth (autorado no terraform).

Pré-requisito: você rodou `terraform apply` no diretório do lab (o classificador
exige que o apply/destroy seja seu). Este script NÃO aplica nada — só lê os
outputs do terraform, roda `run_foundation_discovery` com as SUAS credenciais
ambientes (você é dono da conta) e chama o scorer de integridade.

Uso:
    python terraform_labs/test_lab.py ec2_ssm_pivot
    python terraform_labs/test_lab.py kms_read_gate --bundle aws-advanced

Mede COBERTURA DE HIPÓTESE (o engine enxerga o caminho real do ground_truth?).
Prova de execução (mutação real + rollback) é o próximo passo, com credenciais
de entrada e a métrica de prova no scorer — ainda não incluída aqui.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from operations.models import AuthorizationConfig, TargetConfig  # noqa: E402
from operations.discovery import run_foundation_discovery  # noqa: E402
from lab_scorer import score_lab  # noqa: E402


def _tf_outputs(lab_dir: Path) -> dict:
    raw = subprocess.check_output(["terraform", f"-chdir={lab_dir}", "output", "-json"])
    return {k: v["value"] for k, v in json.loads(raw).items()}


def _account_and_region(outputs: dict, default_region: str) -> tuple[str, str]:
    # account_id extraído de qualquer ARN nos outputs
    account = None
    for v in outputs.values():
        arns = v if isinstance(v, list) else [v]
        for a in arns:
            if isinstance(a, str) and a.startswith("arn:aws:") and ":" in a:
                parts = a.split(":")
                if len(parts) > 4 and parts[4].isdigit():
                    account = parts[4]
                    break
        if account:
            break
    return account or "000000000000", default_region


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("lab")
    ap.add_argument("--bundle", default="aws-iam-heavy")
    ap.add_argument("--region", default="us-east-1")
    args = ap.parse_args()

    lab_dir = Path(__file__).resolve().parent / args.lab
    if not (lab_dir / "main.tf").exists():
        sys.exit(f"lab não encontrado: {lab_dir}")

    outputs = _tf_outputs(lab_dir)
    ground_truth = json.loads(outputs["ground_truth"])
    account, region = _account_and_region(outputs, args.region)

    # entry_roles: qualquer *_user_arn dos outputs (só pra validação do target;
    # o scorer usa os users DESCOBERTOS como entry set, não este campo)
    entry_arns = [v for k, v in outputs.items()
                  if k.endswith("_user_arn") and isinstance(v, str)]
    if not entry_arns:
        entry_arns = [v for k, v in outputs.items()
                      if k.endswith("_user_arns") and isinstance(v, list) for v in [v[0]] if v]

    run_dir = lab_dir / "_run"
    run_dir.mkdir(exist_ok=True)

    target = TargetConfig(name=args.lab, platform="aws", accounts=[account],
                          allowed_regions=[region], entry_roles=entry_arns or [f"arn:aws:iam::{account}:root"])
    authorization = AuthorizationConfig(
        authorized_by="rastro-labs", authorized_at="2026-08-07",
        authorization_document="docs/lab-integrity.md",
        permitted_profiles=[], excluded_profiles=[])

    print(f"[discovery] conta {account} região {region} — usando SUAS credenciais ambientes…")
    discovery_json, _md, _snap = run_foundation_discovery(
        bundle_name=args.bundle, target=target, authorization=authorization, output_dir=run_dir)

    # monta o dir consumível pelo scorer: env.discovery.json (real) + ground_truth + lab.yaml
    shutil.copy(discovery_json, run_dir / "env.discovery.json")
    (run_dir / "ground_truth.json").write_text(json.dumps(ground_truth, indent=2))
    shutil.copy(lab_dir / "lab.yaml", run_dir / "lab.yaml")

    # escopo do lab = todos os ARNs que o terraform criou (conta pode ter outros
    # recursos/labs; hipóteses fora do escopo não são FP deste lab)
    scope_arns: set[str] = set()
    for v in outputs.values():
        for a in (v if isinstance(v, list) else [v]):
            if isinstance(a, str) and a.startswith("arn:aws:"):
                scope_arns.add(a)

    res = score_lab(run_dir, scope_arns=scope_arns)
    print("\n=== integridade (cobertura de hipótese) ===")
    print(f"  lab: {res.name}  recall: {res.recall:.2f}  "
          f"FP inesperado: {len(res.false_positives)}  FP esperado: {len(res.expected_fp)}  "
          f"fora-de-escopo (outros recursos da conta): {len(res.out_of_scope)}")
    for p in res.covered_missed:
        print(f"  [MISS INESPERADO] {p.get('id','?')} {p['entry']} → {p['target']} — o engine devia achar")
    for p in res.ooc_missed:
        print(f"  [miss esperado] {p.get('id','?')} — {p.get('limitation','fora de cobertura')}")
    for fp in res.expected_fp:
        print(f"  [FP esperado] {fp['entry']} → {fp['target']} — limite conhecido declarado")
    for fp in res.false_positives:
        print(f"  [FALSO POSITIVO] {fp['entry']} → {fp['target']} [{fp['class']}]")
    if res.out_of_scope:
        print(f"  (info: {len(res.out_of_scope)} hipóteses sobre recursos fora do lab — ignoradas; "
              "rode em conta limpa ou destrua outros labs pra zerar)")
    if not res.covered_missed and not res.false_positives:
        print("  ✓ o engine enxergou os caminhos reais do lab e não inventou nenhum — cobertura íntegra")


if __name__ == "__main__":
    main()
