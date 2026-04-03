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


SERVERLESS_BUSINESS_APP_SYNTHETIC_PROFILES: dict[str, ProfileDefinition] = {
    "aws-iam-s3": ProfileDefinition(
        name="aws-iam-s3",
        bundle="aws-foundation-sba-synthetic",
        description="Synthetic IAM to S3 for serverless-business-app.",
        fixture_path=_path("fixtures", "serverless_business_app_iam_s3_lab.json"),
        objective_path=_path("examples", "objective_serverless_business_app_iam_s3.json"),
        scope_path=_path("examples", "scope_serverless_business_app_iam_s3.json"),
    ),
    "aws-iam-secrets": ProfileDefinition(
        name="aws-iam-secrets",
        bundle="aws-foundation-sba-synthetic",
        description="Synthetic IAM to Secrets for serverless-business-app.",
        fixture_path=_path("fixtures", "serverless_business_app_iam_secrets_lab.json"),
        objective_path=_path("examples", "objective_serverless_business_app_iam_secrets.json"),
        scope_path=_path("examples", "scope_serverless_business_app_iam_secrets.json"),
    ),
    "aws-iam-ssm": ProfileDefinition(
        name="aws-iam-ssm",
        bundle="aws-foundation-sba-synthetic",
        description="Synthetic IAM to SSM for serverless-business-app.",
        fixture_path=_path("fixtures", "serverless_business_app_iam_ssm_lab.json"),
        objective_path=_path("examples", "objective_serverless_business_app_iam_ssm.json"),
        scope_path=_path("examples", "scope_serverless_business_app_iam_ssm.json"),
    ),
    "aws-iam-role-chaining": ProfileDefinition(
        name="aws-iam-role-chaining",
        bundle="aws-foundation-sba-synthetic",
        description="Synthetic role chaining for serverless-business-app.",
        fixture_path=_path("fixtures", "serverless_business_app_iam_role_chaining_lab.json"),
        objective_path=_path("examples", "objective_serverless_business_app_iam_role_chaining.json"),
        scope_path=_path("examples", "scope_serverless_business_app_iam_role_chaining.json"),
    ),
    "aws-iam-lambda-data": ProfileDefinition(
        name="aws-iam-lambda-data",
        bundle="aws-advanced-sba-synthetic",
        description="Synthetic IAM to Lambda to data for serverless-business-app.",
        fixture_path=_path("fixtures", "serverless_business_app_iam_lambda_data_lab.json"),
        objective_path=_path("examples", "objective_serverless_business_app_iam_lambda_data.json"),
        scope_path=_path("examples", "scope_serverless_business_app_iam_lambda_data.json"),
    ),
    "aws-iam-kms-data": ProfileDefinition(
        name="aws-iam-kms-data",
        bundle="aws-advanced-sba-synthetic",
        description="Synthetic IAM to KMS to data for serverless-business-app.",
        fixture_path=_path("fixtures", "serverless_business_app_iam_kms_data_lab.json"),
        objective_path=_path("examples", "objective_serverless_business_app_iam_kms_data.json"),
        scope_path=_path("examples", "scope_serverless_business_app_iam_kms_data.json"),
    ),
}


COMPUTE_PIVOT_APP_SYNTHETIC_PROFILES: dict[str, ProfileDefinition] = {
    "aws-iam-s3": ProfileDefinition(
        name="aws-iam-s3",
        bundle="aws-foundation-cpa-synthetic",
        description="Synthetic IAM to S3 for compute-pivot-app.",
        fixture_path=_path("fixtures", "compute_pivot_app_iam_s3_lab.json"),
        objective_path=_path("examples", "objective_compute_pivot_app_iam_s3.json"),
        scope_path=_path("examples", "scope_compute_pivot_app_iam_s3.json"),
    ),
    "aws-iam-secrets": ProfileDefinition(
        name="aws-iam-secrets",
        bundle="aws-foundation-cpa-synthetic",
        description="Synthetic IAM to Secrets for compute-pivot-app.",
        fixture_path=_path("fixtures", "compute_pivot_app_iam_secrets_lab.json"),
        objective_path=_path("examples", "objective_compute_pivot_app_iam_secrets.json"),
        scope_path=_path("examples", "scope_compute_pivot_app_iam_secrets.json"),
    ),
    "aws-iam-ssm": ProfileDefinition(
        name="aws-iam-ssm",
        bundle="aws-foundation-cpa-synthetic",
        description="Synthetic IAM to SSM for compute-pivot-app.",
        fixture_path=_path("fixtures", "compute_pivot_app_iam_ssm_lab.json"),
        objective_path=_path("examples", "objective_compute_pivot_app_iam_ssm.json"),
        scope_path=_path("examples", "scope_compute_pivot_app_iam_ssm.json"),
    ),
    "aws-iam-role-chaining": ProfileDefinition(
        name="aws-iam-role-chaining",
        bundle="aws-foundation-cpa-synthetic",
        description="Synthetic role chaining for compute-pivot-app.",
        fixture_path=_path("fixtures", "compute_pivot_app_iam_role_chaining_lab.json"),
        objective_path=_path("examples", "objective_compute_pivot_app_iam_role_chaining.json"),
        scope_path=_path("examples", "scope_compute_pivot_app_iam_role_chaining.json"),
    ),
    "aws-iam-compute-iam": ProfileDefinition(
        name="aws-iam-compute-iam",
        bundle="aws-advanced-cpa-synthetic",
        description="Synthetic IAM to Compute to IAM pivot for compute-pivot-app.",
        fixture_path=_path("fixtures", "compute_pivot_app_iam_compute_iam_lab.json"),
        objective_path=_path("examples", "objective_compute_pivot_app_iam_compute_iam.json"),
        scope_path=_path("examples", "scope_compute_pivot_app_iam_compute_iam.json"),
    ),
    "aws-external-entry-data": ProfileDefinition(
        name="aws-external-entry-data",
        bundle="aws-advanced-cpa-synthetic",
        description="Synthetic external entry to IAM to data for compute-pivot-app.",
        fixture_path=_path("fixtures", "compute_pivot_app_external_entry_lab.json"),
        objective_path=_path("examples", "objective_compute_pivot_app_external_entry.json"),
        scope_path=_path("examples", "scope_compute_pivot_app_external_entry.json"),
    ),
    "aws-cross-account-data": ProfileDefinition(
        name="aws-cross-account-data",
        bundle="aws-enterprise-cpa-synthetic",
        description="Synthetic cross-account path for compute-pivot-app.",
        fixture_path=_path("fixtures", "compute_pivot_app_cross_account_lab.json"),
        objective_path=_path("examples", "objective_compute_pivot_app_cross_account.json"),
        scope_path=_path("examples", "scope_compute_pivot_app_cross_account.json"),
    ),
    "aws-multi-step-data": ProfileDefinition(
        name="aws-multi-step-data",
        bundle="aws-enterprise-cpa-synthetic",
        description="Synthetic multi-step chain for compute-pivot-app.",
        fixture_path=_path("fixtures", "compute_pivot_app_multi_step_lab.json"),
        objective_path=_path("examples", "objective_compute_pivot_app_multi_step.json"),
        scope_path=_path("examples", "scope_compute_pivot_app_multi_step.json"),
    ),
}


