from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.domain import Action, ActionType, Observation, Scope, Technique


@dataclass
class BlindRealRuntime:
    target_arn: str
    profile_name: str
    discovery_snapshot: dict[str, Any]
    scope: Scope
    entry_identities: list[str]
    state: dict[str, Any]

    @classmethod
    def build(
        cls,
        *,
        plan: dict[str, Any],
        discovery_snapshot: dict[str, Any],
        scope: Scope,
        entry_identities: list[str],
    ) -> "BlindRealRuntime":
        identities = {
            identity: {"active": True}
            for identity in entry_identities
        }
        return cls(
            target_arn=plan["resource_arn"],
            profile_name=plan["profile"],
            discovery_snapshot=discovery_snapshot,
            scope=scope,
            entry_identities=entry_identities,
            state={
                "flags": [],
                "identities": identities,
                "discovered_roles": cls._discovered_roles(discovery_snapshot),
            },
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "name": "blind-real-runtime",
            "description": "Runtime action space derived from real discovery.",
            "profile": self.profile_name,
            "target_arn": self.target_arn,
            "mode": "blind_real",
        }

    def state_copy(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.state))

    def has_flag(self, flag: str) -> bool:
        return flag in self.state.get("flags", [])

    def canonicalize(self, value):
        return value

    def enumerate_actions(self, snapshot) -> list[Action]:
        actions: list[Action] = []
        region = _resource_region(self.target_arn) or (self.scope.allowed_regions[0] if self.scope.allowed_regions else "us-east-1")
        discovered_roles = self.state.get("discovered_roles", [])
        for actor, actor_state in self.state.get("identities", {}).items():
            if not actor_state.get("active", False):
                continue
            if actor_state.get("extracted", False):
                # Bloco 6c/6d: extracted identities may only assume roles — no enumeration or mutation
                actions.extend(self._assume_role_actions(actor, region, discovered_roles))
                continue
            if self.profile_name in _PIVOT_PROFILES:
                # Bloco 6c/6d: non-extracted actors in pivot profiles may only enumerate + read pivot resource.
                # The target role must be assumed via the extracted identity, not directly.
                actions.extend(self._enumeration_actions(actor, region))
                actions.extend(self._target_access_actions(actor, region))
                continue
            actions.extend(self._enumeration_actions(actor, region))
            actions.extend(self._assume_role_actions(actor, region, discovered_roles))
            actions.extend(self._target_access_actions(actor, region))
            actions.extend(self._policy_abuse_actions(actor, region, discovered_roles))
        return actions

    def observe_real(self, action: Action, details: dict[str, Any]) -> Observation:
        success = True
        state = self.state
        if action.action_type == ActionType.ASSUME_ROLE and details.get("granted_role"):
            granted_role = details["granted_role"]
            state.setdefault("identities", {}).setdefault(granted_role, {"active": True})
            state["identities"][granted_role]["active"] = True
        if action.action_type == ActionType.ENUMERATE and details.get("discovered_roles"):
            for role_arn in details["discovered_roles"]:
                if role_arn not in state.setdefault("discovered_roles", []):
                    state["discovered_roles"].append(role_arn)
        if action.action_type == ActionType.ACCESS_RESOURCE and action.target == self.target_arn:
            flags = state.setdefault("flags", [])
            if "target_accessed" not in flags:
                flags.append("target_accessed")
        # Bloco 8: registra identidade sintética — qualquer tool com produces: credential_pivot
        # O synthetic_actor é setado por _apply_produces no executor, não mais hardcoded aqui.
        if details.get("synthetic_actor"):
            synthetic_actor = details["synthetic_actor"]
            identities = state.setdefault("identities", {})
            if synthetic_actor not in identities:
                identities[synthetic_actor] = {"active": True, "extracted": True}
        return Observation(success=success, details=details)

    def _enumeration_actions(self, actor: str, region: str) -> list[Action]:
        if "iam" not in self.scope.allowed_services:
            return []
        return [
            Action(
                action_type=ActionType.ENUMERATE,
                actor=actor,
                target=None,
                parameters={"service": "iam", "region": region},
                tool="iam_list_roles",
                technique=_technique("T1087.004", "Cloud Account Discovery"),
            )
        ]

    def _assume_role_actions(self, actor: str, region: str, roles: list[str]) -> list[Action]:
        if "iam" not in self.scope.allowed_services:
            return []
        actions: list[Action] = []
        for role_arn in roles:
            if role_arn == actor or _is_noise_role(role_arn):
                continue
            actions.append(
                Action(
                    action_type=ActionType.ASSUME_ROLE,
                    actor=actor,
                    target=role_arn,
                    parameters={
                        "service": "iam",
                        "region": region,
                        "role_arn": role_arn,
                        "policy_action": _policy_action_for_target(self.target_arn),
                        "policy_resource": _policy_resource_for_target(self.target_arn),
                    },
                    tool="iam_passrole",
                    technique=_technique("T1098", "Account Manipulation"),
                )
            )
        return actions

    def _target_access_actions(self, actor: str, region: str) -> list[Action]:
        target = self.target_arn
        if self.profile_name == "aws-iam-role-chaining":
            return []
        # Bloco 6c/6d: credential pivot variants — entry reads intermediate resource.
        if self.profile_name == "aws-credential-pivot":
            return self._pivot_secret_read_actions(actor, region)
        if self.profile_name == "aws-credential-pivot-ssm":
            return self._pivot_ssm_read_actions(actor, region)
        if self.profile_name == "aws-credential-pivot-s3":
            return self._pivot_s3_read_actions(actor, region)
        if self.profile_name == "aws-iam-create-access-key-pivot":
            return self._create_access_key_actions(actor, region)
        # Bloco 6b: credential_access_direct — entry user reads secret/SSM directly.
        # Skip the simulation probe and fall through to the type-based real read actions.
        is_direct_credential_access = self.profile_name in (
            "aws-credential-access-secret",
        )
        if ":user/" in actor and not is_direct_credential_access:
            return [
                Action(
                    action_type=ActionType.ACCESS_RESOURCE,
                    actor=actor,
                    target=target,
                    parameters={
                        "service": _service_for_target(target),
                        "region": region,
                        "policy_action": _policy_action_for_target(target),
                        "policy_resource": _policy_resource_for_target(target),
                    },
                    tool="iam_simulate_target_access",
                    technique=_technique("T1526", "Cloud Service Discovery"),
                )
            ]
        if target.startswith("arn:aws:s3:::"):
            bucket, object_key = _split_s3_arn(target)
            if object_key:
                return [
                    Action(
                        action_type=ActionType.ACCESS_RESOURCE,
                        actor=actor,
                        target=target,
                        parameters={
                            "service": "s3",
                            "region": region,
                            "bucket": bucket,
                            "object_key": object_key,
                        },
                        tool="s3_read_sensitive",
                        technique=_technique("T1530", "Data from Cloud Storage"),
                    )
                ]
            return [
                Action(
                    action_type=ActionType.ACCESS_RESOURCE,
                    actor=actor,
                    target=target,
                    parameters={"service": "s3", "region": region, "bucket": bucket},
                    tool="s3_list_bucket",
                    technique=_technique("T1530", "Data from Cloud Storage"),
                )
            ]
        if ":secret:" in target:
            secret_id = target.split(":secret:", 1)[1]
            return [
                Action(
                    action_type=ActionType.ACCESS_RESOURCE,
                    actor=actor,
                    target=target,
                    parameters={"service": "secretsmanager", "region": region, "secret_id": secret_id},
                    tool="secretsmanager_read_secret",
                    technique=_technique("T1552", "Unsecured Credentials"),
                )
            ]
        if ":parameter/" in target:
            parameter_name = "/" + target.split(":parameter/", 1)[1]
            return [
                Action(
                    action_type=ActionType.ACCESS_RESOURCE,
                    actor=actor,
                    target=target,
                    parameters={"service": "ssm", "region": region, "parameter": parameter_name},
                    tool="ssm_read_parameter",
                    technique=_technique("T1552", "Unsecured Credentials"),
                )
            ]
        return []

    def _pivot_secret_read_actions(self, actor: str, region: str) -> list[Action]:
        """Bloco 6c: oferece secretsmanager_read_secret para secrets onde actor está em readable_by."""
        actions: list[Action] = []
        for resource in self.discovery_snapshot.get("resources", []):
            if resource.get("resource_type") != "secret.secrets_manager":
                continue
            readable_by = (resource.get("metadata") or {}).get("readable_by", [])
            if actor not in readable_by:
                continue
            secret_arn = resource["identifier"]
            # Use full ARN as secret_id so IAM policy matching works regardless of name suffix
            secret_id = secret_arn
            actions.append(
                Action(
                    action_type=ActionType.ACCESS_RESOURCE,
                    actor=actor,
                    target=secret_arn,
                    parameters={"service": "secretsmanager", "region": region, "secret_id": secret_id},
                    tool="secretsmanager_read_secret",
                    technique=_technique("T1552", "Unsecured Credentials"),
                )
            )
        return actions

    def _pivot_ssm_read_actions(self, actor: str, region: str) -> list[Action]:
        """Bloco 6d: oferece ssm_read_parameter para params SSM onde actor está em readable_by."""
        actions: list[Action] = []
        for resource in self.discovery_snapshot.get("resources", []):
            if resource.get("resource_type") != "secret.ssm_parameter":
                continue
            readable_by = (resource.get("metadata") or {}).get("readable_by", [])
            if actor not in readable_by:
                continue
            param_arn = resource["identifier"]
            # Deriva nome do parâmetro a partir do ARN: arn:aws:ssm:region:acct:parameter/path
            if ":parameter/" in param_arn:
                param_name = "/" + param_arn.split(":parameter/", 1)[1]
            else:
                param_name = param_arn
            actions.append(
                Action(
                    action_type=ActionType.ACCESS_RESOURCE,
                    actor=actor,
                    target=param_arn,
                    parameters={"service": "ssm", "region": region, "name": param_name},
                    tool="ssm_read_parameter",
                    technique=_technique("T1552", "Unsecured Credentials"),
                )
            )
        return actions

    def _pivot_s3_read_actions(self, actor: str, region: str) -> list[Action]:
        """Bloco 6d: oferece s3_read_sensitive para objects S3 onde actor está em readable_by."""
        actions: list[Action] = []
        for resource in self.discovery_snapshot.get("resources", []):
            if resource.get("resource_type") != "data_store.s3_object":
                continue
            readable_by = (resource.get("metadata") or {}).get("readable_by", [])
            if actor not in readable_by:
                continue
            obj_arn = resource["identifier"]
            bucket, object_key = _split_s3_arn(obj_arn)
            if not object_key:
                continue
            actions.append(
                Action(
                    action_type=ActionType.ACCESS_RESOURCE,
                    actor=actor,
                    target=obj_arn,
                    parameters={"service": "s3", "region": region, "bucket": bucket, "object_key": object_key},
                    tool="s3_read_sensitive",
                    technique=_technique("T1530", "Data from Cloud Storage"),
                )
            )
        return actions

    def _create_access_key_actions(self, actor: str, region: str) -> list[Action]:
        """Bloco 6d: oferece iam_create_access_key para users onde actor está em createkey_by."""
        actions: list[Action] = []
        for resource in self.discovery_snapshot.get("resources", []):
            if resource.get("resource_type") != "identity.user":
                continue
            createkey_by = (resource.get("metadata") or {}).get("createkey_by", [])
            if actor not in createkey_by:
                continue
            user_arn = resource["identifier"]
            if user_arn == actor:
                continue
            actions.append(
                Action(
                    action_type=ActionType.ACCESS_RESOURCE,
                    actor=actor,
                    target=user_arn,
                    parameters={"service": "iam", "region": region, "user_arn": user_arn},
                    tool="iam_create_access_key",
                    technique=_technique("T1098", "Account Manipulation"),
                )
            )
        return actions

    def _policy_abuse_actions(self, actor: str, region: str, roles: list[str]) -> list[Action]:
        if "iam" not in self.scope.allowed_services:
            return []
        abuse_actions: list[Action] = []
        profile_tools = {
            "aws-iam-create-policy-version-privesc": ["iam_create_policy_version_mutate"],
            "aws-iam-attach-role-policy-privesc": ["iam_attach_role_policy_mutate", "iam_attach_role_policy"],
            "aws-iam-pass-role-privesc": ["iam_pass_role_service_create"],
        }.get(
            self.profile_name,
            ["iam_create_policy_version_mutate", "iam_attach_role_policy", "iam_pass_role_service_create"],
        )
        # Always include the objective target so the required tool appears at step 0,
        # even before discovered_roles is populated via iam_list_roles.
        candidate_roles = list(roles)
        if ":role/" in self.target_arn and self.target_arn not in candidate_roles:
            candidate_roles = [self.target_arn] + candidate_roles
        for role_arn in candidate_roles:
            if role_arn == actor or _is_noise_role(role_arn):
                continue
            for tool in profile_tools:
                params: dict[str, Any] = {"service": "iam", "region": region, "role_arn": role_arn}
                # For CreatePolicyVersion mutations, pre-resolve the policy ARN from discovery
                # so the executor does not need iam:ListAttachedRolePolicies at runtime.
                if tool == "iam_create_policy_version_mutate":
                    policy_arn = self._customer_policy_arn_for_role(role_arn)
                    if policy_arn:
                        params["policy_arn"] = policy_arn
                abuse_actions.append(
                    Action(
                        action_type=ActionType.ACCESS_RESOURCE,
                        actor=actor,
                        target=role_arn,
                        parameters=params,
                        tool=tool,
                        technique=_policy_probe_technique(tool),
                    )
                )
        return abuse_actions

    def _customer_policy_arn_for_role(self, role_arn: str) -> str | None:
        """Returns the first customer-managed policy ARN attached to the role from discovery."""
        for resource in self.discovery_snapshot.get("resources", []):
            if resource.get("identifier") == role_arn:
                arns = (resource.get("metadata") or {}).get("attached_policy_arns", [])
                for arn in arns:
                    if not arn.startswith("arn:aws:iam::aws:policy/"):
                        return arn
        return None

    def _account_id(self) -> str:
        return (
            self.discovery_snapshot.get("caller_identity", {}).get("Account")
            or (self.scope.aws_account_ids[0] if self.scope.aws_account_ids else "000000000000")
        )

    @staticmethod
    def _discovered_roles(discovery_snapshot: dict[str, Any]) -> list[str]:
        return [
            resource["identifier"]
            for resource in discovery_snapshot.get("resources", [])
            if resource.get("resource_type") == "identity.role" and not _is_noise_role(resource.get("identifier", ""))
        ]


