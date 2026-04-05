from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


AwsCredentials = Dict[str, str]


class AwsClient(Protocol):
    def list_users(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[str]:
        ...

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

    def get_role_details(
        self,
        region: str,
        role_name: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
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

    def list_instance_profiles(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def list_instances(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def list_internet_gateways(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def list_route_tables(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def list_subnets(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def list_security_groups(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def list_load_balancers(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def list_rest_apis(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def list_api_stages(
        self,
        region: str,
        rest_api_id: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def list_target_groups(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def describe_target_health(
        self,
        region: str,
        target_group_arn: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def list_listeners(
        self,
        region: str,
        load_balancer_arn: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def list_listener_rules(
        self,
        region: str,
        listener_arn: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        ...

    def list_api_integrations(
        self,
        region: str,
        rest_api_id: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
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

    def list_users(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[str]:
        client = self._session(credentials).client("iam", region_name=region)
        paginator = client.get_paginator("list_users")
        users: list[str] = []
        for page in paginator.paginate():
            for user in page.get("Users", []):
                if user.get("Arn"):
                    users.append(user["Arn"])
        return users

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

    def get_role_details(
        self,
        region: str,
        role_name: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> Dict[str, Any]:
        client = self._session(credentials).client("iam", region_name=region)
        role = client.get_role(RoleName=role_name)["Role"]

        attached_policies: list[Dict[str, Any]] = []
        paginator = client.get_paginator("list_attached_role_policies")
        for page in paginator.paginate(RoleName=role_name):
            attached_policies.extend(page.get("AttachedPolicies", []))

        inline_policy_names: list[str] = []
        paginator = client.get_paginator("list_role_policies")
        for page in paginator.paginate(RoleName=role_name):
            inline_policy_names.extend(page.get("PolicyNames", []))

        return {
            "Arn": role.get("Arn"),
            "AssumeRolePolicyDocument": role.get("AssumeRolePolicyDocument"),
            "PermissionsBoundary": role.get("PermissionsBoundary"),
            "AttachedPolicies": attached_policies,
            "InlinePolicyNames": inline_policy_names,
        }

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
                    "SubnetId": instance.get("SubnetId"),
                    "VpcId": instance.get("VpcId"),
                    "SecurityGroupIds": [
                        group.get("GroupId")
                        for group in instance.get("SecurityGroups", [])
                        if group.get("GroupId")
                    ],
                    "IamInstanceProfileArn": (instance.get("IamInstanceProfile") or {}).get("Arn"),
                    "MetadataOptions": instance.get("MetadataOptions") or {},
                }
        return {}

    def list_instance_profiles(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("iam", region_name=region)
        paginator = client.get_paginator("list_instance_profiles")
        profiles: list[Dict[str, Any]] = []
        for page in paginator.paginate():
            for profile in page.get("InstanceProfiles", []):
                roles = [role.get("Arn") for role in profile.get("Roles", []) if role.get("Arn")]
                arn = profile.get("Arn")
                name = profile.get("InstanceProfileName")
                if arn and name:
                    profiles.append(
                        {
                            "Arn": arn,
                            "InstanceProfileName": name,
                            "Roles": roles,
                        }
                    )
        return profiles

    def list_instances(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("ec2", region_name=region)
        paginator = client.get_paginator("describe_instances")
        account_id = self.get_caller_identity(region, credentials).get("Account")
        instances: list[Dict[str, Any]] = []
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instance_id = instance.get("InstanceId")
                    if not instance_id:
                        continue
                    security_groups = [
                        group.get("GroupId")
                        for group in instance.get("SecurityGroups", [])
                        if group.get("GroupId")
                    ]
                    instances.append(
                        {
                            "InstanceId": instance_id,
                            "Arn": f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}",
                            "SubnetId": instance.get("SubnetId"),
                            "VpcId": instance.get("VpcId"),
                            "PublicIpAddress": instance.get("PublicIpAddress"),
                            "PrivateIpAddress": instance.get("PrivateIpAddress"),
                            "State": (instance.get("State") or {}).get("Name"),
                            "SecurityGroupIds": security_groups,
                            "IamInstanceProfileArn": (instance.get("IamInstanceProfile") or {}).get("Arn"),
                            "MetadataOptions": instance.get("MetadataOptions") or {},
                        }
                    )
        return instances

    def list_internet_gateways(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("ec2", region_name=region)
        response = client.describe_internet_gateways()
        gateways: list[Dict[str, Any]] = []
        for gateway in response.get("InternetGateways", []):
            gateway_id = gateway.get("InternetGatewayId")
            if not gateway_id:
                continue
            gateways.append(
                {
                    "InternetGatewayId": gateway_id,
                    "Attachments": gateway.get("Attachments", []),
                }
            )
        return gateways

    def list_route_tables(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("ec2", region_name=region)
        response = client.describe_route_tables()
        route_tables: list[Dict[str, Any]] = []
        for table in response.get("RouteTables", []):
            route_table_id = table.get("RouteTableId")
            if not route_table_id:
                continue
            route_tables.append(
                {
                    "RouteTableId": route_table_id,
                    "VpcId": table.get("VpcId"),
                    "Associations": table.get("Associations", []),
                    "Routes": table.get("Routes", []),
                }
            )
        return route_tables

    def list_subnets(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("ec2", region_name=region)
        response = client.describe_subnets()
        subnets: list[Dict[str, Any]] = []
        for subnet in response.get("Subnets", []):
            subnet_id = subnet.get("SubnetId")
            if not subnet_id:
                continue
            subnets.append(
                {
                    "SubnetId": subnet_id,
                    "VpcId": subnet.get("VpcId"),
                    "AvailabilityZone": subnet.get("AvailabilityZone"),
                    "MapPublicIpOnLaunch": subnet.get("MapPublicIpOnLaunch"),
                }
            )
        return subnets

    def list_security_groups(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("ec2", region_name=region)
        response = client.describe_security_groups()
        groups: list[Dict[str, Any]] = []
        for group in response.get("SecurityGroups", []):
            group_id = group.get("GroupId")
            if not group_id:
                continue
            groups.append(
                {
                    "GroupId": group_id,
                    "VpcId": group.get("VpcId"),
                    "GroupName": group.get("GroupName"),
                    "IpPermissions": group.get("IpPermissions", []),
                }
            )
        return groups

    def list_load_balancers(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("elbv2", region_name=region)
        paginator = client.get_paginator("describe_load_balancers")
        load_balancers: list[Dict[str, Any]] = []
        for page in paginator.paginate():
            for lb in page.get("LoadBalancers", []):
                arn = lb.get("LoadBalancerArn")
                if not arn:
                    continue
                load_balancers.append(
                    {
                        "LoadBalancerArn": arn,
                        "DNSName": lb.get("DNSName"),
                        "Scheme": lb.get("Scheme"),
                        "VpcId": lb.get("VpcId"),
                        "State": (lb.get("State") or {}).get("Code"),
                    }
                )
        return load_balancers

    def list_rest_apis(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("apigateway", region_name=region)
        paginator = client.get_paginator("get_rest_apis")
        apis: list[Dict[str, Any]] = []
        for page in paginator.paginate():
            for api in page.get("items", []):
                api_id = api.get("id")
                if not api_id:
                    continue
                apis.append(
                    {
                        "RestApiId": api_id,
                        "Arn": f"arn:aws:apigateway:{region}::/restapis/{api_id}",
                        "Name": api.get("name"),
                        "EndpointConfiguration": api.get("endpointConfiguration") or {},
                    }
                )
        return apis

    def list_api_stages(
        self,
        region: str,
        rest_api_id: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("apigateway", region_name=region)
        response = client.get_stages(restApiId=rest_api_id)
        stages: list[Dict[str, Any]] = []
        for stage in response.get("item", []):
            stage_name = stage.get("stageName")
            if not stage_name:
                continue
            stages.append(
                {
                    "StageName": stage_name,
                    "DeploymentId": stage.get("deploymentId"),
                }
            )
        return stages

    def list_target_groups(
        self,
        region: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("elbv2", region_name=region)
        paginator = client.get_paginator("describe_target_groups")
        groups: list[Dict[str, Any]] = []
        for page in paginator.paginate():
            for group in page.get("TargetGroups", []):
                arn = group.get("TargetGroupArn")
                if not arn:
                    continue
                groups.append(
                    {
                        "TargetGroupArn": arn,
                        "LoadBalancerArns": group.get("LoadBalancerArns", []),
                        "TargetType": group.get("TargetType"),
                        "Protocol": group.get("Protocol"),
                        "Port": group.get("Port"),
                        "VpcId": group.get("VpcId"),
                        "HealthCheckProtocol": group.get("HealthCheckProtocol"),
                    }
                )
        return groups

    def describe_target_health(
        self,
        region: str,
        target_group_arn: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("elbv2", region_name=region)
        response = client.describe_target_health(TargetGroupArn=target_group_arn)
        descriptions: list[Dict[str, Any]] = []
        for description in response.get("TargetHealthDescriptions", []):
            target = description.get("Target") or {}
            health = description.get("TargetHealth") or {}
            descriptions.append(
                {
                    "TargetId": target.get("Id"),
                    "Port": target.get("Port"),
                    "State": health.get("State"),
                    "Reason": health.get("Reason"),
                    "Description": health.get("Description"),
                }
            )
        return descriptions

    def list_listeners(
        self,
        region: str,
        load_balancer_arn: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("elbv2", region_name=region)
        paginator = client.get_paginator("describe_listeners")
        listeners: list[Dict[str, Any]] = []
        for page in paginator.paginate(LoadBalancerArn=load_balancer_arn):
            for listener in page.get("Listeners", []):
                arn = listener.get("ListenerArn")
                if not arn:
                    continue
                target_group_arns = [
                    action.get("TargetGroupArn")
                    for action in listener.get("DefaultActions", [])
                    if action.get("TargetGroupArn")
                ]
                listeners.append(
                    {
                        "ListenerArn": arn,
                        "Port": listener.get("Port"),
                        "Protocol": listener.get("Protocol"),
                        "TargetGroupArns": target_group_arns,
                    }
                )
        return listeners

    def list_api_integrations(
        self,
        region: str,
        rest_api_id: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("apigateway", region_name=region)
        resources = client.get_resources(restApiId=rest_api_id, embed=["methods"]).get("items", [])
        integrations: list[Dict[str, Any]] = []
        for resource in resources:
            resource_id = resource.get("id")
            path = resource.get("path")
            methods = resource.get("resourceMethods", {}) or {}
            for method in methods.keys():
                integration = client.get_integration(
                    restApiId=rest_api_id,
                    resourceId=resource_id,
                    httpMethod=method,
                )
                integrations.append(
                    {
                        "ResourcePath": path,
                        "HttpMethod": method,
                        "Type": integration.get("type"),
                        "Uri": integration.get("uri"),
                        "ConnectionType": integration.get("connectionType"),
                    }
                )
        return integrations

    def list_listener_rules(
        self,
        region: str,
        listener_arn: str,
        credentials: Optional[AwsCredentials] = None,
    ) -> list[Dict[str, Any]]:
        client = self._session(credentials).client("elbv2", region_name=region)
        paginator = client.get_paginator("describe_rules")
        rules: list[Dict[str, Any]] = []
        for page in paginator.paginate(ListenerArn=listener_arn):
            for rule in page.get("Rules", []):
                rule_arn = rule.get("RuleArn")
                if not rule_arn:
                    continue
                target_group_arns = [
                    action.get("TargetGroupArn")
                    for action in rule.get("Actions", [])
                    if action.get("TargetGroupArn")
                ]
                conditions = []
                for condition in rule.get("Conditions", []):
                    conditions.append(
                        {
                            "Field": condition.get("Field"),
                            "Values": condition.get("Values", []),
                            "PathPatternConfig": condition.get("PathPatternConfig") or {},
                        }
                    )
                rules.append(
                    {
                        "RuleArn": rule_arn,
                        "Priority": rule.get("Priority"),
                        "IsDefault": rule.get("IsDefault", False),
                        "TargetGroupArns": target_group_arns,
                        "Conditions": conditions,
                    }
                )
        return rules

    def _session(self, credentials: Optional[AwsCredentials] = None):
        import boto3

        if not credentials:
            return boto3.session.Session()
        return boto3.session.Session(
            aws_access_key_id=credentials.get("AccessKeyId"),
            aws_secret_access_key=credentials.get("SecretAccessKey"),
            aws_session_token=credentials.get("SessionToken"),
        )
