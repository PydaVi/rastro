from __future__ import annotations

import json
from pathlib import Path

from core.domain import Scope
from operations.catalog import BUNDLES, FOUNDATION_PROFILES, get_profile, resolve_bundle
from operations.models import (
    AssessmentFinding,
    AssessmentResult,
    AuthorizationConfig,
    CampaignResult,
    ProfileDefinition,
    TargetConfig,
)


def load_target(path: Path) -> TargetConfig:
    return TargetConfig.model_validate_json(path.read_text())


def load_authorization(path: Path) -> AuthorizationConfig:
    return AuthorizationConfig.model_validate_json(path.read_text())


def validate_target(target: TargetConfig) -> list[str]:
    issues: list[str] = []
    if target.platform != "aws":
        issues.append("target.platform must be aws")
    if not target.accounts:
        issues.append("target.accounts must not be empty")
    if not target.allowed_regions:
        issues.append("target.allowed_regions must not be empty")
    if not target.entry_roles:
        issues.append("target.entry_roles must not be empty")
    return issues


def validate_profile_access(profile_name: str, authorization: AuthorizationConfig) -> None:
    if authorization.permitted_profiles and profile_name not in authorization.permitted_profiles:
        raise ValueError(f"profile {profile_name} is not permitted by authorization")
    if profile_name in authorization.excluded_profiles:
        raise ValueError(f"profile {profile_name} is excluded by authorization")


def build_campaign_scope(
    profile: ProfileDefinition,
    target: TargetConfig,
    authorization: AuthorizationConfig,
) -> Scope:
    scope = Scope.model_validate_json(profile.scope_path.read_text())
    data = scope.model_dump()
    data["aws_account_ids"] = target.accounts
    data["allowed_regions"] = target.allowed_regions
    data["authorized_by"] = authorization.authorized_by
    data["authorized_at"] = authorization.authorized_at
    data["authorization_document"] = authorization.authorization_document
    return Scope.model_validate(data)


def write_campaign_scope(
    profile: ProfileDefinition,
    target: TargetConfig,
    authorization: AuthorizationConfig,
    output_dir: Path,
) -> Path:
    scope = build_campaign_scope(profile, target, authorization)
    output_dir.mkdir(parents=True, exist_ok=True)
    scope_path = output_dir / f"{profile.name}.scope.json"
    scope_path.write_text(json.dumps(scope.model_dump(), indent=2))
    return scope_path


def list_available_profiles() -> list[ProfileDefinition]:
    return list(FOUNDATION_PROFILES.values())


def list_available_bundles() -> dict[str, list[str]]:
    return BUNDLES


def build_assessment_summary(campaigns: list[CampaignResult]) -> dict:
    total = len(campaigns)
    passed = sum(1 for campaign in campaigns if campaign.status == "passed")
    objective_not_met = sum(1 for campaign in campaigns if campaign.status == "objective_not_met")
    preflight_failed = sum(1 for campaign in campaigns if campaign.status == "preflight_failed")
    run_failed = sum(1 for campaign in campaigns if campaign.status == "run_failed")
    return {
        "campaigns_total": total,
        "campaigns_passed": passed,
        "campaigns_objective_not_met": objective_not_met,
        "campaigns_preflight_failed": preflight_failed,
        "campaigns_run_failed": run_failed,
        "assessment_ok": preflight_failed == 0 and run_failed == 0,
    }


def run_campaign(
    *,
    profile_name: str,
    target: TargetConfig,
    authorization: AuthorizationConfig,
    output_dir: Path,
    runner,
    max_steps: int | None = None,
    seed: int | None = None,
) -> CampaignResult:
    validate_profile_access(profile_name, authorization)
    profile = get_profile(profile_name)
    generated_scope_path = write_campaign_scope(profile, target, authorization, output_dir)
    try:
        result = runner(
            fixture_path=profile.fixture_path,
            objective_path=profile.objective_path,
            scope_path=generated_scope_path,
            output_dir=output_dir,
            max_steps=max_steps,
            seed=seed,
        )
    except Exception as exc:
        message = str(exc)
        status = "preflight_failed" if "preflight failed" in message.lower() else "run_failed"
        return CampaignResult(
            status=status,
            profile=profile_name,
            output_dir=output_dir,
            generated_scope=generated_scope_path,
            objective_met=False,
            preflight_ok=status != "preflight_failed",
            preflight_details={},
            error=message,
        )
    objective_met = result["objective_met"]
    preflight = result.get("preflight", {})
    return CampaignResult(
        status="passed" if objective_met else "objective_not_met",
        profile=profile_name,
        output_dir=output_dir,
        generated_scope=generated_scope_path,
        objective_met=objective_met,
        preflight_ok=preflight.get("ok", True),
        preflight_details=preflight.get("details", {}),
        report_json=result["report_json"],
        report_md=result["report_md"],
    )


