from __future__ import annotations

from pathlib import Path

from operations.models import ProfileDefinition


REPO_ROOT = Path(__file__).resolve().parents[2]


def _real_path(*parts: str) -> Path:
    return REPO_ROOT.joinpath(*parts)


FOUNDATION_PROFILES: dict[str, ProfileDefinition] = {
    "aws-iam-s3": ProfileDefinition(
        name="aws-iam-s3",
        bundle="aws-foundation",
        description="IAM to S3 object access with real AWS evidence.",
        fixture_path=_real_path("terraform_local_lab", "rastro_local", "aws_role_choice_lab.local.json"),
        objective_path=_real_path("terraform_local_lab", "rastro_local", "objective_aws_role_choice.local.json"),
        scope_path=_real_path("terraform_local_lab", "rastro_local", "scope_aws_role_choice_openai_real.local.json"),
    ),
    "aws-iam-secrets": ProfileDefinition(
        name="aws-iam-secrets",
        bundle="aws-foundation",
        description="IAM to Secrets Manager secret access with real AWS evidence.",
        fixture_path=_real_path("terraform_local_lab", "rastro_local", "aws_secrets_backtracking_lab.local.json"),
        objective_path=_real_path("terraform_local_lab", "rastro_local", "objective_aws_secrets_backtracking.local.json"),
        scope_path=_real_path("terraform_local_lab", "rastro_local", "scope_aws_secrets_backtracking_openai.local.json"),
    ),
    "aws-iam-ssm": ProfileDefinition(
        name="aws-iam-ssm",
        bundle="aws-foundation",
        description="IAM to SSM Parameter Store access with real AWS evidence.",
        fixture_path=_real_path("terraform_local_lab", "rastro_local", "aws_ssm_backtracking_lab.local.json"),
        objective_path=_real_path("terraform_local_lab", "rastro_local", "objective_aws_ssm_backtracking.local.json"),
        scope_path=_real_path("terraform_local_lab", "rastro_local", "scope_aws_ssm_backtracking_openai.local.json"),
    ),
    "aws-iam-role-chaining": ProfileDefinition(
        name="aws-iam-role-chaining",
        bundle="aws-foundation",
        description="Two-step STS role chain to final S3 access with real AWS evidence.",
        fixture_path=_real_path("terraform_local_lab", "rastro_local", "aws_role_chaining_lab.local.json"),
        objective_path=_real_path("terraform_local_lab", "rastro_local", "objective_aws_role_chaining.local.json"),
        scope_path=_real_path("terraform_local_lab", "rastro_local", "scope_aws_role_chaining_openai.local.json"),
    ),
}


BUNDLES: dict[str, list[str]] = {
    "aws-foundation": list(FOUNDATION_PROFILES.keys()),
}


def get_profile(name: str) -> ProfileDefinition:
    return FOUNDATION_PROFILES[name]


def list_profiles() -> list[ProfileDefinition]:
    return list(FOUNDATION_PROFILES.values())


def resolve_bundle(name: str) -> list[ProfileDefinition]:
    return [get_profile(profile_name) for profile_name in BUNDLES[name]]
