from __future__ import annotations

from pathlib import Path

from operations.models import ProfileDefinition


REPO_ROOT = Path(__file__).resolve().parents[2]


def _path(*parts: str) -> Path:
    return REPO_ROOT.joinpath(*parts)


INTERNAL_DATA_PLATFORM_SYNTHETIC_PROFILES: dict[str, ProfileDefinition] = {
    "aws-iam-s3": ProfileDefinition(
        name="aws-iam-s3",
        bundle="aws-foundation-idp-synthetic",
        description="Synthetic IAM to S3 for internal-data-platform.",
        fixture_path=_path("fixtures", "internal_data_platform_iam_s3_lab.json"),
        objective_path=_path("examples", "objective_internal_data_platform_iam_s3.json"),
        scope_path=_path("examples", "scope_internal_data_platform_iam_s3.json"),
    ),
    "aws-iam-secrets": ProfileDefinition(
        name="aws-iam-secrets",
        bundle="aws-foundation-idp-synthetic",
        description="Synthetic IAM to Secrets for internal-data-platform.",
        fixture_path=_path("fixtures", "internal_data_platform_iam_secrets_lab.json"),
        objective_path=_path("examples", "objective_internal_data_platform_iam_secrets.json"),
        scope_path=_path("examples", "scope_internal_data_platform_iam_secrets.json"),
    ),
    "aws-iam-ssm": ProfileDefinition(
        name="aws-iam-ssm",
        bundle="aws-foundation-idp-synthetic",
        description="Synthetic IAM to SSM for internal-data-platform.",
        fixture_path=_path("fixtures", "internal_data_platform_iam_ssm_lab.json"),
        objective_path=_path("examples", "objective_internal_data_platform_iam_ssm.json"),
        scope_path=_path("examples", "scope_internal_data_platform_iam_ssm.json"),
    ),
    "aws-iam-role-chaining": ProfileDefinition(
        name="aws-iam-role-chaining",
        bundle="aws-foundation-idp-synthetic",
        description="Synthetic role chaining for internal-data-platform.",
        fixture_path=_path("fixtures", "internal_data_platform_iam_role_chaining_lab.json"),
        objective_path=_path("examples", "objective_internal_data_platform_iam_role_chaining.json"),
        scope_path=_path("examples", "scope_internal_data_platform_iam_role_chaining.json"),
    ),
}


def get_synthetic_profile(profile_set: str, family: str) -> ProfileDefinition:
    if profile_set != "internal-data-platform":
        raise KeyError(f"unknown synthetic profile set: {profile_set}")
    return INTERNAL_DATA_PLATFORM_SYNTHETIC_PROFILES[family]
