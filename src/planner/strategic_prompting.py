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
1. For each entry_identity in the input, examine its policy_permissions when available (actual \
policy documents with Effect/Action/Resource/Condition). If policy_permissions is absent, fall back \
to reasoning from attached_policy_names and inline_policy_names.
2. When policy_permissions is present, reason about ACTUAL grants:
   - A statement with Effect=Allow, Action=iam:* (or iam:CreatePolicyVersion, iam:AttachRolePolicy, \
     iam:PutRolePolicy, etc.) and Resource=* with NO Condition is directly exploitable for iam_privesc.
   - A statement with Effect=Allow, Action=sts:AssumeRole and Resource=<role ARN> enables role_chain.
   - A statement with Effect=Allow, Action=secretsmanager:GetSecretValue or ssm:GetParameter enables \
     credential_access.
   - A Condition block (aws:RequestedRegion, StringEquals, etc.) may restrict the exploit — note it.
3. If policy_permissions is absent, infer from policy names (e.g. "iam-CreatePolicyVersion" → grants \
iam:CreatePolicyVersion).
4. Identify what targets are reachable given those permissions (roles, secrets, S3 objects, etc.).
5. Generate one hypothesis per (entry_identity, attack_path) pair.
6. Prefer hypotheses with concrete IAM API calls in attack_steps.

Focus especially on: CreatePolicyVersion, AttachRolePolicy, PassRole, CreateAccessKey, \
PutRolePolicy, AddUserToGroup, UpdateLoginProfile, SetDefaultPolicyVersion, \
AssumeRole, GetSecretValue, GetParameter.

IMPORTANT — target ARN selection rules:

STEP 1 — Read the Resource field in policy_permissions first:
- If a statement has a specific Resource ARN (not "*"), that ARN IS the target. Use it directly. \
Do not substitute a "more privileged-looking" resource. The Resource field tells you exactly \
what the policy grants access to.
- Only when Resource = "*" should you choose a target from the resources list.

STEP 2 — When Resource = "*", choose by attack type:
- iam_privesc via role mutation (CreatePolicyVersion, AttachRolePolicy, PutRolePolicy, \
SetDefaultPolicyVersion, UpdatingAssumeRolePolicy): pick an IAM ROLE ARN \
(arn:aws:iam::ACCOUNT:role/ROLE_NAME) from the resources list. \
Never use a policy ARN (arn:aws:iam::ACCOUNT:policy/...) as target.
- iam_privesc via user manipulation (CreateAccessKey, CreateLoginProfile, UpdateLoginProfile, \
AttachUserPolicy, PutUserPolicy): pick an IAM USER ARN \
(arn:aws:iam::ACCOUNT:user/USER_NAME) from the resources list. \
Never invent ARNs like "any-user" or "any-admin-user".
- role_chain: pick an IAM role ARN from the resources list that the entry identity can assume.
- credential_access: pick a Secrets Manager or SSM ARN from the resources list.
- data_exfil: pick an S3 bucket or object ARN from the resources list.
- compute_pivot (PassRole to Lambda, EC2, CodeBuild, Glue, SageMaker): pick an IAM role ARN \
from the resources list that will be passed to the service.

CRITICAL: Only use ARNs that appear in the provided resources. Do NOT invent ARNs. \
If no real ARN fits, omit the hypothesis entirely.

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
        # Bloco 4 — policy documents (highest signal)
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