# Perfis que usam pivot de credencial — entry não pode assumir role diretamente
_PIVOT_PROFILES = frozenset({
    "aws-credential-pivot",
    "aws-credential-pivot-ssm",
    "aws-credential-pivot-s3",
    "aws-iam-create-access-key-pivot",
})


def _split_s3_arn(resource_arn: str) -> tuple[str, str | None]:
    path = resource_arn.replace("arn:aws:s3:::", "", 1)
    if "/" not in path:
        return path, None
    return path.split("/", 1)


def _resource_region(resource_arn: str) -> str | None:
    if not resource_arn.startswith("arn:aws:"):
        return None
    parts = resource_arn.split(":")
    if len(parts) < 4:
        return None
    return parts[3] or None


def _policy_probe_technique(tool: str) -> Technique:
    mapping = {
        "iam_create_policy_version": _technique("T1484.001", "Domain Policy Modification"),
        "iam_create_policy_version_mutate": _technique("T1484.001", "Domain Policy Modification"),
        "iam_attach_role_policy": _technique("T1098", "Account Manipulation"),
        "iam_attach_role_policy_mutate": _technique("T1098", "Account Manipulation"),
        "iam_pass_role_service_create": _technique("T1098", "Account Manipulation"),
    }
    return mapping[tool]


def _policy_action_for_target(resource_arn: str) -> str:
    if resource_arn.startswith("arn:aws:s3:::"):
        return "s3:GetObject"
    if ":secret:" in resource_arn:
        return "secretsmanager:GetSecretValue"
    if ":parameter/" in resource_arn:
        return "ssm:GetParameter"
    return "iam:ListRoles"


def _policy_resource_for_target(resource_arn: str) -> str:
    return resource_arn


def _service_for_target(resource_arn: str) -> str:
    if resource_arn.startswith("arn:aws:s3:::"):
        return "s3"
    if ":secret:" in resource_arn:
        return "secretsmanager"
    if ":parameter/" in resource_arn:
        return "ssm"
    if ":role/" in resource_arn:
        return "iam"
    return "aws"


def _technique(mitre_id: str, mitre_name: str) -> Technique:
    return Technique(
        mitre_id=mitre_id,
        mitre_name=mitre_name,
        tactic="Discovery",
        platform="AWS",
    )


def _is_noise_role(role_arn: str) -> bool:
    return ":role/aws-service-role/" in role_arn
