from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


AwsCredentials = Dict[str, str]


class AwsClient(Protocol):
    def get_caller_identity(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        ...

    def list_roles(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[str]:
        ...

    def assume_role(
        self,
        region: str,
        role_arn: str,
        session_name: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        ...

    def simulate_principal_policy(
        self,
        region: str,
        policy_source_arn: str,
        action_names: list[str],
        resource_arns: list[str],
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        ...

    def get_object(
        self,
        region: str,
        bucket: str,
        object_key: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        ...


@dataclass
class Boto3AwsClient:
    def __post_init__(self) -> None:
        try:
            import boto3  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "boto3 não está instalado. Execute: pip install '.[aws]'"
            ) from exc

    def get_caller_identity(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        client = self._session(credentials).client("sts", region_name=region)
        return client.get_caller_identity()

    def list_roles(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[str]:
        client = self._session(credentials).client("iam", region_name=region)
        paginator = client.get_paginator("list_roles")
        roles: list[str] = []
        for page in paginator.paginate():
            for role in page.get("Roles", []):
                if role.get("Arn"):
                    roles.append(role["Arn"])
        return roles

    def assume_role(
        self,
        region: str,
        role_arn: str,
        session_name: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        client = self._session(credentials).client("sts", region_name=region)
        return client.assume_role(RoleArn=role_arn, RoleSessionName=session_name)

    def simulate_principal_policy(
        self,
        region: str,
        policy_source_arn: str,
        action_names: list[str],
        resource_arns: list[str],
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        client = self._session(credentials).client("iam", region_name=region)
        return client.simulate_principal_policy(
            PolicySourceArn=policy_source_arn,
            ActionNames=action_names,
            ResourceArns=resource_arns,
        )

    def get_object(
        self,
        region: str,
        bucket: str,
        object_key: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        client = self._session(credentials).client("s3", region_name=region)
        response = client.get_object(Bucket=bucket, Key=object_key)
        body = response.get("Body")
        preview = b""
        if body is not None:
            preview = body.read(256)
            body.close()
        return {
            "ContentLength": response.get("ContentLength"),
            "ETag": response.get("ETag"),
            "Preview": preview.decode("utf-8", errors="replace"),
        }

    def _session(self, credentials: Optional[AwsCredentials] = None):
        import boto3

        if not credentials:
            return boto3.session.Session()
        return boto3.session.Session(
            aws_access_key_id=credentials.get("AccessKeyId"),
            aws_secret_access_key=credentials.get("SecretAccessKey"),
            aws_session_token=credentials.get("SessionToken"),
        )
