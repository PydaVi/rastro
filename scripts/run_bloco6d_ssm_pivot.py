"""
Bloco 6d integration test — SSM Parameter Pivot.

Fluxo testado:
  queue-indexer-user (ssm:GetParameter /svc/mesh/runtime/bootstrap)
    → lê param com credenciais de artifact-relay-user
      → assume batch-distributor-role como identidade extraída
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["RASTRO_ENABLE_AWS_REAL"] = "1"

from operations.models import AuthorizationConfig, TargetConfig
from operations.service import run_generated_campaign, _derive_credential_pivot_hypotheses
from app.main import execute_run

LAB_DIR = Path(__file__).parent.parent / "terraform-realistic-iam" / "ssm_parameter_pivot_real" / "rastro_local"
FIXTURE_PATH = LAB_DIR / "aws_ssm_parameter_pivot_lab.local.json"
OBJECTIVE_PATH = LAB_DIR / "objective_aws_ssm_parameter_pivot.local.json"
SCOPE_PATH = LAB_DIR / "scope_aws_ssm_parameter_pivot_openai.local.json"

OUTPUT = Path("outputs_bloco6d_ssm_pivot")
ACCOUNT = "550192603632"
REGION = "us-east-1"
ENTRY_USER_ARN = f"arn:aws:iam::{ACCOUNT}:user/queue-indexer-user"
TARGET_ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/batch-distributor-role"


def main() -> None:
    discovery_snapshot = json.loads(FIXTURE_PATH.read_text())

    hypotheses = _derive_credential_pivot_hypotheses(discovery_snapshot, [ENTRY_USER_ARN])
    print(f"\n{'='*60}")
    print(f"Hypotheses derivadas: {len(hypotheses)}")
    for h in hypotheses:
        print(f"  [{h.attack_class}] {h.entry_identity.split('/')[-1]} → {h.target.split('/')[-1]}")
        print(f"    intermediate: {h.intermediate_resource}")

    if not hypotheses:
        print("ERRO: nenhuma hipótese gerada — verifica readable_by no fixture")
        sys.exit(1)

    pivot_hyp = next((h for h in hypotheses if h.attack_class == "ssm_pivot" and h.target == TARGET_ROLE_ARN), None)
    if not pivot_hyp:
        print("ERRO: nenhuma hipótese ssm_pivot para target_role")
        sys.exit(1)

    campaign_output = OUTPUT / "campaigns" / "aws-credential-pivot-ssm" / "bloco6d-ssm"
    campaign_output.mkdir(parents=True, exist_ok=True)

    import shutil
    scope_path = campaign_output / "scope.json"
    objective_path = campaign_output / "objective.json"
    shutil.copy(SCOPE_PATH, scope_path)
    shutil.copy(OBJECTIVE_PATH, objective_path)

    plan = {
        "id": "bloco6d-ssm-test",
        "profile": "aws-credential-pivot-ssm",
        "resource_arn": TARGET_ROLE_ARN,
        "entry_identities": [ENTRY_USER_ARN],
        "generated_scope": str(scope_path),
        "generated_objective": str(objective_path),
        "signals": {
            "entry_identity": ENTRY_USER_ARN,
            "intermediate_resource": pivot_hyp.intermediate_resource,
            "attack_class": "ssm_pivot",
        },
    }

    target = TargetConfig(
        name="rastro-ssm-pivot-lab",
        accounts=[ACCOUNT],
        allowed_regions=[REGION],
        entry_roles=[],
        entry_credential_profiles={ENTRY_USER_ARN: "rastro-ssm-pivot-entry"},
    )

    authorization = AuthorizationConfig(
        authorized_by="PydaVi",
        authorized_at=date.today().isoformat(),
        authorization_document="docs/authorization-bloco6d.md",
        permitted_profiles=["aws-credential-pivot-ssm"],
        permitted_entry_identities=[ENTRY_USER_ARN],
        planner_config={"backend": "openai", "model": "gpt-4o"},
    )

    print(f"\n{'='*60}")
    print("Iniciando run real — aws-credential-pivot-ssm")
    print(f"  entry:        {ENTRY_USER_ARN.split('/')[-1]}")
    print(f"  target:       {TARGET_ROLE_ARN.split('/')[-1]}")
    print(f"  intermediate: {(pivot_hyp.intermediate_resource or '').split(':')[-1]}")

    result = run_generated_campaign(
        plan=plan,
        target=target,
        authorization=authorization,
        output_dir=campaign_output,
        runner=execute_run,
        max_steps=6,
        discovery_snapshot=discovery_snapshot,
    )

    print(f"\n{'='*60}")
    print(f"objective_met: {result.objective_met}")
    print(f"profile:       {result.profile}")
    print(f"error:         {result.error}")
    if result.report_json and Path(result.report_json).exists():
        report = json.loads(Path(result.report_json).read_text())
        steps = report.get("steps", [])
        print(f"steps:         {len(steps)}")
        for i, step in enumerate(steps):
            action = step.get("action", {})
            obs = step.get("observation", {})
            tool = action.get("tool", "?")
            actor = (action.get("actor") or "?").split("/")[-1]
            success = obs.get("success", "?")
            details = obs.get("details", {})
            synthetic = details.get("synthetic_actor", "").split("/")[-1]
            granted = details.get("granted_role", "").split("/")[-1]
            extra = f" → synthetic={synthetic}" if synthetic else ""
            extra += f" → granted={granted}" if granted else ""
            print(f"  step {i+1}: [{tool}] as {actor} → success={success}{extra}")
        flags = report.get("final_state", {}).get("flags", [])
        print(f"flags:         {flags}")


if __name__ == "__main__":
    main()
