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
    "aws-credential-pivot": ProfileDefinition(
        name="aws-credential-pivot",
        bundle="aws-iam-heavy",
        description="Credential pivot — extract AWS credentials from a secret, then assume a privileged role.",
        fixture_path=_real_path("terraform_local_lab", "credential_pivot_real", "rastro_local", "aws_credential_pivot_lab.local.json"),
        objective_path=_real_path("terraform_local_lab", "credential_pivot_real", "rastro_local", "objective_aws_credential_pivot.local.json"),
        scope_path=_real_path("terraform_local_lab", "credential_pivot_real", "rastro_local", "scope_aws_credential_pivot_openai.local.json"),
        discovery_ssm_prefixes=[],
    ),
    "aws-credential-pivot-ssm": ProfileDefinition(
        name="aws-credential-pivot-ssm",
        bundle="aws-iam-heavy",
        description="Credential pivot via SSM — extract AWS credentials from an SSM parameter, then assume a privileged role.",
        fixture_path=_real_path("terraform-realistic-iam", "ssm_parameter_pivot_real", "rastro_local", "aws_ssm_parameter_pivot_lab.local.json"),
        objective_path=_real_path("terraform-realistic-iam", "ssm_parameter_pivot_real", "rastro_local", "objective_aws_ssm_parameter_pivot.local.json"),
        scope_path=_real_path("terraform-realistic-iam", "ssm_parameter_pivot_real", "rastro_local", "scope_aws_ssm_parameter_pivot_openai.local.json"),
        discovery_ssm_prefixes=["/svc"],
    ),
    "aws-credential-pivot-s3": ProfileDefinition(
        name="aws-credential-pivot-s3",
        bundle="aws-iam-heavy",
        description="Credential pivot via S3 — extract AWS credentials from an S3 object, then assume a privileged role.",
        fixture_path=_real_path("terraform-realistic-iam", "s3_object_pivot_real", "rastro_local", "aws_s3_object_pivot_lab.local.json"),
        objective_path=_real_path("terraform-realistic-iam", "s3_object_pivot_real", "rastro_local", "objective_aws_s3_object_pivot.local.json"),
        scope_path=_real_path("terraform-realistic-iam", "s3_object_pivot_real", "rastro_local", "scope_aws_s3_object_pivot_openai.local.json"),
        discovery_ssm_prefixes=[],
    ),
    "aws-iam-create-access-key-pivot": ProfileDefinition(
        name="aws-iam-create-access-key-pivot",
        bundle="aws-iam-heavy",
        description="CreateAccessKey pivot — entry user creates access key for target user, extracted identity assumes privileged role.",
        fixture_path=_real_path("terraform-realistic-iam", "create_access_key_pivot_real", "rastro_local", "aws_create_access_key_pivot_lab.local.json"),
        objective_path=_real_path("terraform-realistic-iam", "create_access_key_pivot_real", "rastro_local", "objective_aws_create_access_key_pivot.local.json"),
        scope_path=_real_path("terraform-realistic-iam", "create_access_key_pivot_real", "rastro_local", "scope_aws_create_access_key_pivot_openai.local.json"),
        discovery_ssm_prefixes=[],
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
        "aws-credential-pivot",
        "aws-credential-pivot-ssm",
        "aws-credential-pivot-s3",
        "aws-iam-create-access-key-pivot",
    ],
}


def get_profile(name: str) -> ProfileDefinition:
    return FOUNDATION_PROFILES[name]


def list_profiles() -> list[ProfileDefinition]:
    return list(FOUNDATION_PROFILES.values())


def resolve_bundle(name: str) -> list[ProfileDefinition]:
    return [get_profile(profile_name) for profile_name in BUNDLES[name]]
