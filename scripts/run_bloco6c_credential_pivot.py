"""
Bloco 6c integration test — Credential Pivot Chain.

Fluxo testado:
  entry_user (secretsmanager:GetSecretValue)
    → lê secret com credenciais de rastro-pivot-svc-user
      → assume rastro-pivot-target-role como identidade extraída

Usa o snapshot pre-construído pelo terraform (credential_pivot_real)
sem rodar discovery real, para isolar exatamente o pipeline do 6c.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ["RASTRO_ENABLE_AWS_REAL"] = "1"

from operations.models import AuthorizationConfig, TargetConfig
from operations.service import run_generated_campaign, _derive_credential_pivot_hypotheses
from app.main import execute_run

# ---------------------------------------------------------------------------
# Caminhos do módulo terraform
# ---------------------------------------------------------------------------

PIVOT_DIR = Path(__file__).parent.parent / "terraform_local_lab" / "credential_pivot_real" / "rastro_local"
FIXTURE_PATH = PIVOT_DIR / "aws_credential_pivot_lab.local.json"
OBJECTIVE_PATH = PIVOT_DIR / "objective_aws_credential_pivot.local.json"
SCOPE_PATH = PIVOT_DIR / "scope_aws_credential_pivot_openai.local.json"

OUTPUT = Path("outputs_bloco6c_credential_pivot")

ACCOUNT = "550192603632"
REGION = "us-east-1"
ENTRY_USER_ARN = f"arn:aws:iam::{ACCOUNT}:user/rastro-pivot-entry-user"
TARGET_ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/rastro-pivot-target-role"


def main() -> None:
    discovery_snapshot = json.loads(FIXTURE_PATH.read_text())

    # ---------------------------------------------------------------------------
    # Verifica que _derive_credential_pivot_hypotheses dispara corretamente
    # ---------------------------------------------------------------------------
    hypotheses = _derive_credential_pivot_hypotheses(discovery_snapshot, [ENTRY_USER_ARN])
    print(f"\n{'='*60}")
    print(f"Hypotheses derivadas: {len(hypotheses)}")
    for h in hypotheses:
        print(f"  [{h.attack_class}] {h.entry_identity.split('/')[-1]} → {h.target.split('/')[-1]}")
        print(f"    intermediate: {h.intermediate_resource}")
        print(f"    confidence: {h.confidence}")

    if not hypotheses:
        print("ERRO: nenhuma hipótese gerada — verifica readable_by no fixture")
        sys.exit(1)

    pivot_hyp = next((h for h in hypotheses if h.attack_class == "credential_pivot"), None)
    if not pivot_hyp:
        print("ERRO: nenhuma hipótese credential_pivot")
        sys.exit(1)

    # ---------------------------------------------------------------------------
    # Monta o plan diretamente (sem campaign_synthesis) para execução real
    # ---------------------------------------------------------------------------
    campaign_output = OUTPUT / "campaigns" / "aws-credential-pivot" / "bloco6c-pivot"
    campaign_output.mkdir(parents=True, exist_ok=True)

    # Copia scope e objective para o diretório da campanha
    # (run_generated_campaign lê esses paths em disco)
    import shutil
    scope_path = campaign_output / "scope.json"
    objective_path = campaign_output / "objective.json"
    shutil.copy(SCOPE_PATH, scope_path)
    shutil.copy(OBJECTIVE_PATH, objective_path)

    plan = {
        "id": "bloco6c-pivot-test",
        "profile": "aws-credential-pivot",
        "resource_arn": TARGET_ROLE_ARN,
        "entry_identities": [ENTRY_USER_ARN],
        "generated_scope": str(scope_path),
        "generated_objective": str(objective_path),
        "signals": {
            "entry_identity": ENTRY_USER_ARN,
            "intermediate_resource": pivot_hyp.intermediate_resource,
            "attack_class": "credential_pivot",
        },
    }

    target = TargetConfig(
        name="rastro-credential-pivot-lab",
        accounts=[ACCOUNT],
        allowed_regions=[REGION],
        entry_roles=[],
        entry_credential_profiles={
            ENTRY_USER_ARN: "rastro-pivot-entry",
        },
    )

    authorization = AuthorizationConfig(
        authorized_by="PydaVi",
        authorized_at=date.today().isoformat(),
        authorization_document="docs/authorization-bloco6c.md",
        permitted_profiles=["aws-credential-pivot"],
        permitted_entry_identities=[ENTRY_USER_ARN],
        planner_config={"backend": "openai", "model": "gpt-4o"},
    )

    print(f"\n{'='*60}")
    print("Iniciando run real — aws-credential-pivot")
    print(f"  entry:  {ENTRY_USER_ARN.split('/')[-1]}")
    print(f"  target: {TARGET_ROLE_ARN.split('/')[-1]}")
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
            synthetic_actor = (obs.get("details") or {}).get("synthetic_actor", "")
            granted_role = (obs.get("details") or {}).get("granted_role", "")
            extra = f" → synthetic={synthetic_actor}" if synthetic_actor else ""
            extra += f" → granted={granted_role.split('/')[-1]}" if granted_role else ""
            print(f"  step {i+1}: [{tool}] as {actor} → success={success}{extra}")
        flags = report.get("final_state", {}).get("flags", [])
        print(f"flags:         {flags}")


if __name__ == "__main__":
    main()
