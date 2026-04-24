from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from core.capability_graph import CapabilityGraph
from core.domain import ActionType, Scope, TargetType

logger = logging.getLogger(__name__)
from core.blind_real_runtime import BlindRealRuntime
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
    if not target.entry_roles and not target.entry_credential_profiles:
        issues.append("target.entry_roles must not be empty (or provide entry_credential_profiles)")
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


def build_campaign_scope_from_path(
    scope_path: Path,
    target: TargetConfig,
    authorization: AuthorizationConfig,
) -> Scope:
    scope = Scope.model_validate_json(scope_path.read_text())
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
        campaign_id=None,
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
    discovery_snapshot: dict | None = None,
    attack_steps: list[str] | None = None,
) -> CampaignResult:
    profile_resolver = profile_resolver or get_profile
    profile_name = plan["profile"]
    validate_profile_access(profile_name, authorization)
    generated_scope_path = Path(plan["generated_scope"])
    generated_objective_path = Path(plan["generated_objective"])
    generated_scope_data = json.loads(generated_scope_path.read_text())
    if (
        discovery_snapshot is not None
        and discovery_snapshot.get("caller_identity")
        and os.getenv("RASTRO_ENABLE_AWS_REAL", "0") == "1"
        and generated_scope_data.get("target") == "aws"
    ):
        generated_scope_data["dry_run"] = False
        generated_scope_data["allowed_resources"] = _blind_real_allowed_resources(
            plan=plan,
            discovery_snapshot=discovery_snapshot,
            target=target,
        )
        if authorization.planner_config:
            generated_scope_data["planner"] = authorization.planner_config
        generated_scope_path.write_text(json.dumps(generated_scope_data, indent=2))
    generated_scope = Scope.model_validate(generated_scope_data)
    runtime_fixture = None
    resolved_fixture_path = None
    if (
        discovery_snapshot is not None
        and generated_scope.target.value == "aws"
        and not generated_scope.dry_run
    ):
        entry_identities = plan.get("entry_identities") or target.entry_roles
        runtime_fixture = BlindRealRuntime.build(
            plan=plan,
            discovery_snapshot=discovery_snapshot,
            scope=generated_scope,
            entry_identities=entry_identities,
        )
        # runtime-driven plans must not fall back to fixture path
        plan["fixture_path"] = None
        plan["scope_template_path"] = None
        plan["execution_fixture_set"] = None
    else:
        fixture_path = plan.get("fixture_path")
        if fixture_path:
            resolved_fixture_path = Path(fixture_path)
        else:
            profile = _resolve_profile(profile_resolver, profile_name, plan)
            resolved_fixture_path = profile.fixture_path
    if (
        discovery_snapshot is not None
        and generated_scope.target.value == "aws"
        and not generated_scope.dry_run
        and resolved_fixture_path is not None
    ):
        raise ValueError("blind real campaigns derived from discovery must not use fixture_path")
    # Resolve AWS credential profile for the entry identity of this campaign.
    entry_identities = plan.get("entry_identities") or []
    entry_profile: str | None = None
    if entry_identities and target.entry_credential_profiles:
        entry_profile = target.entry_credential_profiles.get(entry_identities[0])

    try:
        runner_kwargs = dict(
            fixture_path=resolved_fixture_path,
            objective_path=generated_objective_path,
            scope_path=generated_scope_path,
            output_dir=output_dir,
            max_steps=max_steps,
            seed=seed,
        )
        if runtime_fixture is not None:
            runner_kwargs["runtime_fixture"] = runtime_fixture
        if attack_steps:
            runner_kwargs["attack_steps"] = attack_steps
        if entry_profile:
            runner_kwargs["entry_profile"] = entry_profile
        result = runner(**runner_kwargs)
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
        campaign_id=plan.get("id"),
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


def _build_scope_for_strategic_planner(target: TargetConfig, authorization: AuthorizationConfig) -> Scope:
    return Scope(
        target=TargetType.AWS,
        allowed_actions=[
            ActionType.ENUMERATE,
            ActionType.ASSUME_ROLE,
            ActionType.ACCESS_RESOURCE,
            ActionType.ANALYZE,
        ],
        allowed_resources=["*"],
        aws_account_ids=target.accounts,
        allowed_regions=target.allowed_regions or ["us-east-1"],
        allowed_services=["iam", "sts", "s3", "secretsmanager", "ssm", "ec2", "lambda"],
        authorized_by=authorization.authorized_by,
        authorized_at=authorization.authorized_at,
        authorization_document=authorization.authorization_document,
    )


def _scope_enforce_hypotheses(hypotheses, target: TargetConfig) -> list:
    if not target.accounts:
        return hypotheses
    allowed_accounts = set(target.accounts)

    def _account_ok(arn: str) -> bool:
        parts = arn.split(":")
        if len(parts) < 5:
            return True  # non-ARN or global resource — allow
        account = parts[4]
        return not account or account in allowed_accounts

    return [h for h in hypotheses if _account_ok(h.target)]


