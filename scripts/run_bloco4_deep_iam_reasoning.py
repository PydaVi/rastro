"""
Bloco 4 benchmark: Deep IAM Reasoning.
Discovery agora enriquece policies com documentos reais (GetPolicyVersion, GetRolePolicy,
GetUserPolicy). StrategicPlanner recebe policy_permissions com Effect/Action/Resource/Condition
em vez de raciocinar apenas pelos nomes das policies.

Objetivo: verificar que o planner identifica paths exploitaveis com base nas permissoes reais,
nao apenas em heuristicas de nome de policy.

Identidades selecionadas (cobertura expandida — mais paths do lab):
  - privesc1 a privesc9 users (os 9 mais comuns de IAM privesc)
  - brainctl-user (role chaining — starting-role only trusts brainctl-user)
  - brainctl-user (sanity check admin)
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

OUTPUT = Path("outputs_bloco4_deep_iam_reasoning")

TARGET_JSON = Path("examples/target_iam_vulnerable.json")

PERMITTED_PROFILES = [
    "aws-iam-role-chaining",
    "aws-iam-attach-role-policy-privesc",
    "aws-iam-create-policy-version-privesc",
    "aws-iam-pass-role-privesc",
    "aws-iam-s3",
    "aws-iam-secrets",
    "aws-iam-ssm",
]

ACCOUNT = "550192603632"

PERMITTED_ENTRY_IDENTITIES = [
    f"arn:aws:iam::{ACCOUNT}:user/brainctl-user",
]

PROFILE_ENTRY_IDENTITIES = {
    "aws-iam-attach-role-policy-privesc": [
        f"arn:aws:iam::{ACCOUNT}:user/privesc9-AttachRolePolicy-user",
        f"arn:aws:iam::{ACCOUNT}:user/brainctl-user",
    ],
    "aws-iam-create-policy-version-privesc": [
        f"arn:aws:iam::{ACCOUNT}:user/privesc1-CreateNewPolicyVersion-user",
        f"arn:aws:iam::{ACCOUNT}:user/brainctl-user",
    ],
    "aws-iam-role-chaining": [
        f"arn:aws:iam::{ACCOUNT}:user/brainctl-user",
    ],
    "aws-iam-pass-role-privesc": [
        f"arn:aws:iam::{ACCOUNT}:user/brainctl-user",
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
        permitted_entry_identities=PERMITTED_ENTRY_IDENTITIES,
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

    # Verifica se o discovery snapshot tem policy_permissions
    discovery_path = OUTPUT / "discovery" / "discovery.json"
    if discovery_path.exists():
        snapshot = json.loads(discovery_path.read_text())
        principals_with_docs = sum(
            1 for r in snapshot.get("resources", [])
            if r.get("resource_type") in ("identity.user", "identity.role")
            and (r.get("metadata") or {}).get("policy_permissions")
        )
        total_principals = sum(
            1 for r in snapshot.get("resources", [])
            if r.get("resource_type") in ("identity.user", "identity.role")
        )
        print(f"\ndiscovery: {principals_with_docs}/{total_principals} principals with policy_permissions")


if __name__ == "__main__":
    main()