def run_generated_campaign(
    *,
    plan: dict,
    target: TargetConfig,
    authorization: AuthorizationConfig,
    output_dir: Path,
    runner,
    max_steps: int | None = None,
    seed: int | None = None,
    profile_resolver=None,
) -> CampaignResult:
    profile_resolver = profile_resolver or get_profile
    profile_name = plan["profile"]
    validate_profile_access(profile_name, authorization)
    profile = _resolve_profile(profile_resolver, profile_name, plan)
    generated_scope_path = Path(plan["generated_scope"])
    generated_objective_path = Path(plan["generated_objective"])
    try:
        result = runner(
            fixture_path=profile.fixture_path,
            objective_path=generated_objective_path,
            scope_path=generated_scope_path,
            output_dir=output_dir,
            max_steps=max_steps,
            seed=seed,
        )
    except Exception as exc:
        message = str(exc)
        status = "preflight_failed" if "preflight failed" in message.lower() else "run_failed"
        return CampaignResult(
            status=status,
            profile=profile_name,
            output_dir=output_dir,
            generated_scope=generated_scope_path,
            objective_met=False,
            preflight_ok=status != "preflight_failed",
            preflight_details={},
            error=message,
        )
    objective_met = result["objective_met"]
    preflight = result.get("preflight", {})
    return CampaignResult(
        status="passed" if objective_met else "objective_not_met",
        profile=profile_name,
        output_dir=output_dir,
        generated_scope=generated_scope_path,
        objective_met=objective_met,
        preflight_ok=preflight.get("ok", True),
        preflight_details=preflight.get("details", {}),
        report_json=result["report_json"],
        report_md=result["report_md"],
    )


def run_assessment(
    *,
    bundle_name: str,
    target: TargetConfig,
    authorization: AuthorizationConfig,
    output_dir: Path,
    runner,
    max_steps: int | None = None,
    seed: int | None = None,
) -> AssessmentResult:
    campaigns: list[CampaignResult] = []
    for profile in resolve_bundle(bundle_name):
        campaign_output = output_dir / profile.name
        campaigns.append(
            run_campaign(
                profile_name=profile.name,
                target=target,
                authorization=authorization,
                output_dir=campaign_output,
                runner=runner,
                max_steps=max_steps,
                seed=seed,
            )
        )
    return AssessmentResult(
        bundle=bundle_name,
        target=target.name,
        summary=build_assessment_summary(campaigns),
        campaigns=campaigns,
    )