def _attack_class_to_profile(attack_class: str, target_arn: str, attack_steps: list[str]) -> str:
    if attack_class == "role_chain":
        return "aws-iam-role-chaining"
    if attack_class == "iam_privesc":
        steps_lower = " ".join(attack_steps).lower()
        if "createpolicyversion" in steps_lower or "create_policy_version" in steps_lower:
            return "aws-iam-create-policy-version-privesc"
        if "attachrolepolicy" in steps_lower or "attach_role_policy" in steps_lower:
            return "aws-iam-attach-role-policy-privesc"
        if "putrolepolicy" in steps_lower or "put_role_policy" in steps_lower:
            # iam:PutRolePolicy injeta policy inline em role — mesmo efeito que AttachRolePolicy
            return "aws-iam-attach-role-policy-privesc"
        if "passrole" in steps_lower or "pass_role" in steps_lower:
            return "aws-iam-pass-role-privesc"
        return "aws-iam-role-chaining"
    if attack_class == "credential_access":
        if "secretsmanager" in target_arn:
            return "aws-iam-secrets"
        if ":ssm:" in target_arn or "/parameter/" in target_arn:
            return "aws-iam-ssm"
        return "aws-iam-secrets"
    if attack_class == "credential_access_direct":
        if "secretsmanager" in target_arn:
            return "aws-credential-access-secret"
        if ":ssm:" in target_arn or "/parameter/" in target_arn:
            return "aws-iam-ssm"
        return "aws-credential-access-secret"
    if attack_class == "credential_pivot":
        # Routa para o perfil correto com base no tipo do intermediate_resource
        # (passado via attack_steps ou target_arn para compatibilidade)
        return "aws-credential-pivot"
    if attack_class == "ssm_pivot":
        return "aws-credential-pivot-ssm"
    if attack_class == "s3_pivot":
        return "aws-credential-pivot-s3"
    if attack_class == "iam_create_access_key_pivot":
        return "aws-iam-create-access-key-pivot"
    if attack_class == "data_exfil":
        return "aws-iam-s3"
    if attack_class == "compute_pivot":
        return "aws-iam-compute-iam"
    return "aws-iam-role-chaining"


def _confidence_to_score(confidence: str) -> int:
    return {"high": 80, "medium": 50, "low": 20}.get(confidence, 20)


_ACTION_TO_CLASS: dict[str, str] = {
    "iam:attachrolepolicy": "iam_privesc",
    "iam:createpolicyversion": "iam_privesc",
    "iam:putrolepolicy": "iam_privesc",
    "iam:setdefaultpolicyversion": "iam_privesc",
    "iam:updateassumerolepolicy": "iam_privesc",
    "iam:createaccesskey": "iam_privesc",
    "iam:createloginprofile": "iam_privesc",
    "iam:updateloginprofile": "iam_privesc",
    "iam:attachuserpolicy": "iam_privesc",
    "iam:addusertgroup": "iam_privesc",
    "sts:assumerole": "role_chain",
    "iam:passrole": "compute_pivot",
    "secretsmanager:getsecretvalue": "credential_access",
    "ssm:getparameter": "credential_access",
    "ssm:getparametersbypath": "credential_access",
    "s3:getobject": "data_exfil",
}

_IAM_PRIVESC_STEP: dict[str, str] = {
    "iam:attachrolepolicy": "Call iam:AttachRolePolicy to attach AdministratorAccess to {target}",
    "iam:createpolicyversion": "Call iam:CreatePolicyVersion on {target} to inject Allow:* policy version",
    "iam:putrolepolicy": "Call iam:PutRolePolicy on {target} to inject an inline Allow:* policy",
    "iam:setdefaultpolicyversion": "Call iam:SetDefaultPolicyVersion on {target} to activate a privileged version",
    "iam:updateassumerolepolicy": "Call iam:UpdateAssumeRolePolicy on {target} to add attacker as trusted principal, then sts:AssumeRole",
    "iam:createaccesskey": "Call iam:CreateAccessKey on {target} to extract long-term credentials",
    "iam:createloginprofile": "Call iam:CreateLoginProfile on {target} to set console password",
    "iam:updateloginprofile": "Call iam:UpdateLoginProfile on {target} to reset console password",
    "iam:attachuserpolicy": "Call iam:AttachUserPolicy on {target} to attach AdministratorAccess",
    "iam:addusertgroup": "Call iam:AddUserToGroup on {target} to add attacker to privileged group",
}


def _derive_hypotheses_from_snapshot(
    discovery_snapshot: dict,
    entry_identities: list[str],
) -> list:
    """Síntese determinística: converte derived_attack_targets em AttackHypothesis sem LLM.

    Garante recall 100% para todos os entry identities com targets pré-computados.
    """
    from planner.strategic_planner import AttackHypothesis

    identity_set = set(entry_identities)
    resource_map = {
        r["identifier"]: r
        for r in discovery_snapshot.get("resources", [])
        if r.get("identifier")
    }
    hypotheses: list[AttackHypothesis] = []

    for arn in entry_identities:
        r = resource_map.get(arn)
        if r is None:
            continue
        meta = r.get("metadata") or {}
        derived = meta.get("derived_attack_targets")
        if not derived:
            continue

        for entry in derived:
            action: str = entry.get("action", "")
            target_arn: str = entry.get("target_arn", "")
            if not action or not target_arn:
                continue
            action_lower = action.lower()
            attack_class = _ACTION_TO_CLASS.get(action_lower)
            if not attack_class:
                continue

            step_template = _IAM_PRIVESC_STEP.get(
                action_lower,
                f"Call {action} on {{target}}",
            )
            step = step_template.format(target=target_arn)

            if attack_class == "role_chain":
                steps = [
                    f"Call sts:AssumeRole to assume {target_arn}",
                    "Use assumed role credentials to escalate further in the chain",
                ]
            elif attack_class == "compute_pivot":
                steps = [
                    f"Call iam:PassRole to pass {target_arn} to a Lambda/EC2/Glue/SageMaker service",
                    "Create a compute resource with the passed role to gain its permissions",
                ]
            elif attack_class == "credential_access":
                steps = [f"Call {action} on {target_arn} to extract credentials or secrets"]
            elif attack_class == "data_exfil":
                steps = [f"Call {action} on {target_arn} to read sensitive data"]
            else:
                steps = [step]

            hypotheses.append(
                AttackHypothesis(
                    entry_identity=arn,
                    target=target_arn,
                    attack_class=attack_class,
                    attack_steps=steps,
                    confidence="high",
                    reasoning=(
                        f"Deterministic: policy_permissions grants {action} with "
                        f"resolved target {target_arn} (derived_attack_targets)."
                    ),
                )
            )

    return hypotheses


# Data resource types that carry readable_by (Bloco 6a/6d)
_DIRECT_READ_RESOURCE_TYPES = {
    "secret.secrets_manager",
    "secret.ssm_parameter",
}

