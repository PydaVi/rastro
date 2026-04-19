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
        discovery_ssm_prefixes=["/prod", "/app", "/finance", "/shared"],
    ),
    "aws-iam-secrets": ProfileDefinition(
        name="aws-iam-secrets",
        bundle="aws-foundation",
        description="IAM to Secrets Manager secret access with real AWS evidence.",
        fixture_path=_real_path("terraform_local_lab", "rastro_local", "aws_secrets_backtracking_lab.local.json"),
        objective_path=_real_path("terraform_local_lab", "rastro_local", "objective_aws_secrets_backtracking.local.json"),
        scope_path=_real_path("terraform_local_lab", "rastro_local", "scope_aws_secrets_backtracking_openai.local.json"),
        discovery_ssm_prefixes=["/prod", "/app", "/finance", "/shared"],
    ),
    "aws-iam-ssm": ProfileDefinition(
        name="aws-iam-ssm",
        bundle="aws-foundation",
        description="IAM to SSM Parameter Store access with real AWS evidence.",
        fixture_path=_real_path("terraform_local_lab", "rastro_local", "aws_ssm_backtracking_lab.local.json"),
        objective_path=_real_path("terraform_local_lab", "rastro_local", "objective_aws_ssm_backtracking.local.json"),
        scope_path=_real_path("terraform_local_lab", "rastro_local", "scope_aws_ssm_backtracking_openai.local.json"),
        discovery_ssm_prefixes=["/prod", "/app", "/finance", "/shared"],
    ),
    "aws-iam-role-chaining": ProfileDefinition(
        name="aws-iam-role-chaining",
        bundle="aws-foundation",
        description="Two-step STS role chain to final S3 access with real AWS evidence.",
        fixture_path=_real_path("terraform_local_lab", "rastro_local", "aws_role_chaining_lab.local.json"),
        objective_path=_real_path("terraform_local_lab", "rastro_local", "objective_aws_role_chaining.local.json"),
        scope_path=_real_path("terraform_local_lab", "rastro_local", "scope_aws_role_chaining_openai.local.json"),
        discovery_ssm_prefixes=["/prod", "/app", "/finance", "/shared"],
    ),
    "aws-iam-create-policy-version-privesc": ProfileDefinition(
        name="aws-iam-create-policy-version-privesc",
        bundle="aws-iam-heavy",
        description="IAM privilege-escalation opportunity via CreatePolicyVersion or SetDefaultPolicyVersion.",
        fixture_path=_real_path("terraform_local_lab", "rastro_local", "aws_role_chaining_lab.local.json"),
        objective_path=_real_path("terraform_local_lab", "rastro_local", "objective_aws_role_chaining.local.json"),
        scope_path=_real_path("terraform_local_lab", "rastro_local", "scope_aws_role_chaining_openai.local.json"),
        discovery_ssm_prefixes=["/prod", "/app", "/finance", "/shared"],
    ),
    "aws-iam-attach-role-policy-privesc": ProfileDefinition(
        name="aws-iam-attach-role-policy-privesc",
        bundle="aws-iam-heavy",
        description="IAM privilege-escalation opportunity via policy attachment or inline policy mutation.",
        fixture_path=_real_path("terraform_local_lab", "rastro_local", "aws_role_chaining_lab.local.json"),
        objective_path=_real_path("terraform_local_lab", "rastro_local", "objective_aws_role_chaining.local.json"),
        scope_path=_real_path("terraform_local_lab", "rastro_local", "scope_aws_role_chaining_openai.local.json"),
        discovery_ssm_prefixes=["/prod", "/app", "/finance", "/shared"],
    ),
    "aws-iam-pass-role-privesc": ProfileDefinition(
        name="aws-iam-pass-role-privesc",
        bundle="aws-iam-heavy",
        description="IAM privilege-escalation opportunity via PassRole into service-controlled compute.",
        fixture_path=_real_path("terraform_local_lab", "rastro_local", "aws_role_chaining_lab.local.json"),
        objective_path=_real_path("terraform_local_lab", "rastro_local", "objective_aws_role_chaining.local.json"),
        scope_path=_real_path("terraform_local_lab", "rastro_local", "scope_aws_role_chaining_openai.local.json"),
        discovery_ssm_prefixes=["/prod", "/app", "/finance", "/shared"],
    ),
    "aws-credential-access-secret": ProfileDefinition(
        name="aws-credential-access-secret",
        bundle="aws-iam-heavy",
        description="Direct credential extraction from Secrets Manager — entry identity reads secret without role chain.",
        fixture_path=_real_path("terraform_local_lab", "rastro_local", "aws_role_chaining_lab.local.json"),
        objective_path=_real_path("terraform_local_lab", "rastro_local", "objective_aws_role_chaining.local.json"),
        scope_path=_real_path("terraform_local_lab", "rastro_local", "scope_aws_role_chaining_openai.local.json"),
        discovery_ssm_prefixes=["/prod", "/app", "/finance", "/shared"],
    ),
}


BUNDLES: dict[str, list[str]] = {
    "aws-foundation": [
        "aws-iam-s3",
        "aws-iam-secrets",
        "aws-iam-ssm",
        "aws-iam-role-chaining",
    ],
    "aws-iam-role-chaining-only": [
        "aws-iam-role-chaining",
    ],
    "aws-iam-attach-role-policy-only": [
        "aws-iam-attach-role-policy-privesc",
    ],
    "aws-iam-heavy": [
        "aws-iam-role-chaining",
        "aws-iam-create-policy-version-privesc",
        "aws-iam-attach-role-policy-privesc",
        "aws-iam-pass-role-privesc",
        "aws-iam-s3",
        "aws-iam-secrets",
        "aws-iam-ssm",
        "aws-credential-access-secret",
    ],
}


def get_profile(name: str) -> ProfileDefinition:
    return FOUNDATION_PROFILES[name]


def list_profiles() -> list[ProfileDefinition]:
    return list(FOUNDATION_PROFILES.values())


def resolve_bundle(name: str) -> list[ProfileDefinition]:
    return [get_profile(profile_name) for profile_name in BUNDLES[name]]