MIXED_GENERALIZATION_SYNTHETIC_PROFILES: dict[str, ProfileDefinition] = {
    "aws-iam-s3": ProfileDefinition(
        name="aws-iam-s3",
        bundle="aws-enterprise-mixed-synthetic",
        description="Synthetic IAM to S3 for mixed-generalization benchmark.",
        fixture_path=_path("fixtures", "mixed_generalization_iam_s3_lab.json"),
        objective_path=_path("examples", "objective_compute_pivot_app_iam_s3.json"),
        scope_path=_path("examples", "scope_compute_pivot_app_iam_s3.json"),
    ),
    "aws-iam-secrets": ProfileDefinition(
        name="aws-iam-secrets",
        bundle="aws-enterprise-mixed-synthetic",
        description="Synthetic IAM to Secrets for mixed-generalization benchmark.",
        fixture_path=_path("fixtures", "serverless_business_app_iam_secrets_lab.json"),
        objective_path=_path("examples", "objective_serverless_business_app_iam_secrets.json"),
        scope_path=_path("examples", "scope_serverless_business_app_iam_secrets.json"),
    ),
    "aws-iam-ssm": ProfileDefinition(
        name="aws-iam-ssm",
        bundle="aws-enterprise-mixed-synthetic",
        description="Synthetic IAM to SSM for mixed-generalization benchmark.",
        fixture_path=_path("fixtures", "serverless_business_app_iam_ssm_lab.json"),
        objective_path=_path("examples", "objective_serverless_business_app_iam_ssm.json"),
        scope_path=_path("examples", "scope_serverless_business_app_iam_ssm.json"),
    ),
    "aws-iam-role-chaining": ProfileDefinition(
        name="aws-iam-role-chaining",
        bundle="aws-enterprise-mixed-synthetic",
        description="Synthetic role chaining for mixed-generalization benchmark.",
        fixture_path=_path("fixtures", "serverless_business_app_iam_role_chaining_lab.json"),
        objective_path=_path("examples", "objective_serverless_business_app_iam_role_chaining.json"),
        scope_path=_path("examples", "scope_serverless_business_app_iam_role_chaining.json"),
    ),
}


def get_synthetic_profile(profile_set: str, family: str) -> ProfileDefinition:
    if profile_set == "internal-data-platform":
        return INTERNAL_DATA_PLATFORM_SYNTHETIC_PROFILES[family]
    if profile_set == "serverless-business-app":
        return SERVERLESS_BUSINESS_APP_SYNTHETIC_PROFILES[family]
    if profile_set == "compute-pivot-app":
        return COMPUTE_PIVOT_APP_SYNTHETIC_PROFILES[family]
    raise KeyError(f"unknown synthetic profile set: {profile_set}")


def get_mixed_synthetic_profile(family: str, candidate_or_plan: dict | None = None) -> ProfileDefinition:
    if family in MIXED_GENERALIZATION_SYNTHETIC_PROFILES:
        return MIXED_GENERALIZATION_SYNTHETIC_PROFILES[family]

    resource_arn = ""
    if candidate_or_plan:
        resource_arn = candidate_or_plan.get("resource_arn", "")

    serverless_only = {"aws-iam-lambda-data", "aws-iam-kms-data"}
    if family in serverless_only:
        return SERVERLESS_BUSINESS_APP_SYNTHETIC_PROFILES[family]

    if family in {"aws-iam-s3", "aws-iam-secrets", "aws-iam-ssm"}:
        if ":210987654321:" in resource_arn:
            return COMPUTE_PIVOT_APP_SYNTHETIC_PROFILES[family]
        if "mixed-payroll-data-prod" in resource_arn:
            return COMPUTE_PIVOT_APP_SYNTHETIC_PROFILES[family]
        return COMPUTE_PIVOT_APP_SYNTHETIC_PROFILES[family]

    if family in {
        "aws-iam-role-chaining",
        "aws-iam-compute-iam",
        "aws-external-entry-data",
        "aws-cross-account-data",
        "aws-multi-step-data",
    }:
        return COMPUTE_PIVOT_APP_SYNTHETIC_PROFILES[family]

    return COMPUTE_PIVOT_APP_SYNTHETIC_PROFILES[family]