# Resource types that can carry embedded credentials for pivot (6c/6d)
_PIVOT_READ_RESOURCE_TYPES = {
    "secret.secrets_manager",
    "secret.ssm_parameter",
    "data_store.s3_object",
}


def _derive_credential_access_hypotheses(
    discovery_snapshot: dict,
    entry_identities: list[str],
) -> list:
    """Bloco 6b: hipóteses determinísticas de leitura direta de segredos.

    Para cada recurso de dado no snapshot com readable_by preenchido (Bloco 6a),
    se o entry_identity aparece em readable_by, gera uma hipótese credential_access_direct
    com confidence=high (não depende de LLM).
    """
    from planner.strategic_planner import AttackHypothesis

    identity_set = set(entry_identities)
    hypotheses: list[AttackHypothesis] = []

    for resource in discovery_snapshot.get("resources", []):
        if resource.get("resource_type") not in _DIRECT_READ_RESOURCE_TYPES:
            continue
        resource_arn = resource.get("identifier", "")
        meta = resource.get("metadata") or {}
        readable_by: list[str] = meta.get("readable_by", [])

        for principal_arn in readable_by:
            if principal_arn not in identity_set:
                continue

            is_secret = "secretsmanager" in resource_arn
            action = "secretsmanager:GetSecretValue" if is_secret else "ssm:GetParameter"
            hypotheses.append(
                AttackHypothesis(
                    entry_identity=principal_arn,
                    target=resource_arn,
                    attack_class="credential_access_direct",
                    attack_steps=[
                        f"Call {action} on {resource_arn} to extract stored credentials",
                        "Parse returned value for AWS access keys or other credentials",
                    ],
                    confidence="high",
                    reasoning=(
                        f"Deterministic: readable_by confirms {principal_arn} has {action} "
                        f"on {resource_arn} (computed by _compute_data_resource_access)."
                    ),
                )
            )

    return hypotheses


def _derive_credential_pivot_hypotheses(
    discovery_snapshot: dict,
    entry_identities: list[str],
) -> list:
    """Bloco 6c: hipóteses de pivot via credencial extraída de segredo.

    Para cada entry identity que pode ler um segredo (readable_by), gera hipótese
    credential_pivot com target=role e intermediate_resource=secret.
    """
    from planner.strategic_planner import AttackHypothesis

    identity_set = set(entry_identities)
    resources = discovery_snapshot.get("resources", [])

    # Coleta roles disponíveis (exclui service roles)
    role_arns = [
        r["identifier"]
        for r in resources
        if r.get("resource_type") == "identity.role"
        and ":role/aws-service-role/" not in r.get("identifier", "")
    ]
    if not role_arns:
        return []

    hypotheses: list[AttackHypothesis] = []
    for resource in resources:
        rtype = resource.get("resource_type", "")
        if rtype not in _PIVOT_READ_RESOURCE_TYPES:
            continue
        resource_arn = resource.get("identifier", "")
        readable_by: list[str] = (resource.get("metadata") or {}).get("readable_by", [])
        # Determina attack_class baseado no tipo do recurso intermediário
        if rtype == "secret.secrets_manager":
            attack_class = "credential_pivot"
        elif rtype == "secret.ssm_parameter":
            attack_class = "ssm_pivot"
        else:  # data_store.s3_object
            attack_class = "s3_pivot"
        for principal_arn in readable_by:
            if principal_arn not in identity_set:
                continue
            for role_arn in role_arns:
                hypotheses.append(
                    AttackHypothesis(
                        entry_identity=principal_arn,
                        target=role_arn,
                        attack_class=attack_class,
                        intermediate_resource=resource_arn,
                        attack_steps=[
                            f"Read {resource_arn} to extract embedded AWS credentials",
                            f"Use extracted identity to call sts:AssumeRole on {role_arn}",
                        ],
                        confidence="medium",
                        reasoning=(
                            f"Deterministic: {principal_arn} can read {resource_arn} "
                            f"(readable_by). Embedded credentials may trust {role_arn}."
                        ),
                    )
                )
    return hypotheses


def _derive_create_access_key_hypotheses(
    discovery_snapshot: dict,
    entry_identities: list[str],
) -> list:
    """Bloco 6d: hipóteses de pivot via iam:CreateAccessKey.

    Para cada user com createkey_by preenchido no snapshot, gera hipótese
    iam_create_access_key_pivot com target=role para todos os roles disponíveis.
    """
    from planner.strategic_planner import AttackHypothesis

    identity_set = set(entry_identities)
    resources = discovery_snapshot.get("resources", [])

    role_arns = [
        r["identifier"]
        for r in resources
        if r.get("resource_type") == "identity.role"
        and ":role/aws-service-role/" not in r.get("identifier", "")
    ]
    if not role_arns:
        return []

    hypotheses: list[AttackHypothesis] = []
    for resource in resources:
        if resource.get("resource_type") != "identity.user":
            continue
        user_arn = resource.get("identifier", "")
        createkey_by: list[str] = (resource.get("metadata") or {}).get("createkey_by", [])
        for principal_arn in createkey_by:
            if principal_arn not in identity_set:
                continue
            for role_arn in role_arns:
                hypotheses.append(
                    AttackHypothesis(
                        entry_identity=principal_arn,
                        target=role_arn,
                        attack_class="iam_create_access_key_pivot",
                        intermediate_resource=user_arn,
                        attack_steps=[
                            f"Call iam:CreateAccessKey on {user_arn} to create long-term credentials",
                            f"Use extracted identity to call sts:AssumeRole on {role_arn}",
                        ],
                        confidence="medium",
                        reasoning=(
                            f"Deterministic: {principal_arn} has iam:CreateAccessKey on {user_arn} "
                            f"(createkey_by). Created credentials may trust {role_arn}."
                        ),
                    )
                )
    return hypotheses