def run_discovery_driven_assessment(
    *,
    bundle_name: str,
    target: TargetConfig,
    authorization: AuthorizationConfig,
    output_dir: Path,
    runner,
    max_steps: int | None = None,
    seed: int | None = None,
    max_candidates_per_profile: int = 5,
    max_plans_per_profile: int = 1,
    dedupe_resource_targets: bool = False,
    discovery_runner=None,
    target_selector=None,
    campaign_synthesizer=None,
    profile_resolver=None,
) -> AssessmentResult:
    from operations.campaign_synthesis import synthesize_foundation_campaigns
    from operations.discovery import run_foundation_discovery
    from operations.target_selection import select_foundation_targets

    discovery_runner = discovery_runner or run_foundation_discovery
    target_selector = target_selector or select_foundation_targets
    campaign_synthesizer = campaign_synthesizer or synthesize_foundation_campaigns
    profile_resolver = profile_resolver or get_profile

    discovery_dir = output_dir / "discovery"
    candidates_dir = output_dir / "target-selection"
    campaign_plan_dir = output_dir / "campaign-synthesis"

    discovery_json, discovery_md, discovery_snapshot = discovery_runner(
        bundle_name=bundle_name,
        target=target,
        authorization=authorization,
        output_dir=discovery_dir,
    )
    candidates_json, candidates_md, candidates_payload = target_selector(
        discovery_snapshot=discovery_snapshot,
        output_dir=candidates_dir,
        max_candidates_per_profile=max_candidates_per_profile,
        bundle_name=bundle_name,
    )
    campaign_plan_json, campaign_plan_md, campaign_plan_payload = campaign_synthesizer(
        candidates_payload=candidates_payload,
        target=target,
        authorization=authorization,
        output_dir=campaign_plan_dir,
        max_plans_per_profile=max_plans_per_profile,
        dedupe_resource_targets=dedupe_resource_targets,
        profile_resolver=profile_resolver,
    )

    campaigns: list[CampaignResult] = []
    for plan in campaign_plan_payload["plans"]:
        campaign_output = output_dir / "campaigns" / plan["profile"]
        campaigns.append(
            run_generated_campaign(
                plan=plan,
                target=target,
                authorization=authorization,
                output_dir=campaign_output,
                runner=runner,
                max_steps=max_steps,
                seed=seed,
                profile_resolver=profile_resolver,
            )
        )

    return AssessmentResult(
        bundle=bundle_name,
        target=target.name,
        summary=build_assessment_summary(campaigns),
        artifacts={
            "discovery_json": str(discovery_json),
            "discovery_md": str(discovery_md),
            "target_candidates_json": str(candidates_json),
            "target_candidates_md": str(candidates_md),
            "campaign_plan_json": str(campaign_plan_json),
            "campaign_plan_md": str(campaign_plan_md),
        },
        campaigns=campaigns,
    )


def _resolve_profile(profile_resolver, profile_name: str, plan: dict):
    try:
        return profile_resolver(profile_name, plan)
    except TypeError:
        return profile_resolver(profile_name)


def write_assessment_summary(result: AssessmentResult, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "assessment.json"
    md_path = output_dir / "assessment.md"
    if not result.summary:
        result.summary = build_assessment_summary(result.campaigns)
    findings_json_path, findings_md_path = write_assessment_findings(result, output_dir)
    result.artifacts.setdefault("assessment_findings_json", str(findings_json_path))
    result.artifacts.setdefault("assessment_findings_md", str(findings_md_path))
    json_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2))
    lines = [
        "# Assessment Summary",
        "",
        f"- Bundle: {result.bundle}",
        f"- Target: {result.target}",
        f"- Assessment OK: {result.summary.get('assessment_ok', True)}",
        f"- Campaigns total: {result.summary.get('campaigns_total', len(result.campaigns))}",
        f"- Campaigns passed: {result.summary.get('campaigns_passed', 0)}",
        f"- Campaigns objective not met: {result.summary.get('campaigns_objective_not_met', 0)}",
        f"- Campaigns preflight failed: {result.summary.get('campaigns_preflight_failed', 0)}",
        f"- Campaigns run failed: {result.summary.get('campaigns_run_failed', 0)}",
        "",
        "## Artifacts",
        "",
    ]
    for name, value in result.artifacts.items():
        lines.append(f"- {name}: {value}")
    lines.extend(["", "## Campaigns", ""])
    for campaign in result.campaigns:
        lines.append(
            f"- {campaign.profile}: status={campaign.status} objective_met={campaign.objective_met} preflight_ok={campaign.preflight_ok}"
        )
        lines.append(f"  scope={campaign.generated_scope}")
        if campaign.report_md:
            lines.append(f"  report={campaign.report_md}")
        lines.append(f"  output={campaign.output_dir}")
        if campaign.error:
            lines.append(f"  error={campaign.error}")
    md_path.write_text("\n".join(lines) + "\n")
    return json_path, md_path


