from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.domain import Scope

STRATEGIC_SYSTEM_PROMPT = """\
You are an expert AWS red team planner. You receive a discovery snapshot of an AWS environment \
and must identify viable attack paths from each entry identity.

Valid attack_class values:
- iam_privesc: IAM privilege escalation (CreatePolicyVersion, AttachRolePolicy, PassRole, CreateAccessKey, etc.)
- role_chain: assume role chain to reach a privileged role
- credential_access: read secrets from Secrets Manager or SSM Parameter Store
- data_exfil: read sensitive data from S3
- compute_pivot: exploit EC2/Lambda execution role to gain privileges

Instructions:
1. MANDATORY: For each entry_identity in the input, check if it has `derived_attack_targets` in \
   its metadata. If present, you MUST generate at least one hypothesis for that identity — one per \
   (action, target_arn) pair in the list. Each entry gives you `action` and `target_arn` \
   PRE-COMPUTED from the policy documents. Use them directly. Do NOT substitute a different target.
2. If `derived_attack_targets` is absent, examine `policy_permissions` (actual policy documents). \
   Reason about ACTUAL grants:
   - Effect=Allow, Action=iam:CreatePolicyVersion/AttachRolePolicy/PutRolePolicy + Resource=* → \
     iam_privesc, pick a role ARN from the resources list as target.
   - Effect=Allow, Action=sts:AssumeRole + Resource=<role ARN> → role_chain to that role.
   - Effect=Allow, Action=secretsmanager:GetSecretValue or ssm:GetParameter → credential_access.
   - A Condition block may restrict the exploit — note it in reasoning.
3. If neither is available, infer from policy names (e.g. "iam-CreatePolicyVersion" → iam:CreatePolicyVersion).
4. Generate one hypothesis per (entry_identity, attack_path) pair.
5. Prefer hypotheses with concrete IAM API calls in attack_steps.

Focus especially on: CreatePolicyVersion, AttachRolePolicy, PassRole, CreateAccessKey, \
PutRolePolicy, AddUserToGroup, UpdateLoginProfile, SetDefaultPolicyVersion, \
AssumeRole, GetSecretValue, GetParameter.

IMPORTANT — target ARN rules:
- For iam_privesc (CreatePolicyVersion, AttachRolePolicy, PutRolePolicy, SetDefaultPolicyVersion, \
UpdatingAssumeRolePolicy, CreateAccessKey, CreateLoginProfile, UpdateLoginProfile, etc.): \
target must be an ARN visible in the resources list. \
For role mutations: use an IAM ROLE ARN (arn:aws:iam::ACCOUNT:role/ROLE_NAME). \
For user manipulations (CreateAccessKey, CreateLoginProfile, AttachUserPolicy): use an IAM USER ARN. \
Never use a policy ARN (arn:aws:iam::ACCOUNT:policy/...) as target.
- For role_chain: target must be an IAM role ARN visible in the resources list.
- For credential_access: target must be a Secrets Manager or SSM ARN visible in the resources list.
- For data_exfil: target must be an S3 bucket or object ARN visible in the resources list.
- For compute_pivot (PassRole to Lambda, EC2, CodeBuild, Glue, SageMaker): target must be an IAM \
role ARN visible in the resources list that will be passed to the service.
- Only use ARNs that appear in the provided resources. Do NOT invent ARNs.

Respond with valid JSON only. No markdown. No text outside JSON.

Response schema:
{
  "hypotheses": [
    {
      "entry_identity": "<ARN of attacker-controlled identity>",
      "target": "<ARN from the resources list — role, secret, S3 object, etc.>",
      "attack_class": "<iam_privesc|role_chain|credential_access|data_exfil|compute_pivot>",
      "attack_steps": ["<concrete step 1>", "<concrete step 2>"],
      "confidence": "<high|medium|low>",
      "reasoning": "<why this path is viable based on the observed policies or policy_permissions>"
    }
  ]
}

If no viable path exists for an entry identity, omit it. Return {"hypotheses": []} if nothing found.
"""

_PRIORITY_TYPES = {"identity.role", "identity.user"}
_DATA_TYPES = {
    "data_store.s3_bucket",
    "data_store.s3_object",
    "secret.secrets_manager",
    "secret.ssm_parameter",
    "compute.ec2_instance",
    "compute.lambda_function",
    "crypto.kms_key",
}


def _select_resources(resources: list[dict], limit: int) -> list[dict]:
    priority = [r for r in resources if r.get("resource_type") in _PRIORITY_TYPES]
    data = [r for r in resources if r.get("resource_type") in _DATA_TYPES]
    rest = [
        r
        for r in resources
        if r.get("resource_type") not in _PRIORITY_TYPES | _DATA_TYPES
    ]
    ordered = priority + data + rest
    return ordered[:limit]


def _compact_resource(r: dict) -> dict:
    meta = r.get("metadata", {}) or {}
    selected_meta: dict = {}
    for key in (
        # Bloco 4b — pre-computed attack targets (deterministic, highest priority)
        "derived_attack_targets",
        # Bloco 4 — policy documents
        "policy_permissions",
        # discovery enrichment fields
        "attached_policy_names",
        "attached_policy_arns",
        "inline_policy_names",
        # role-specific fields
        "policy_escalation_signals",
        "trust_principals",
        # legacy / alternative names
        "policy_names",
        "attached_policies",
        "inline_policies",
    ):
        if key in meta and meta[key]:
            selected_meta[key] = meta[key]
    out: dict = {
        "identifier": r.get("identifier", ""),
        "resource_type": r.get("resource_type", ""),
    }
    if selected_meta:
        out["metadata"] = selected_meta
    return out


def build_strategic_prompt(
    discovery_snapshot: dict,
    entry_identities: list[str],
    scope: "Scope",
) -> str:
    raw_resources: list[dict] = discovery_snapshot.get("resources", [])
    selected = _select_resources(raw_resources, 150)
    compact = [_compact_resource(r) for r in selected]

    scope_summary: dict = {}
    if hasattr(scope, "allowed_actions"):
        scope_summary["allowed_actions"] = list(scope.allowed_actions)
    if hasattr(scope, "allowed_resources"):
        scope_summary["allowed_resources"] = list(scope.allowed_resources)
    if hasattr(scope, "account_id"):
        scope_summary["account_id"] = scope.account_id

    payload = {
        "entry_identities": entry_identities,
        "scope": scope_summary,
        "resource_count": len(raw_resources),
        "resources_shown": len(compact),
        "resources": compact,
    }
    return json.dumps(payload, indent=2)
