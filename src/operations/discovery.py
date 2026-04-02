from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

from execution.aws_client import AwsClient, Boto3AwsClient
from operations.catalog import resolve_bundle
from operations.models import AuthorizationConfig, TargetConfig
from operations.service import validate_profile_access, validate_target


DEFAULT_SSM_DISCOVERY_PREFIXES = ["/prod", "/app", "/finance", "/shared"]


@dataclass
class DiscoveryLimits:
    max_roles: int = 100
    max_buckets: int = 50
    max_objects_per_bucket: int = 20
    max_secrets: int = 100
    max_parameters_per_prefix: int = 100


def _is_service_linked_role(role_arn: str) -> bool:
    return ":role/aws-service-role/" in role_arn


def _ssm_parameter_arn(region: str, account_id: str, name: str) -> str:
    normalized = name if name.startswith("/") else f"/{name}"
    return f"arn:aws:ssm:{region}:{account_id}:parameter{normalized}"


def run_foundation_discovery(
    *,
    bundle_name: str,
    target: TargetConfig,
    authorization: AuthorizationConfig,
    output_dir: Path,
    client: AwsClient | None = None,
    limits: DiscoveryLimits | None = None,
) -> tuple[Path, Path, dict]:
    issues = validate_target(target)
    if issues:
        raise ValueError("; ".join(issues))

    profiles = resolve_bundle(bundle_name)
    for profile in profiles:
        validate_profile_access(profile.name, authorization)

    aws_client = client or Boto3AwsClient()
    effective_limits = limits or DiscoveryLimits()
    region = target.allowed_regions[0]
    caller_identity = aws_client.get_caller_identity(region=region)

    resources: list[dict] = []
    evidence: list[dict] = []
    services_scanned: list[str] = []

    roles = aws_client.list_roles(region=region)[: effective_limits.max_roles]
    services_scanned.append("iam")
    evidence.append({"service": "iam", "api_calls": ["sts:GetCallerIdentity", "iam:ListRoles"]})
    for role_arn in roles:
        if _is_service_linked_role(role_arn):
            continue
        resources.append(
            {
                "service": "iam",
                "resource_type": "identity.role",
                "identifier": role_arn,
                "region": region,
                "metadata": {"is_service_linked": False},
                "source": "aws_api",
            }
        )

    buckets = aws_client.list_buckets(region=region)[: effective_limits.max_buckets]
    services_scanned.append("s3")
    evidence.append({"service": "s3", "api_calls": ["s3:ListBuckets", "s3:ListBucket"]})
    for bucket_name in buckets:
        bucket_arn = f"arn:aws:s3:::{bucket_name}"
        resources.append(
            {
                "service": "s3",
                "resource_type": "data_store.s3_bucket",
                "identifier": bucket_arn,
                "region": region,
                "metadata": {},
                "source": "aws_api",
            }
        )
        object_keys = aws_client.list_objects(region=region, bucket=bucket_name)[
            : effective_limits.max_objects_per_bucket
        ]
        for object_key in object_keys:
            resources.append(
                {
                    "service": "s3",
                    "resource_type": "data_store.s3_object",
                    "identifier": f"{bucket_arn}/{object_key}",
                    "region": region,
                    "metadata": {"bucket": bucket_name, "object_key": object_key},
                    "source": "aws_api",
                }
            )

    secrets = aws_client.list_secrets(region=region)[: effective_limits.max_secrets]
    services_scanned.append("secretsmanager")
    evidence.append({"service": "secretsmanager", "api_calls": ["secretsmanager:ListSecrets"]})
    for secret_name in secrets:
        resources.append(
            {
                "service": "secretsmanager",
                "resource_type": "secret.secrets_manager",
                "identifier": f"arn:aws:secretsmanager:{region}:{target.accounts[0]}:secret:{secret_name}",
                "region": region,
                "metadata": {"name": secret_name},
                "source": "aws_api",
            }
        )

    ssm_prefixes = _resolve_ssm_discovery_prefixes(target=target, profiles=profiles)
    services_scanned.append("ssm")
    evidence.append({"service": "ssm", "api_calls": ["ssm:GetParametersByPath"]})
    for path_prefix in ssm_prefixes:
        parameter_names = aws_client.list_parameters_by_path(region=region, path=path_prefix)[
            : effective_limits.max_parameters_per_prefix
        ]
        for name in parameter_names:
            parameter_arn = _ssm_parameter_arn(region, target.accounts[0], name)
            resources.append(
                {
                    "service": "ssm",
                    "resource_type": "secret.ssm_parameter",
                    "identifier": parameter_arn,
                    "region": region,
                    "metadata": {"name": name, "path_prefix": path_prefix},
                    "source": "aws_api",
                }
            )

    summary = {
        "roles": sum(1 for resource in resources if resource["resource_type"] == "identity.role"),
        "buckets": sum(1 for resource in resources if resource["resource_type"] == "data_store.s3_bucket"),
        "objects": sum(1 for resource in resources if resource["resource_type"] == "data_store.s3_object"),
        "secrets": sum(
            1 for resource in resources if resource["resource_type"] == "secret.secrets_manager"
        ),
        "parameters": sum(
            1 for resource in resources if resource["resource_type"] == "secret.ssm_parameter"
        ),
    }

    snapshot = {
        "target": target.name,
        "bundle": bundle_name,
        "collected_at": datetime.now(UTC).isoformat(),
        "caller_identity": caller_identity,
        "services_scanned": services_scanned,
        "regions_scanned": target.allowed_regions,
        "resources": resources,
        "evidence": evidence,
        "summary": summary,
        "discovery_config": {
            "ssm_prefixes": ssm_prefixes,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "discovery.json"
    md_path = output_dir / "discovery.md"
    json_path.write_text(json.dumps(snapshot, indent=2))
    md_path.write_text(_render_discovery_markdown(snapshot))
    return json_path, md_path, snapshot


def _render_discovery_markdown(snapshot: dict) -> str:
    summary = snapshot["summary"]
    lines = [
        "# Discovery Summary",
        "",
        f"- Target: {snapshot['target']}",
        f"- Bundle: {snapshot['bundle']}",
        f"- Collected at: {snapshot['collected_at']}",
        f"- Services scanned: {snapshot['services_scanned']}",
        f"- Regions scanned: {snapshot['regions_scanned']}",
        f"- SSM prefixes: {snapshot.get('discovery_config', {}).get('ssm_prefixes', [])}",
        "",
        "## Summary",
        f"- Roles: {summary['roles']}",
        f"- Buckets: {summary['buckets']}",
        f"- Objects: {summary['objects']}",
        f"- Secrets: {summary['secrets']}",
        f"- Parameters: {summary['parameters']}",
        "",
        "## Sample Resources",
    ]
    for resource in snapshot["resources"][:15]:
        lines.append(
            f"- {resource['resource_type']}: {resource['identifier']}"
        )
    lines.append("")
    return "\n".join(lines)


def _resolve_ssm_discovery_prefixes(*, target: TargetConfig, profiles: list) -> list[str]:
    if target.discovery_ssm_prefixes:
        return sorted(set(target.discovery_ssm_prefixes))
    profile_prefixes = {
        prefix
        for profile in profiles
        for prefix in getattr(profile, "discovery_ssm_prefixes", [])
    }
    if profile_prefixes:
        return sorted(profile_prefixes)
    return list(DEFAULT_SSM_DISCOVERY_PREFIXES)
