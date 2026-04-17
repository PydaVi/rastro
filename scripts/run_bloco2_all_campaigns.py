"""Run all Bloco 2 campaigns using existing discovery + campaign plan."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from operations.models import AuthorizationConfig, TargetConfig
from operations.service import run_generated_campaign
from app.main import execute_run

PREV_OUTPUT = Path("outputs_bloco2_mutation_benchmark")
NEW_OUTPUT = Path("outputs_bloco2_all_campaigns")

os.environ["RASTRO_ENABLE_AWS_REAL"] = "1"

PERMITTED_PROFILES = [
    "aws-iam-role-chaining",
    "aws-iam-attach-role-policy-privesc",
    "aws-iam-create-policy-version-privesc",
]


def main() -> None:
    discovery_snapshot = json.loads((PREV_OUTPUT / "discovery" / "discovery.json").read_text())
    campaign_plan = json.loads((PREV_OUTPUT / "campaign-synthesis" / "campaign_plan.json").read_text())

    target = TargetConfig(
        name="aws",
        accounts=["550192603632"],
        allowed_regions=["us-east-1"],
        entry_roles=["arn:aws:iam::550192603632:user/brainctl-user"],
    )
    authorization = AuthorizationConfig(
        authorized_by="PydaVi",
        authorized_at="2026-04-04",
        authorization_document="docs/authorization-blind-real.md",
        permitted_profiles=PERMITTED_PROFILES,
        planner_config={"backend": "openai", "model": "gpt-4o"},
    )

    entry_identity = "arn:aws:iam::550192603632:user/brainctl-user"
    results = []

    for plan in campaign_plan["plans"]:
        plan_id = f"{plan['id']}:brainctl-user"
        output_dir = NEW_OUTPUT / "campaigns" / plan["profile"] / plan_id.replace(":", "-")
        attack_steps = plan.get("signals", {}).get("attack_steps")

        print(f"\nRunning: {plan['profile']}")
        print(f"  target: {plan['resource_arn']}")
        print(f"  attack_steps_hint: {attack_steps}")

        result = run_generated_campaign(
            plan={**plan, "id": plan_id, "entry_identities": [entry_identity]},
            target=target,
            authorization=authorization,
            output_dir=output_dir,
            runner=execute_run,
            max_steps=9,
            discovery_snapshot=discovery_snapshot,
            attack_steps=attack_steps,
        )
        results.append(result)
        print(f"  objective_met={result.objective_met}, error={result.error}")

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r.objective_met)
    print(f"Bloco 2 benchmark: {passed}/{len(results)} campaigns proved")
    for i, (plan, result) in enumerate(zip(campaign_plan["plans"], results)):
        status = "PASS" if result.objective_met else ("ERROR" if result.error else "FAIL")
        print(f"  [{status}] {plan['profile']}")


if __name__ == "__main__":
    main()
