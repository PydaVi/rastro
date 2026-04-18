"""
Bloco 4c benchmark: Privilege Scoring em conta sem naming convention.

Objetivo: validar que o engine seleciona platform-admin-role como target
para ops-deploy-user (que tem iam:AttachRolePolicy + CreatePolicyVersion
em Resource:*) com base no privilege_score — sem naming convention como hint.

Conta: terraform-realistic-iam (acme enterprise simulada)
  - ops-deploy-user: iam:AttachRolePolicy, CreatePolicyVersion, PutRolePolicy em *
  - platform-admin-role: iam:* em * (score esperado ~9999, target correto)
  - 9 outros roles com permissões menores (cicd-deploy, data-pipeline, etc.)

Critério de sucesso:
  - derived_attack_targets de ops-deploy-user aponta para platform-admin-role
  - privilege_score de platform-admin-role > todos os outros roles
  - Pelo menos 1 campanha de iam_privesc provada contra platform-admin-role
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ["RASTRO_ENABLE_AWS_REAL"] = "1"

from operations.models import AuthorizationConfig, TargetConfig
from operations.service import run_discovery_driven_assessment
from app.main import execute_run

OUTPUT = Path("outputs_bloco4c_privilege_scoring")
TARGET_JSON = Path("examples/target_realistic_iam.json")
ACCOUNT = "550192603632"

PERMITTED_PROFILES = [
    "aws-iam-attach-role-policy-privesc",
    "aws-iam-create-policy-version-privesc",
    "aws-iam-role-chaining",
    "aws-iam-secrets",
    "aws-iam-ssm",
]

PROFILE_ENTRY_IDENTITIES = {
    "aws-iam-attach-role-policy-privesc": [
        f"arn:aws:iam::{ACCOUNT}:user/ops-deploy-user",
    ],
    "aws-iam-create-policy-version-privesc": [
        f"arn:aws:iam::{ACCOUNT}:user/ops-deploy-user",
    ],
    "aws-iam-role-chaining": [
        f"arn:aws:iam::{ACCOUNT}:user/ops-deploy-user",
    ],
}


def main() -> None:
    target_data = json.loads(TARGET_JSON.read_text())
    target = TargetConfig.model_validate(target_data)

    authorization = AuthorizationConfig(
        authorized_by="PydaVi",
        authorized_at="2026-04-18",
        authorization_document="docs/authorization-blind-real.md",
        permitted_profiles=PERMITTED_PROFILES,
        permitted_entry_identities=[f"arn:aws:iam::{ACCOUNT}:user/ops-deploy-user"],
        profile_entry_identities=PROFILE_ENTRY_IDENTITIES,
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
        max_plans_per_profile=1,
        dedupe_resource_targets=True,
        strategic_planner=strategic_planner,
        max_hypotheses=20,
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

        print("\n=== DERIVED ATTACK TARGETS (ops-deploy-user) ===")
        for r in resources:
            if "ops-deploy-user" in r.get("identifier", ""):
                meta = r.get("metadata") or {}
                dat = meta.get("derived_attack_targets", [])
                if dat:
                    for d in dat:
                        print(f"  {d['action']} → {d['target_arn'].split('/')[-1]}")
                else:
                    print("  (nenhum derived_attack_target)")

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


if __name__ == "__main__":
    main()