def _infer_resource_type_from_arn(arn: str) -> str:
    if ":role/" in arn:
        return "identity.role"
    if ":user/" in arn:
        return "identity.user"
    if "secretsmanager" in arn:
        return "secret.secrets_manager"
    if ":ssm:" in arn and "/parameter/" in arn:
        return "secret.ssm_parameter"
    if arn.startswith("arn:aws:s3:::"):
        return "data_store.s3_object" if "/" in arn.split(":::")[-1] else "data_store.s3_bucket"
    if ":lambda:" in arn:
        return "compute.lambda_function"
    if ":ec2:" in arn:
        return "compute.ec2_instance"
    return "unknown"


def _hypotheses_to_candidates_payload(hypotheses, discovery_snapshot: dict, bundle_name: str) -> dict:
    bundle_profiles = {p.name for p in resolve_bundle(bundle_name)}
    # Build set of known ARNs and privilege scores for target resolution.
    known_arns: set[str] = set()
    target_priv_scores: dict[str, int] = {}
    for r in discovery_snapshot.get("resources", []):
        arn = r.get("identifier", "")
        if arn and arn.startswith("arn:aws:"):
            known_arns.add(arn)
        if r.get("resource_type") in ("identity.user", "identity.role"):
            priv_score = (r.get("metadata") or {}).get("privilege_score", 0)
            if priv_score:
                target_priv_scores[arn] = priv_score

    candidates = []
    seen: set[tuple[str, str]] = set()
    for hyp in hypotheses:
        profile_family = _attack_class_to_profile(hyp.attack_class, hyp.target, hyp.attack_steps)
        if profile_family not in bundle_profiles:
            logger.debug("Skipping hypothesis: profile %s not in bundle %s", profile_family, bundle_name)
            continue
        # Reject targets that are not wildcards and don't exist in the discovery snapshot.
        if hyp.target and hyp.target != "*" and hyp.target not in known_arns:
            logger.warning("Skipping hypothesis: target %s not found in discovery snapshot", hyp.target)
            continue
        key = (profile_family, hyp.target)
        if key in seen:
            continue
        seen.add(key)
        base_score = _confidence_to_score(hyp.confidence)
        # Tiebreaker: adiciona bônus baseado no privilege_score do alvo (0-15 pts).
        # Garante que roles de alto valor (iam:*, score elevado) sejam priorizados
        # sobre alvos menos relevantes com mesma confidence.
        priv_bonus = min(15, target_priv_scores.get(hyp.target, 0) // 600)
        score = base_score + priv_bonus
        candidates.append({
            "id": f"{profile_family}:{_slugify(hyp.target)}",
            "resource_arn": hyp.target,
            "resource_type": _infer_resource_type_from_arn(hyp.target),
            "profile_family": profile_family,
            "score": score,
            "confidence": hyp.confidence,
            "selection_reason": [f"strategic:{hyp.attack_class}", *hyp.attack_steps[:2]],
            "signals": {"reasoning": hyp.reasoning, "entry_identity": hyp.entry_identity, "attack_steps": hyp.attack_steps},
            "score_components": {"lexical": 0, "structural": base_score, "privilege_bonus": priv_bonus},
            "execution_fixture_set": None,
            "fixture_path": None,
            "scope_template_path": None,
            "supporting_evidence": {},
        })
    by_profile: dict[str, int] = {}
    for c in candidates:
        by_profile[c["profile_family"]] = by_profile.get(c["profile_family"], 0) + 1
    return {
        "target": discovery_snapshot.get("target"),
        "bundle": bundle_name,
        "derived_from": "strategic_planner",
        "summary": {"candidates_total": len(candidates), "by_profile": by_profile},
        "candidates": candidates,
    }


def _write_strategic_candidates(payload: dict, output_dir: Path) -> tuple[Path, Path, dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "target_candidates.json"
    md_path = output_dir / "target_candidates.md"
    json_path.write_text(json.dumps(payload, indent=2))
    lines = ["# Strategic Candidates\n", f"Source: {payload.get('derived_from')}\n\n"]
    for c in payload.get("candidates", []):
        lines.append(f"- `{c['profile_family']}` → `{c['resource_arn']}` ({c['confidence']})\n")
    md_path.write_text("".join(lines))
    return json_path, md_path, payload


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
    strategic_planner=None,
    max_hypotheses: int = 20,
) -> AssessmentResult:
    from operations.campaign_synthesis import synthesize_foundation_campaigns
    from operations.discovery import run_foundation_discovery
    from operations.target_selection import select_foundation_targets

    discovery_runner = discovery_runner or run_foundation_discovery
    target_selector = target_selector or select_foundation_targets
    campaign_synthesizer = campaign_synthesizer or synthesize_foundation_campaigns
    discovery_dir = output_dir / "discovery"
    candidates_dir = output_dir / "target-selection"
    campaign_plan_dir = output_dir / "campaign-synthesis"

    discovery_json, discovery_md, discovery_snapshot = discovery_runner(
        bundle_name=bundle_name,
        target=target,
        authorization=authorization,
        output_dir=discovery_dir,
    )
    # Strategic planner: LLM reasons about discovery before target selection.
    # Falls back to rule-based target_selector on any failure or empty result.
    strategic_hypotheses_path = None
    strategic_active = False
    if strategic_planner is not None:
        # For strategic reasoning, always expose all discovered identities so the LLM
        # can reason about which users have vulnerable permissions (e.g. iam:CreatePolicyVersion).
        # Campaign execution uses entry_roles separately (see below).
        discovered_users = [
            r.get("identifier")
            for r in discovery_snapshot.get("resources", [])
            if r.get("resource_type") == "identity.user" and r.get("identifier")
        ]
        effective_entry_identities = sorted(set(discovered_users)) or list(target.entry_roles)
        scope_for_strategic = _build_scope_for_strategic_planner(target, authorization)
        try:
            # Síntese determinística primeiro (derived_attack_targets → hipóteses sem LLM)
            det_hypotheses = _derive_hypotheses_from_snapshot(
                discovery_snapshot, effective_entry_identities
            )
            logger.info(
                "Deterministic hypotheses from derived_attack_targets: %d", len(det_hypotheses)
            )

            # Bloco 9: hipóteses via BFS do CapabilityGraph
            # (substitui _derive_credential_access_hypotheses,
            #  _derive_credential_pivot_hypotheses e _derive_create_access_key_hypotheses)
            cap_graph = CapabilityGraph.build(discovery_snapshot)
            graph_hypotheses = cap_graph.derive_all_hypotheses(effective_entry_identities)
            if graph_hypotheses:
                logger.info(
                    "CapabilityGraph BFS hypotheses: %d", len(graph_hypotheses)
                )
                det_hypotheses.extend(graph_hypotheses)

            llm_hypotheses = strategic_planner.plan_attacks(
                discovery_snapshot, effective_entry_identities, scope_for_strategic
            )

            # Merge: LLM first (may have richer steps), then fill in any missed with deterministic.
            # Dedup key usa profile_family (não attack_class) para que AttachRolePolicy,
            # CreatePolicyVersion e PutRolePolicy gerem candidatos em perfis distintos.
            seen_keys: set[tuple] = {
                (h.entry_identity, h.target,
                 _attack_class_to_profile(h.attack_class, h.target, h.attack_steps))
                for h in llm_hypotheses
            }
            for h in det_hypotheses:
                key = (h.entry_identity, h.target,
                       _attack_class_to_profile(h.attack_class, h.target, h.attack_steps))
                if key not in seen_keys:
                    seen_keys.add(key)
                    llm_hypotheses.append(h)

            hypotheses = _scope_enforce_hypotheses(llm_hypotheses, target)[:max_hypotheses]
            if hypotheses:
                strategic_payload = _hypotheses_to_candidates_payload(
                    hypotheses, discovery_snapshot, bundle_name
                )
                candidates_dir.mkdir(parents=True, exist_ok=True)
                hyp_path = candidates_dir / "strategic_hypotheses.json"
                hyp_path.write_text(json.dumps([h.model_dump() for h in hypotheses], indent=2))
                strategic_hypotheses_path = hyp_path
                candidates_json, candidates_md, candidates_payload = _write_strategic_candidates(
                    strategic_payload, candidates_dir
                )
                strategic_active = True
        except Exception as exc:
            logger.warning("Strategic planner failed, falling back to rule-based: %s", exc)

    if not strategic_active:
        candidates_json, candidates_md, candidates_payload = target_selector(
            discovery_snapshot=discovery_snapshot,
            output_dir=candidates_dir,
            max_candidates_per_profile=max_candidates_per_profile,
            bundle_name=bundle_name,
        )
    entry_identities = _blind_real_entry_identities(discovery_snapshot=discovery_snapshot, target=target)
    if authorization.permitted_entry_identities:
        entry_identities = [e for e in entry_identities if e in authorization.permitted_entry_identities]
    synthesis_target = target
    if entry_identities and not target.entry_roles:
        synthesis_target = target.model_copy(update={"entry_roles": entry_identities})
    campaign_plan_json, campaign_plan_md, campaign_plan_payload = campaign_synthesizer(
        candidates_payload=candidates_payload,
        target=synthesis_target,
        authorization=authorization,
        output_dir=campaign_plan_dir,
        max_plans_per_profile=max_plans_per_profile,
        dedupe_resource_targets=dedupe_resource_targets,
        profile_resolver=profile_resolver,
    )

    campaigns: list[CampaignResult] = []
    for plan in campaign_plan_payload["plans"]:
        base_plan_id = plan.get("id") or f"{plan['profile']}:{_slugify(plan.get('resource_arn', plan.get('generated_objective', 'campaign')))}"
        profile_ids = authorization.profile_entry_identities.get(plan["profile"])
        # Prioridade: 1) profile_entry_identities explícito, 2) signals.entry_identity
        # da hipótese (sabe qual user tem a capability), 3) todos os entry_identities.
        if profile_ids is not None:
            plan_entry_identities = profile_ids
        else:
            hypothesis_entry = (plan.get("signals") or {}).get("entry_identity")
            if hypothesis_entry and hypothesis_entry in entry_identities:
                plan_entry_identities = [hypothesis_entry]
            else:
                plan_entry_identities = entry_identities
        for entry_identity in plan_entry_identities:
            actor_slug = _slugify(entry_identity)
            plan_id = f"{base_plan_id}:{actor_slug}"
            campaign_output = output_dir / "campaigns" / plan["profile"] / _slugify(plan_id)
            campaigns.append(
                run_generated_campaign(
                    plan={
                        **plan,
                        "id": plan_id,
                        "entry_identities": [entry_identity],
                    },
                    target=target,
                    authorization=authorization,
                    output_dir=campaign_output,
                    runner=runner,
                    max_steps=max_steps,
                    seed=seed,
                    profile_resolver=profile_resolver,
                    discovery_snapshot=discovery_snapshot,
                    attack_steps=plan.get("signals", {}).get("attack_steps"),
                )
            )

    artifacts = {
        "discovery_json": str(discovery_json),
        "discovery_md": str(discovery_md),
        "target_candidates_json": str(candidates_json),
        "target_candidates_md": str(candidates_md),
        "campaign_plan_json": str(campaign_plan_json),
        "campaign_plan_md": str(campaign_plan_md),
    }
    if strategic_hypotheses_path is not None:
        artifacts["strategic_hypotheses_json"] = str(strategic_hypotheses_path)
    return AssessmentResult(
        bundle=bundle_name,
        target=target.name,
        summary=build_assessment_summary(campaigns),
        artifacts=artifacts,
        campaigns=campaigns,
    )


def _resolve_profile(profile_resolver, profile_name: str, plan: dict):
    if profile_resolver is None:
        raise ValueError(f"profile_resolver is required to resolve profile {profile_name}")
    try:
        return profile_resolver(profile_name, plan)
    except TypeError:
        return profile_resolver(profile_name)


def _extract_account_id(resource_arn: str) -> str | None:
    if not resource_arn.startswith("arn:aws:"):
        return None
    parts = resource_arn.split(":")
    if len(parts) < 5:
        return None
    return parts[4] or None


def _blind_real_allowed_resources(*, plan: dict, discovery_snapshot: dict, target: TargetConfig) -> list[str]:
    allowed_resources: set[str] = set()
    resource_arn = plan.get("resource_arn")
    if resource_arn:
        allowed_resources.add(resource_arn)
    for resource in discovery_snapshot.get("resources", []):
        identifier = resource.get("identifier")
        if not identifier:
            continue
        rtype = resource.get("resource_type", "")
        if rtype == "identity.role":
            allowed_resources.add(identifier)
        # Bloco 6c/6d: pivot profiles need intermediate resources in scope
        elif rtype in ("secret.secrets_manager", "secret.ssm_parameter", "data_store.s3_object"):
            allowed_resources.add(identifier)
        elif rtype == "identity.user":
            # Bloco 6d: CreateAccessKey pivot targets users
            allowed_resources.add(identifier)
    return sorted(allowed_resources)


def _blind_real_entry_identities(*, discovery_snapshot: dict, target: TargetConfig) -> list[str]:
    if target.entry_roles:
        return list(target.entry_roles)
    users = [
        resource.get("identifier")
        for resource in discovery_snapshot.get("resources", [])
        if resource.get("resource_type") == "identity.user" and resource.get("identifier")
    ]
    return sorted(set(users))


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
    source_campaign_findings_total = sum(
        1
        for campaign in result.campaigns
        if campaign.status == "passed" and campaign.report_json and campaign.report_json.exists()
    )
    payload = {
        "bundle": result.bundle,
        "target": result.target,
        "summary": {
            "findings_total": len(findings),
            "source_campaign_findings_total": source_campaign_findings_total,
            "distinct_paths_total": len(findings),
            "principal_multiplicity_total": sum(finding.principal_multiplicity for finding in findings),
            "additional_principal_observations": sum(
                max(0, finding.principal_multiplicity - 1) for finding in findings
            ),
            "paths_with_multiple_principals": sum(
                1 for finding in findings if finding.principal_multiplicity > 1
            ),
            "validated_findings": sum(1 for finding in findings if finding.status == "validated"),
            "observed_findings": sum(1 for finding in findings if finding.status == "observed"),
            "finding_states": _count_states(findings),
            "by_profile": _count_findings_by_profile(findings),
            "principal_multiplicity_by_profile": _count_principal_multiplicity_by_profile(findings),
            "proof_modes": _count_proof_modes(findings),
        },
        "findings": [finding.model_dump(mode="json") for finding in findings],
    }
    json_path.write_text(json.dumps(payload, indent=2))
    md_path.write_text(_render_assessment_findings_markdown(payload))
    return json_path, md_path


def build_assessment_findings(result: AssessmentResult) -> list[AssessmentFinding]:
    aggregated: dict[tuple[str, str, str, str, str], dict] = {}
    for campaign in result.campaigns:
        if campaign.status not in {"passed", "objective_not_met"} or not campaign.report_json or not campaign.report_json.exists():
            continue
        report = json.loads(campaign.report_json.read_text())
        executive_summary = report.get("executive_summary", {})
        objective = report.get("objective", {})
        target_resource = executive_summary.get("final_resource") or objective.get("target") or "-"
        path_summary = _build_path_summary(report)
        finding_status, evidence_level = _classify_finding(report, campaign)
        if not _should_emit_finding(report, campaign, finding_status):
            continue
        finding_state = _determine_finding_state(report, campaign, target_resource)
        proof_mode = _determine_proof_mode(report, campaign, target_resource)
        evidence_summary = _build_evidence_summary(report, finding_status)
        distinct_path_key = _build_distinct_path_key(report, target_resource)
        entry_point = (
            executive_summary.get("effective_entry_identity")
            or executive_summary.get("initial_identity")
        )
        fingerprint = (
            campaign.profile,
            target_resource,
            finding_status,
            finding_state,
            distinct_path_key,
        )
        if fingerprint in aggregated:
            bucket = aggregated[fingerprint]
            if entry_point:
                bucket["entry_points"].add(entry_point)
            finding = bucket["finding"]
            finding.entry_points = sorted(bucket["entry_points"])
            finding.principal_multiplicity = len(finding.entry_points) or 1
            if finding.entry_points:
                finding.entry_point = finding.entry_points[0]
            continue
        aggregated[fingerprint] = {
            "entry_points": set([entry_point] if entry_point else []),
            "finding": AssessmentFinding(
                id=f"finding:{_finding_profile(campaign.profile, proof_mode)}:{_slugify(target_resource)}:{finding_status}",
                title=_build_finding_title(campaign.profile, target_resource, proof_mode),
                profile=_finding_profile(campaign.profile, proof_mode),
                severity=_severity_for_profile(campaign.profile),
                confidence="high" if campaign.objective_met else "medium",
                status=finding_status,
                finding_state=finding_state,
                target_resource=target_resource,
                entry_point=entry_point,
                entry_points=[entry_point] if entry_point else [],
                principal_multiplicity=1,
                distinct_path_key=distinct_path_key,
                path_summary=path_summary,
                services_involved=report.get("execution_policy", {}).get("allowed_services", []),
                evidence_summary=evidence_summary,
                evidence_level=evidence_level,
                proof_mode=proof_mode,
                mitre_techniques=[item.get("mitre_id") for item in report.get("mitre_techniques", []) if item.get("mitre_id")],
            ),
        }
    findings = [bucket["finding"] for bucket in aggregated.values()]
    findings.sort(key=lambda item: (item.profile, item.target_resource, item.distinct_path_key))
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


def _build_evidence_summary(report: dict, finding_status: str = "validated") -> str:
    executive_summary = report.get("executive_summary", {})
    external_entry_maturity = executive_summary.get("external_entry_maturity") or {}
    if external_entry_maturity.get("applicable"):
        classification = external_entry_maturity.get("classification")
        if classification == "public_exploit_path_proved_end_to_end":
            return "Public exploit path proved end-to-end."
        return "Public exposure structurally linked to privileged path."
    proof = executive_summary.get("proof")
    if proof:
        return f"Validated with proof: {proof}"
    if executive_summary.get("simulated_policy_result"):
        simulated = executive_summary["simulated_policy_result"]
        decision = (simulated.get("decision") or "").lower()
        if decision == "allowed":
            return (
                "Observed privilege-escalation opportunity via policy simulation: "
                f"action={simulated.get('action')} decision={simulated.get('decision')}"
            )
        return (
            "Policy simulation did not prove privilege-escalation opportunity: "
            f"action={simulated.get('action')} decision={simulated.get('decision')}"
        )
    final_resource = executive_summary.get("final_resource")
    if final_resource and finding_status == "validated":
        return f"Validated access to {final_resource}"
    return "Observed target or path without minimum proof for validated exploitation."


def _should_emit_finding(report: dict, campaign: CampaignResult, finding_status: str) -> bool:
    if campaign.profile not in {"aws-iam-s3", "aws-iam-secrets", "aws-iam-ssm"}:
        return True
    if finding_status == "validated":
        return True
    simulated = (report.get("executive_summary", {}) or {}).get("simulated_policy_result") or {}
    decision = (simulated.get("decision") or "").lower()
    return decision == "allowed"


def _classify_finding(report: dict, campaign: CampaignResult) -> tuple[str, str]:
    executive_summary = report.get("executive_summary", {})
    proof = executive_summary.get("proof")
    if proof:
        return "validated", "proved"
    target = (report.get("objective") or {}).get("target")
    successful_steps = [
        step for step in report.get("steps", [])
        if (step.get("observation") or {}).get("success")
    ]
    if campaign.profile in {"aws-iam-s3", "aws-iam-secrets", "aws-iam-ssm"}:
        for step in successful_steps:
            action = step.get("action") or {}
            details = ((step.get("observation") or {}).get("details") or {})
            evidence = details.get("evidence") or {}
            if (
                action.get("action_type") == "access_resource"
                and action.get("target") == target
                and evidence
                and not evidence.get("simulated")
            ):
                return "validated", "proved"
        return "observed", "observed"
    if campaign.profile == "aws-iam-role-chaining":
        for step in successful_steps:
            details = ((step.get("observation") or {}).get("details") or {})
            request_summary = details.get("request_summary") or {}
            if step.get("action", {}).get("action_type") == "assume_role" and (
                details.get("granted_role") == target or step.get("action", {}).get("target") == target
            ) and "sts:AssumeRole" in request_summary.get("api_calls", []):
                return "validated", "proved"
            if step.get("action", {}).get("action_type") == "assume_role" and (
                details.get("granted_role") == target or step.get("action", {}).get("target") == target
            ):
                return "observed", "observed"
        return "observed", "observed"
    if campaign.profile in {
        "aws-iam-create-policy-version-privesc",
        "aws-iam-attach-role-policy-privesc",
        "aws-iam-pass-role-privesc",
    }:
        for step in successful_steps:
            action = step.get("action") or {}
            details = ((step.get("observation") or {}).get("details") or {})
            request_summary = details.get("request_summary") or {}
            if action.get("target") == target and "iam:SimulatePrincipalPolicy" in request_summary.get("api_calls", []):
                return "observed", "observed"
        return "observed", "observed"
    return ("validated", "proved") if campaign.objective_met else ("observed", "observed")


def _determine_proof_mode(report: dict, campaign: CampaignResult, target_resource: str) -> str:
    executive_summary = report.get("executive_summary", {})
    if executive_summary.get("proof"):
        return "real"
    for step in report.get("steps", []):
        action = step.get("action") or {}
        details = ((step.get("observation") or {}).get("details") or {})
        if action.get("action_type") == "assume_role" and (
            details.get("granted_role") == target_resource or action.get("target") == target_resource
        ):
            return "simulation" if action.get("tool") == "iam_simulate_assume_role" else "real"
    if executive_summary.get("simulated_policy_result"):
        return "simulation"
    return "structural"


def _finding_profile(profile: str, proof_mode: str) -> str:
    if profile == "aws-iam-role-chaining":
        if proof_mode == "real":
            return "aws-iam-role-assumption-proved"
        if proof_mode == "simulation":
            return "aws-iam-role-chaining-simulated"
    return profile


def _build_finding_title(profile: str, target_resource: str, proof_mode: str = "structural") -> str:
    labels = {
        "aws-iam-s3": "IAM -> S3 exposure",
        "aws-iam-secrets": "IAM -> Secrets exposure",
        "aws-iam-ssm": "IAM -> SSM exposure",
        "aws-iam-role-chaining": "IAM role chaining exposure",
        "aws-iam-create-policy-version-privesc": "IAM CreatePolicyVersion privilege-escalation opportunity",
        "aws-iam-attach-role-policy-privesc": "IAM policy attachment privilege-escalation opportunity",
        "aws-iam-pass-role-privesc": "IAM PassRole privilege-escalation opportunity",
    }
    if profile == "aws-iam-role-chaining":
        if proof_mode == "real":
            return f"IAM role assumption proved for {target_resource}"
        if proof_mode == "simulation":
            return f"IAM role-chaining simulation opportunity to {target_resource}"
    return f"{labels.get(profile, profile)} to {target_resource}"


def _severity_for_profile(profile: str) -> str:
    severities = {
        "aws-iam-s3": "high",
        "aws-iam-secrets": "critical",
        "aws-iam-ssm": "high",
        "aws-iam-role-chaining": "high",
        "aws-iam-role-chaining-simulated": "high",
        "aws-iam-role-assumption-proved": "high",
        "aws-iam-create-policy-version-privesc": "high",
        "aws-iam-attach-role-policy-privesc": "high",
        "aws-iam-pass-role-privesc": "high",
    }
    return severities.get(profile, "medium")


def _count_findings_by_profile(findings: list[AssessmentFinding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.profile] = counts.get(finding.profile, 0) + 1
    return counts


def _count_principal_multiplicity_by_profile(findings: list[AssessmentFinding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.profile] = counts.get(finding.profile, 0) + finding.principal_multiplicity
    return counts


def _count_proof_modes(findings: list[AssessmentFinding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.proof_mode] = counts.get(finding.proof_mode, 0) + 1
    return counts


def _count_states(findings: list[AssessmentFinding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.finding_state] = counts.get(finding.finding_state, 0) + 1
    return counts


def _determine_finding_state(report: dict, campaign: CampaignResult, target_resource: str) -> str:
    steps = report.get("steps", [])
    success_steps = [
        step for step in steps if (step.get("observation") or {}).get("success")
    ]
    state = "observed"
    role_chaining_simulated_allow = False
    policy_probe_simulated_allow = False
    has_assume = False
    has_access = False
    for step in success_steps:
        action = step.get("action") or {}
        observation = (step.get("observation") or {}).get("details") or {}
        if action.get("action_type") == "assume_role":
            granted = observation.get("granted_role") or action.get("target")
            simulated = observation.get("simulated_policy_result") or {}
            if action.get("tool") == "iam_simulate_assume_role":
                if action.get("target") == target_resource and (simulated.get("decision") or "").lower() == "allowed":
                    role_chaining_simulated_allow = True
            elif granted:
                has_assume = True
        if action.get("tool") in {"iam_create_policy_version", "iam_create_policy_version_mutate", "iam_attach_role_policy", "iam_pass_role_service_create"}:
            simulated = observation.get("simulated_policy_result") or {}
            if action.get("target") == target_resource and (simulated.get("decision") or "").lower() == "allowed":
                policy_probe_simulated_allow = True
        if (
            action.get("action_type") == "access_resource"
            and action.get("target") == target_resource
            and action.get("tool")
            not in {"iam_create_policy_version", "iam_create_policy_version_mutate", "iam_attach_role_policy", "iam_pass_role_service_create"}
        ):
            if not (observation.get("evidence") or {}).get("simulated"):
                has_access = True
    if campaign.profile == "aws-iam-role-chaining":
        if role_chaining_simulated_allow:
            state = _state_rank("reachable", current=state)
    elif campaign.profile in {
        "aws-iam-create-policy-version-privesc",
        "aws-iam-attach-role-policy-privesc",
        "aws-iam-pass-role-privesc",
    }:
        if policy_probe_simulated_allow:
            state = _state_rank("reachable", current=state)
    elif success_steps:
        state = _state_rank("reachable")
    if has_assume:
        state = _state_rank("credentialed", current=state)
    if has_access:
        state = _state_rank("exploited", current=state)
    proof = report.get("executive_summary", {}).get("proof")
    if proof and campaign.objective_met:
        state = _state_rank("validated_impact", current=state)
    return state


def _state_rank(target_state: str, current: str | None = None) -> str:
    order = {
        "observed": 0,
        "reachable": 1,
        "credentialed": 2,
        "exploited": 3,
        "validated_impact": 4,
    }
    current_rank = order.get(current, 0) if current else 0
    target_rank = order.get(target_state, 0)
    return target_state if target_rank > current_rank else current or target_state


def _render_assessment_findings_markdown(payload: dict) -> str:
    lines = [
        "# Assessment Findings",
        "",
        f"- Bundle: {payload['bundle']}",
        f"- Target: {payload['target']}",
        f"- Findings total: {payload['summary']['findings_total']}",
        f"- Source campaign findings total: {payload['summary'].get('source_campaign_findings_total', payload['summary']['findings_total'])}",
        f"- Distinct paths total: {payload['summary'].get('distinct_paths_total', payload['summary']['findings_total'])}",
        f"- Principal multiplicity total: {payload['summary'].get('principal_multiplicity_total', payload['summary']['findings_total'])}",
        f"- Additional principal observations: {payload['summary'].get('additional_principal_observations', 0)}",
        f"- Paths with multiple principals: {payload['summary'].get('paths_with_multiple_principals', 0)}",
        f"- Finding states: {payload['summary'].get('finding_states', {})}",
        f"- Proof modes: {payload['summary'].get('proof_modes', {})}",
        "",
        "## Findings",
        "",
    ]
    for finding in payload["findings"]:
        lines.append(f"### {finding['title']}")
        lines.append("")
        lines.append(f"- Profile: {finding['profile']}")
        lines.append(f"- Status: {finding['status']}")
        lines.append(f"- Finding state: {finding['finding_state']}")
        lines.append(f"- Severity: {finding['severity']}")
        lines.append(f"- Confidence: {finding['confidence']}")
        lines.append(f"- Evidence level: {finding['evidence_level']}")
        lines.append(f"- Proof mode: {finding.get('proof_mode', 'structural')}")
        lines.append(f"- Target resource: {finding['target_resource']}")
        lines.append(f"- Entry point: {finding.get('entry_point') or '-'}")
        lines.append(f"- Principal multiplicity: {finding.get('principal_multiplicity', 1)}")
        lines.append(f"- Entry points: {', '.join(finding.get('entry_points') or []) if finding.get('entry_points') else '-'}")
        lines.append(f"- Distinct path key: {finding.get('distinct_path_key') or '-'}")
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


def _build_distinct_path_key(report: dict, target_resource: str) -> str:
    parts: list[str] = []
    for step in report.get("steps", []):
        action = step.get("action", {})
        details = ((step.get("observation") or {}).get("details") or {})
        target = action.get("target")
        normalized_target = "objective_target" if target == target_resource else _short_ref(target or "-")
        token_parts = [
            action.get("action_type") or "-",
            action.get("tool") or "-",
            normalized_target,
        ]
        simulated = details.get("simulated_policy_result") or {}
        decision = simulated.get("decision")
        if decision:
            token_parts.append(str(decision).lower())
        token = ":".join(token_parts)
        if not parts or parts[-1] != token:
            parts.append(token)
    return " | ".join(parts)
