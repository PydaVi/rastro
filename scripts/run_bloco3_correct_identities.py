"""
Bloco 3 benchmark: campaigns com credenciais corretas dos lab users.
Roda re-discovery + strategic planning + campaigns usando cada privesc-user.
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

OUTPUT = Path("outputs_bloco3_correct_identities")

# Load credential profiles mapping from target config
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


def main() -> None:
    target_data = json.loads(TARGET_JSON.read_text())
    target = TargetConfig.model_validate(target_data)

    authorization = AuthorizationConfig(
        authorized_by="PydaVi",
        authorized_at="2026-04-04",
        authorization_document="docs/authorization-blind-real.md",
        permitted_profiles=PERMITTED_PROFILES,
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

    print("\n" + "=" * 60)
    print(f"campaigns_total:          {result.campaigns_total}")
    print(f"campaigns_passed:         {result.campaigns_passed}")
    print(f"campaigns_objective_not_met: {result.campaigns_objective_not_met}")
    print(f"campaigns_run_failed:     {result.campaigns_run_failed}")
    print(f"assessment_ok:            {result.assessment_ok}")

    if result.campaigns:
        print("\nPer-campaign results:")
        for c in result.campaigns:
            status = "PASS" if c.objective_met else ("ERR" if c.error else "FAIL")
            print(f"  [{status}] {c.profile} | {c.error or ''}")


if __name__ == "__main__":
    main()
