from __future__ import annotations

from dataclasses import dataclass, field

from core.domain import Scope, TargetType
from execution.aws_client import AwsClient, Boto3AwsClient


@dataclass
class PreflightResult:
    ok: bool
    details: dict = field(default_factory=dict)


def run_preflight(scope: Scope, client: AwsClient | None = None) -> PreflightResult:
    if scope.target != TargetType.AWS or scope.dry_run:
        return PreflightResult(ok=True, details={"mode": "skipped"})

    aws_client = client or Boto3AwsClient()
    region = scope.allowed_regions[0]
    identity = aws_client.get_caller_identity(region=region)
    account_id = identity["Account"]
    if account_id not in scope.aws_account_ids:
        return PreflightResult(
            ok=False,
            details={
                "reason": "account_not_allowed",
                "account_id": account_id,
                "allowed_accounts": scope.aws_account_ids,
            },
        )

    details = {
        "caller_identity": identity,
        "account_id": account_id,
        "region": region,
    }

    if "iam" in scope.allowed_services:
        roles = set(aws_client.list_roles(region=region))
        required_roles = {
            resource for resource in scope.allowed_resources if ":role/" in resource
        }
        missing_roles = sorted(required_roles - roles)
        details["required_roles"] = sorted(required_roles)
        if missing_roles:
            return PreflightResult(
                ok=False,
                details={
                    **details,
                    "reason": "required_roles_missing",
                    "missing_roles": missing_roles,
                },
            )

    return PreflightResult(ok=True, details=details)
