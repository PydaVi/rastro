"""
Rerun only the aws-iam-attach-role-policy-privesc campaign from Bloco 2 benchmark.
Uses existing discovery snapshot and campaign plan — skips discovery/synthesis.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from operations.models import AuthorizationConfig, TargetConfig
from operations.service import run_generated_campaign

PREV_OUTPUT = Path("outputs_bloco2_mutation_benchmark")
NEW_OUTPUT = Path("outputs_bloco2_mutate_rerun")
PROFILE = "aws-iam-attach-role-policy-privesc"

os.environ["RASTRO_ENABLE_AWS_REAL"] = "1"


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
        permitted_profiles=["aws-iam-attach-role-policy-privesc"],
        planner_config={
            "backend": "openai",
            "model": "gpt-4o",
        },
    )

    plans = [p for p in campaign_plan["plans"] if p["profile"] == PROFILE]
    assert plans, f"No plan found for {PROFILE}"

    from app.main import execute_run

    results = []
    for plan in plans:
        entry_identity = "arn:aws:iam::550192603632:user/brainctl-user"
        plan_id = f"{plan['id']}:brainctl-user"
        output_dir = NEW_OUTPUT / "campaigns" / PROFILE / plan_id.replace(":", "-")

        attack_steps = plan.get("signals", {}).get("attack_steps")
        print(f"Running campaign: {plan_id}")
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
        print(f"  objective_met={result.objective_met}")
        print(f"  error={result.error}")

    passed = sum(1 for r in results if r.objective_met)
    print(f"\nResult: {passed}/{len(results)} campaigns proved")


if __name__ == "__main__":
    main()
