"""
Bloco 5 benchmark: Full Account Scan — todos os entry identities.

Objetivo: demonstrar que o engine descobre e prova TODOS os attack paths
da conta realistic-iam autonomamente, sem configuração por usuário.

Entry identities (5 usuários):
  - ops-deploy-user:    iam:AttachRolePolicy + CreatePolicyVersion + sts:AssumeRole → platform-admin-role
  - data-engineer-user: iam:PassRole → data-pipeline-role; s3:* no data bucket
  - sre-oncall-user:    sts:AssumeRole → sre-ops-role (EC2+SSM)
  - dev-backend-user:   iam:CreateAccessKey em * (credenciais); secretsmanager em app secret
  - readonly-audit-user:sts:AssumeRole → audit-readonly-role

Critério de sucesso:
  - Pelo menos 1 campanha provada por entry identity que tenha alguma capability perigosa
  - Total de campanhas provadas >= 5 (ao menos 1 por vetor principal)
  - Engine seleciona alvos por privilege_score sem naming hints
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ["RASTRO_ENABLE_AWS_REAL"] = "1"
# OPENAI_API_KEY deve estar no ambiente — nunca hardcoded aqui

from operations.models import AuthorizationConfig, TargetConfig
from operations.service import run_discovery_driven_assessment
from app.main import execute_run

OUTPUT = Path("outputs_bloco5_full_account_scan")
TARGET_JSON = Path("examples/target_realistic_iam.json")
ACCOUNT = "550192603632"

PERMITTED_PROFILES = [
    "aws-iam-attach-role-policy-privesc",
    "aws-iam-create-policy-version-privesc",
    "aws-iam-pass-role-privesc",
    "aws-iam-role-chaining",
    "aws-iam-s3",
    "aws-iam-secrets",
    "aws-iam-ssm",
]

ALL_USERS = [
    f"arn:aws:iam::{ACCOUNT}:user/ops-deploy-user",
    f"arn:aws:iam::{ACCOUNT}:user/data-engineer-user",
    f"arn:aws:iam::{ACCOUNT}:user/sre-oncall-user",
    f"arn:aws:iam::{ACCOUNT}:user/dev-backend-user",
    f"arn:aws:iam::{ACCOUNT}:user/readonly-audit-user",
]


def main() -> None:
    target_data = json.loads(TARGET_JSON.read_text())
    target = TargetConfig.model_validate(target_data)

    authorization = AuthorizationConfig(
        authorized_by="PydaVi",
        authorized_at="2026-04-19",
        authorization_document="docs/authorization-blind-real.md",
        permitted_profiles=PERMITTED_PROFILES,
        permitted_entry_identities=ALL_USERS,
        profile_entry_identities={},   # engine escolhe entry por hipótese
        planner_config={"backend": "openai", "model": "gpt-4o"},
    )

    from planner.openai_strategic_planner import OpenAICompatibleStrategicPlanner
    strategic_planner = OpenAICompatibleStrategicPlanner(model="gpt-4o")

    result = run_discovery_driven_assessment(
        bundle_name="aws-iam-heavy",
        target=target,
        authorization=authorization,
        output_dir=OUTPUT,
        runner=execute_run,
        max_steps=9,
        max_plans_per_profile=3,      # até 3 alvos por perfil
        dedupe_resource_targets=False,
        strategic_planner=strategic_planner,
        max_hypotheses=40,            # conta maior, mais hipóteses
    )

    campaigns = result.campaigns
    passed = sum(1 for c in campaigns if c.objective_met)
    failed = sum(1 for c in campaigns if not c.objective_met and not c.error)
    errored = sum(1 for c in campaigns if c.error)

    print("\n" + "=" * 60)
    print(f"campaigns_total:   {len(campaigns)}")
    print(f"campaigns_passed:  {passed}")
    print(f"campaigns_failed:  {failed}")
    print(f"campaigns_errored: {errored}")
    print(f"summary:           {result.summary}")

    if campaigns:
        print("\nPer-campaign results:")
        for c in campaigns:
            entry = getattr(c, "identity_arn", None) or ""
            entry_short = entry.split("/")[-1] if "/" in entry else ""
            status = "PASS" if c.objective_met else ("ERR" if c.error else "FAIL")
            print(f"  [{status}] {c.profile} | {entry_short} | {c.error or ''}")

    # Análise de privilege scoring
    discovery_path = OUTPUT / "discovery" / "discovery.json"
    if discovery_path.exists():
        snapshot = json.loads(discovery_path.read_text())
        resources = snapshot.get("resources", [])

        print("\n=== PRIVILEGE SCORES (roles) ===")
        roles = [r for r in resources if r.get("resource_type") == "identity.role"]
        roles.sort(key=lambda r: (r.get("metadata") or {}).get("privilege_score", 0), reverse=True)
        for r in roles[:10]:
            meta = r.get("metadata") or {}
            name = r["identifier"].split("/")[-1]
            score = meta.get("privilege_score", 0)
            hvt = "★" if meta.get("is_high_value_target") else " "
            print(f"  {score:5d} {hvt} {name}")

        print("\n=== DERIVED TARGETS POR USUÁRIO ===")
        users = [r for r in resources if r.get("resource_type") == "identity.user"]
        for r in users:
            name = r["identifier"].split("/")[-1]
            dat = (r.get("metadata") or {}).get("derived_attack_targets", [])
            if dat:
                for d in dat:
                    action = d["action"]
                    tgt = d["target_arn"].split("/")[-1]
                    print(f"  {name:25s} {action} → {tgt}")

        principals_with_docs = sum(
            1 for r in resources
            if r.get("resource_type") in ("identity.user", "identity.role")
            and (r.get("metadata") or {}).get("policy_permissions")
        )
        total_principals = sum(
            1 for r in resources
            if r.get("resource_type") in ("identity.user", "identity.role")
        )
        print(f"\ndiscovery: {principals_with_docs}/{total_principals} principals com policy_permissions")

        # Resumo por entry identity
        print("\n=== CAMPANHAS POR ENTRY IDENTITY ===")
        by_entry: dict[str, list] = {}
        for c in campaigns:
            entry = getattr(c, "identity_arn", None) or "unknown"
            by_entry.setdefault(entry, []).append(c)
        for entry, cs in sorted(by_entry.items()):
            name = entry.split("/")[-1]
            p = sum(1 for c in cs if c.objective_met)
            f = sum(1 for c in cs if not c.objective_met and not c.error)
            print(f"  {name:25s} {p} passed / {f} failed / {len(cs)} total")


if __name__ == "__main__":
    main()