def write_assessment_findings(result: AssessmentResult, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    findings = build_assessment_findings(result)
    result.findings = findings
    json_path = output_dir / "assessment_findings.json"
    md_path = output_dir / "assessment_findings.md"
    payload = {
        "bundle": result.bundle,
        "target": result.target,
        "summary": {
            "findings_total": len(findings),
            "validated_findings": len(findings),
            "by_profile": _count_findings_by_profile(findings),
        },
        "findings": [finding.model_dump(mode="json") for finding in findings],
    }
    json_path.write_text(json.dumps(payload, indent=2))
    md_path.write_text(_render_assessment_findings_markdown(payload))
    return json_path, md_path


def build_assessment_findings(result: AssessmentResult) -> list[AssessmentFinding]:
    findings: list[AssessmentFinding] = []
    for campaign in result.campaigns:
        if campaign.status != "passed" or not campaign.report_json or not campaign.report_json.exists():
            continue
        report = json.loads(campaign.report_json.read_text())
        executive_summary = report.get("executive_summary", {})
        objective = report.get("objective", {})
        target_resource = executive_summary.get("final_resource") or objective.get("target") or "-"
        path_summary = _build_path_summary(report)
        findings.append(
            AssessmentFinding(
                id=f"finding:{campaign.profile}:{_slugify(target_resource)}",
                title=_build_finding_title(campaign.profile, target_resource),
                profile=campaign.profile,
                severity=_severity_for_profile(campaign.profile),
                confidence="high" if campaign.objective_met else "medium",
                target_resource=target_resource,
                entry_point=executive_summary.get("initial_identity"),
                path_summary=path_summary,
                services_involved=report.get("execution_policy", {}).get("allowed_services", []),
                evidence_summary=_build_evidence_summary(report),
                mitre_techniques=[item.get("mitre_id") for item in report.get("mitre_techniques", []) if item.get("mitre_id")],
            )
        )
    return findings


def _build_path_summary(report: dict) -> str:
    chain: list[str] = []
    for step in report.get("steps", []):
        action = step.get("action", {})
        actor = action.get("actor")
        target = action.get("target")
        if actor:
            chain.append(_short_ref(actor))
        if target:
            chain.append(_short_ref(target))
    deduped: list[str] = []
    for item in chain:
        if not deduped or deduped[-1] != item:
            deduped.append(item)
    return " -> ".join(deduped)


def _build_evidence_summary(report: dict) -> str:
    executive_summary = report.get("executive_summary", {})
    proof = executive_summary.get("proof")
    if proof:
        return f"Validated with proof: {proof}"
    final_resource = executive_summary.get("final_resource")
    if final_resource:
        return f"Validated access to {final_resource}"
    return "Validated path without exported proof payload."


def _build_finding_title(profile: str, target_resource: str) -> str:
    labels = {
        "aws-iam-s3": "IAM -> S3 exposure",
        "aws-iam-secrets": "IAM -> Secrets exposure",
        "aws-iam-ssm": "IAM -> SSM exposure",
        "aws-iam-role-chaining": "IAM role chaining exposure",
    }
    return f"{labels.get(profile, profile)} to {target_resource}"


def _severity_for_profile(profile: str) -> str:
    severities = {
        "aws-iam-s3": "high",
        "aws-iam-secrets": "critical",
        "aws-iam-ssm": "high",
        "aws-iam-role-chaining": "high",
    }
    return severities.get(profile, "medium")


def _count_findings_by_profile(findings: list[AssessmentFinding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.profile] = counts.get(finding.profile, 0) + 1
    return counts


def _render_assessment_findings_markdown(payload: dict) -> str:
    lines = [
        "# Assessment Findings",
        "",
        f"- Bundle: {payload['bundle']}",
        f"- Target: {payload['target']}",
        f"- Findings total: {payload['summary']['findings_total']}",
        "",
        "## Findings",
        "",
    ]
    for finding in payload["findings"]:
        lines.append(f"### {finding['title']}")
        lines.append("")
        lines.append(f"- Profile: {finding['profile']}")
        lines.append(f"- Severity: {finding['severity']}")
        lines.append(f"- Confidence: {finding['confidence']}")
        lines.append(f"- Target resource: {finding['target_resource']}")
        lines.append(f"- Entry point: {finding.get('entry_point') or '-'}")
        lines.append(f"- Path: {finding['path_summary'] or '-'}")
        lines.append(f"- Evidence: {finding['evidence_summary']}")
        lines.append(f"- MITRE: {', '.join(finding['mitre_techniques']) if finding['mitre_techniques'] else '-'}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _short_ref(value: str) -> str:
    if ":role/" in value:
        return value.rsplit("/", 1)[-1]
    if ":user/" in value:
        return value.rsplit("/", 1)[-1]
    if value.startswith("arn:aws:s3:::"):
        return value.replace("arn:aws:s3:::", "s3://")
    if ":secret:" in value:
        return value.split(":secret:", 1)[1]
    if ":parameter/" in value:
        return value.split(":parameter/", 1)[1]
    return value


def _slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
