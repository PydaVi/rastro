"""Bloco 15 — auditor offline independente.

Reabre os artefatos de um assessment já rodado (assessment.json, report.json +
audit.jsonl por campanha, assessment_findings.json, discovery.json quando
presente) e reverifica as alegações sem confiar no self-report do próprio
run — mesma disciplina do PolicyEvaluator (Bloco 12) e do verify_remediation
(Bloco 14): código determinístico revalida, nunca aceita "porque o relatório
disse". Zero chamada AWS: opera inteiramente sobre arquivos já no disco.

Quatro checagens, uma por campanha:
  1. scope_respected — nenhum step usou um serviço fora de execution_policy
  2. objective_claim_grounded — se objective_met=True, existe um step cujo
     action+observation realmente satisfaz o success_criteria.mode declarado
  3. rollback_attempted_when_needed — toda mutação bem-sucedida (Attach/
     CreatePolicyVersion/CreateAccessKey) tem um rollback_executed correspondente
  4. evaluation_tier_consistent — recomputa o PRIMEIRO passo via PolicyEvaluator
     a partir do discovery.json e compara com o evaluation_tier reivindicado
     no finding (quando discovery.json e o finding correspondente existem)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from core.policy_evaluator import evaluate_effective_access

# Tools que mutam estado real e por isso exigem rollback registrado.
_MUTATING_TOOLS = frozenset({
    "iam_attach_role_policy_mutate",
    "iam_create_policy_version_mutate",
    "iam_create_access_key",
})

# tool -> action IAM concreta, o inverso do mapeamento que
# CapabilityGraph._step_tool usa pra ir de action pra tool (Bloco 10).
_ACTION_BY_TOOL: dict[str, str] = {
    "iam_passrole": "sts:AssumeRole",
    "iam_create_access_key": "iam:CreateAccessKey",
    "iam_attach_role_policy_mutate": "iam:AttachRolePolicy",
    "iam_create_policy_version_mutate": "iam:CreatePolicyVersion",
    "secretsmanager_read_secret": "secretsmanager:GetSecretValue",
    "ssm_read_parameter": "ssm:GetParameter",
    "s3_read_sensitive": "s3:GetObject",
}


@dataclass(frozen=True)
class CampaignAuditResult:
    profile: str
    output_dir: str
    scope_respected: bool
    out_of_scope_steps: list[dict] = field(default_factory=list)
    # None = objective_met era False, nada pra checar aqui.
    objective_claim_grounded: bool | None = None
    rollback_attempted_when_needed: bool = True
    missing_rollback_tools: list[str] = field(default_factory=list)
    evaluation_tier_claimed: str | None = None
    evaluation_tier_reproduced: str | None = None
    # None = não foi possível recomputar (sem discovery.json, sem finding
    # correspondente, ou primeiro passo não mapeável) — nunca inferido.
    evaluation_tier_consistent: bool | None = None

    @property
    def passed(self) -> bool:
        return (
            self.scope_respected
            and self.objective_claim_grounded is not False
            and self.rollback_attempted_when_needed
            and self.evaluation_tier_consistent is not False
        )


@dataclass(frozen=True)
class AuditReport:
    output_dir: str
    campaigns: list[CampaignAuditResult]

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.campaigns)


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _check_scope(report: dict) -> tuple[bool, list[dict]]:
    allowed_services = set(report.get("execution_policy", {}).get("allowed_services", []))
    out_of_scope = []
    for step in report.get("steps", []):
        service = step.get("action", {}).get("parameters", {}).get("service")
        if service and allowed_services and service not in allowed_services:
            out_of_scope.append(step)
    return (len(out_of_scope) == 0, out_of_scope)


def _check_objective_claim(report: dict) -> bool | None:
    if not report.get("objective_met"):
        return None
    mode = report.get("objective", {}).get("success_criteria", {}).get("mode")
    target = report.get("objective", {}).get("target")
    required_tool = report.get("objective", {}).get("success_criteria", {}).get("required_tool")

    for step in report.get("steps", []):
        action = step.get("action", {})
        observation = step.get("observation", {})
        if not observation.get("success"):
            continue
        if mode == "assume_role_proved":
            if action.get("action_type") == "assume_role" and action.get("target") == target:
                return True
        elif mode in ("policy_mutation_proved", "policy_probe_proved"):
            if required_tool and action.get("tool") == required_tool:
                return True
        elif mode in ("access_proved", "target_observed"):
            if action.get("action_type") == "access_resource" and action.get("target") == target:
                return True
    return False


def _check_rollback(report: dict, audit_events: list[dict]) -> tuple[bool, list[str]]:
    mutated_tools = {
        step["action"]["tool"]
        for step in report.get("steps", [])
        if step.get("observation", {}).get("success") and step.get("action", {}).get("tool") in _MUTATING_TOOLS
    }
    if not mutated_tools:
        return True, []
    has_rollback_event = any(e.get("event") == "rollback_executed" for e in audit_events)
    if has_rollback_event:
        return True, []
    return False, sorted(mutated_tools)


def _read_audit_events(audit_path: Path) -> list[dict]:
    if not audit_path.exists():
        return []
    events = []
    for line in audit_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


def _find_finding_for_campaign(findings: list[dict], profile: str, report: dict) -> dict | None:
    target = report.get("objective", {}).get("target")
    for finding in findings:
        if finding.get("profile") == profile and finding.get("target_resource") == target:
            return finding
    return None


def _reproduce_evaluation_tier(
    report: dict,
    discovery_snapshot: dict,
) -> str | None:
    """Recomputa o tier do PRIMEIRO passo do report, igual
    CapabilityGraph._compute_evaluation_tier (Bloco 12) faz antes da execução —
    mas aqui a partir do que REALMENTE rodou, não da hipótese original."""
    steps = report.get("steps", [])
    if not steps:
        return None
    first_action = steps[0].get("action", {})
    tool = first_action.get("tool")
    action_name = _ACTION_BY_TOOL.get(tool)
    if action_name is None:
        return None
    actor = first_action.get("actor")
    target = first_action.get("target")
    if not actor or not target:
        return None

    principal = next(
        (r for r in discovery_snapshot.get("resources", []) if r.get("identifier") == actor),
        None,
    )
    if principal is None:
        return None
    meta = principal.get("metadata") or {}
    governance = discovery_snapshot.get("governance") or {}

    result = evaluate_effective_access(
        identity_statements=meta.get("policy_permissions", []),
        action=action_name,
        resource_arn=target,
        boundary_statements=meta.get("boundary_policy_permissions"),
        scp_statements=governance.get("scp_policies"),
    )
    if result.allowed and result.certain:
        return "evaluated"
    return "structural"


def audit_campaign(
    *,
    profile: str,
    report: dict,
    audit_events: list[dict],
    findings: list[dict] | None,
    discovery_snapshot: dict | None,
    output_dir: str,
) -> CampaignAuditResult:
    scope_respected, out_of_scope_steps = _check_scope(report)
    objective_claim_grounded = _check_objective_claim(report)
    rollback_ok, missing_rollback = _check_rollback(report, audit_events)

    evaluation_tier_claimed = None
    evaluation_tier_reproduced = None
    evaluation_tier_consistent = None
    if findings is not None:
        finding = _find_finding_for_campaign(findings, profile, report)
        if finding is not None:
            evaluation_tier_claimed = finding.get("evaluation_tier")
            if discovery_snapshot is not None:
                evaluation_tier_reproduced = _reproduce_evaluation_tier(report, discovery_snapshot)
                if evaluation_tier_reproduced is not None and evaluation_tier_claimed is not None:
                    evaluation_tier_consistent = evaluation_tier_reproduced == evaluation_tier_claimed

    return CampaignAuditResult(
        profile=profile,
        output_dir=output_dir,
        scope_respected=scope_respected,
        out_of_scope_steps=out_of_scope_steps,
        objective_claim_grounded=objective_claim_grounded,
        rollback_attempted_when_needed=rollback_ok,
        missing_rollback_tools=missing_rollback,
        evaluation_tier_claimed=evaluation_tier_claimed,
        evaluation_tier_reproduced=evaluation_tier_reproduced,
        evaluation_tier_consistent=evaluation_tier_consistent,
    )


def audit_assessment(output_dir: Path) -> AuditReport:
    """Ponto de entrada: audita um diretório de output completo de assessment."""
    assessment = _load_json(output_dir / "assessment.json")
    if assessment is None:
        raise ValueError(f"assessment.json não encontrado em {output_dir}")

    findings_payload = _load_json(output_dir / "assessment_findings.json")
    findings = findings_payload.get("findings") if findings_payload else None
    discovery_snapshot = _load_json(output_dir / "discovery" / "discovery.json")

    results: list[CampaignAuditResult] = []
    for campaign in assessment.get("campaigns", []):
        report_path_str = campaign.get("report_json")
        if not report_path_str:
            continue  # skipped/preflight_failed/run_failed sem report — nada pra auditar
        report_path = Path(report_path_str)
        report = _load_json(report_path)
        if report is None:
            continue
        audit_path = report_path.parent / "audit.jsonl"
        audit_events = _read_audit_events(audit_path)

        results.append(
            audit_campaign(
                profile=campaign["profile"],
                report=report,
                audit_events=audit_events,
                findings=findings,
                discovery_snapshot=discovery_snapshot,
                output_dir=str(report_path.parent),
            )
        )

    return AuditReport(output_dir=str(output_dir), campaigns=results)
