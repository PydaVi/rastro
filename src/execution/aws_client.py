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

    def list_objects(
        self,
        region: str,
        bucket: str,
        prefix: Optional[str] = None,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[str]:
        ...

    def list_buckets(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[str]:
        ...

    def list_secrets(
        self,
        region: str,
        name_prefix: Optional[str] = None,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[str]:
        ...

    def get_secret_value(
        self,
        region: str,
        secret_id: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        ...

    def list_parameters_by_path(
        self,
        region: str,
        path: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[str]:
        ...

    def get_parameter(
        self,
        region: str,
        name: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        ...

    def get_instance_profile(
        self,
        region: str,
        instance_profile_name: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        ...

    def list_instance_profile_associations(
        self,
        region: str,
        instance_profile_arn: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def describe_instance(
        self,
        region: str,
        instance_id: str,
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

    def list_objects(
        self,
        region: str,
        bucket: str,
        prefix: Optional[str] = None,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[str]:
        client = self._session(credentials).client("s3", region_name=region)
        paginator = client.get_paginator("list_objects_v2")
        keys: list[str] = []
        paginate_kwargs = {"Bucket": bucket}
        if prefix:
            paginate_kwargs["Prefix"] = prefix
        for page in paginator.paginate(**paginate_kwargs):
            for obj in page.get("Contents", []):
                key = obj.get("Key")
                if key:
                    keys.append(key)
        return keys

    def list_buckets(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[str]:
        client = self._session(credentials).client("s3", region_name=region)
        response = client.list_buckets()
        buckets: list[str] = []
        for bucket in response.get("Buckets", []):
            name = bucket.get("Name")
            if name:
                buckets.append(name)
        return buckets

    def list_secrets(
        self,
        region: str,
        name_prefix: Optional[str] = None,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[str]:
        client = self._session(credentials).client("secretsmanager", region_name=region)
        paginator = client.get_paginator("list_secrets")
        names: list[str] = []
        paginate_kwargs = {}
        if name_prefix:
            paginate_kwargs["Filters"] = [{"Key": "name", "Values": [name_prefix]}]
        for page in paginator.paginate(**paginate_kwargs):
            for secret in page.get("SecretList", []):
                name = secret.get("Name")
                if name:
                    names.append(name)
        return names

    def get_secret_value(
        self,
        region: str,
        secret_id: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        client = self._session(credentials).client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_id)
        return {
            "ARN": response.get("ARN"),
            "Name": response.get("Name"),
            "VersionId": response.get("VersionId"),
            "SecretString": response.get("SecretString"),
        }

    def list_parameters_by_path(
        self,
        region: str,
        path: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[str]:
        client = self._session(credentials).client("ssm", region_name=region)
        paginator = client.get_paginator("get_parameters_by_path")
        names: list[str] = []
        for page in paginator.paginate(Path=path, Recursive=True, WithDecryption=False):
            for param in page.get("Parameters", []):
                name = param.get("Name")
                if name:
                    names.append(name)
        return names

    def get_parameter(
        self,
        region: str,
        name: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        client = self._session(credentials).client("ssm", region_name=region)
        response = client.get_parameter(Name=name, WithDecryption=True)
        parameter = response.get("Parameter", {}) if response else {}
        return {
            "ARN": parameter.get("ARN"),
            "Name": parameter.get("Name"),
            "Type": parameter.get("Type"),
            "Value": parameter.get("Value"),
            "Version": parameter.get("Version"),
        }

    def get_instance_profile(
        self,
        region: str,
        instance_profile_name: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        client = self._session(credentials).client("iam", region_name=region)
        response = client.get_instance_profile(InstanceProfileName=instance_profile_name)
        profile = response.get("InstanceProfile", {}) if response else {}
        roles = [role.get("Arn") for role in profile.get("Roles", []) if role.get("Arn")]
        return {
            "Arn": profile.get("Arn"),
            "InstanceProfileName": profile.get("InstanceProfileName"),
            "Roles": roles,
        }

    def list_instance_profile_associations(
        self,
        region: str,
        instance_profile_arn: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("ec2", region_name=region)
        paginator = client.get_paginator("describe_iam_instance_profile_associations")
        associations: list[Dict[str, Any]] = []
        for page in paginator.paginate():
            for association in page.get("IamInstanceProfileAssociations", []):
                profile = association.get("IamInstanceProfile", {})
                if profile.get("Arn") != instance_profile_arn:
                    continue
                instance_id = association.get("InstanceId")
                state = association.get("State")
                if instance_id:
                    associations.append(
                        {
                            "InstanceId": instance_id,
                            "State": state,
                            "AssociationId": association.get("AssociationId"),
                        }
                    )
        return associations

    def describe_instance(
        self,
        region: str,
        instance_id: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        client = self._session(credentials).client("ec2", region_name=region)
        response = client.describe_instances(InstanceIds=[instance_id])
        reservations = response.get("Reservations", []) if response else []
        for reservation in reservations:
            for instance in reservation.get("Instances", []):
                if instance.get("InstanceId") != instance_id:
                    continue
                return {
                    "InstanceId": instance.get("InstanceId"),
                    "PublicIpAddress": instance.get("PublicIpAddress"),
                    "PrivateIpAddress": instance.get("PrivateIpAddress"),
                    "State": (instance.get("State") or {}).get("Name"),
                    "IamInstanceProfileArn": (instance.get("IamInstanceProfile") or {}).get("Arn"),
                    "MetadataOptions": instance.get("MetadataOptions") or {},
                }
        return {}

    def _session(self, credentials: Optional[AwsCredentials] = None):
        import boto3

        if not credentials:
            return boto3.session.Session()
        return boto3.session.Session(
            aws_access_key_id=credentials.get("AccessKeyId"),
            aws_secret_access_key=credentials.get("SecretAccessKey"),
            aws_session_token=credentials.get("SessionToken"),
        )
