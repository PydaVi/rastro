from __future__ import annotations

import json
from pathlib import Path

from core.domain import Scope
from operations.catalog import BUNDLES, FOUNDATION_PROFILES, get_profile, resolve_bundle
from operations.models import (
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
    result = runner(
        fixture_path=profile.fixture_path,
        objective_path=profile.objective_path,
        scope_path=generated_scope_path,
        output_dir=output_dir,
        max_steps=max_steps,
        seed=seed,
    )
    return CampaignResult(
        profile=profile_name,
        output_dir=output_dir,
        objective_met=result["objective_met"],
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
    return AssessmentResult(bundle=bundle_name, target=target.name, campaigns=campaigns)


def write_assessment_summary(result: AssessmentResult, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "assessment.json"
    md_path = output_dir / "assessment.md"
    json_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2))
    lines = [
        "# Assessment Summary",
        "",
        f"- Bundle: {result.bundle}",
        f"- Target: {result.target}",
        "",
        "## Campaigns",
        "",
    ]
    for campaign in result.campaigns:
        lines.append(f"- {campaign.profile}: objective_met={campaign.objective_met} output={campaign.output_dir}")
    md_path.write_text("\n".join(lines) + "\n")
    return json_path, md_path
