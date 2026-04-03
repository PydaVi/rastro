from __future__ import annotations

from dataclasses import dataclass, field

from core.domain import Action, ActionType, Observation, Scope
from core.fixture import Fixture
from execution.aws_client import AwsClient, AwsCredentials, Boto3AwsClient


class MissingActorCredentialsError(RuntimeError):
    def __init__(self, actor: str):
        super().__init__(f"missing_actor_credentials:{actor}")
        self.actor = actor


@dataclass
class AwsRealExecutorStub:
    scope: Scope

    def execute(self, action: Action) -> Observation:
        return Observation(
            success=False,
            details={
                "reason": "aws_real_execution_not_implemented",
                "target": "aws",
                "execution_mode": "stub",
                "real_api_called": False,
                "service": action.parameters.get("service"),
            },
        )


@dataclass
class AwsRealExecutor:
    fixture: Fixture
    scope: Scope
    client: AwsClient | None = None
    _assumed_credentials: AwsCredentials | None = field(default=None, init=False)
    _assumed_role_arn: str | None = field(default=None, init=False)
    _credentials_by_actor: dict[str, AwsCredentials] = field(default_factory=dict, init=False)
    _base_actor_arn: str | None = field(default=None, init=False)

    def execute(self, action: Action) -> Observation:
        client = self.client or Boto3AwsClient()
        if self._base_actor_arn is None:
            self._base_actor_arn = action.actor
        denial = _build_policy_denial(action, self.scope)
        if denial is not None:
            return denial

        if action.action_type == ActionType.ANALYZE:
            transition = self.fixture.execute(action)
            details = {
                **transition.details,
                "details": transition.details.get(
                    "details",
                    "Executed analysis step without AWS API call.",
                ),
                "execution_mode": "real",
                "real_api_called": False,
            }
            return Observation(success=transition.success, details=details)

        try:
            if action.tool == "iam_list_roles":
                details = self._execute_iam_list_roles(client, action)
            elif action.tool == "iam_passrole":
                details = self._execute_iam_passrole(client, action)
            elif action.tool == "s3_list_bucket":
                details = self._execute_s3_list_bucket(client, action)
            elif action.tool == "s3_read_sensitive":
                details = self._execute_s3_read_sensitive(client, action)
            elif action.tool == "secretsmanager_list_secrets":
                details = self._execute_secretsmanager_list_secrets(client, action)
            elif action.tool == "secretsmanager_read_secret":
                details = self._execute_secretsmanager_read_secret(client, action)
            elif action.tool == "ssm_list_parameters":
                details = self._execute_ssm_list_parameters(client, action)
            elif action.tool == "ssm_read_parameter":
                details = self._execute_ssm_read_parameter(client, action)
            elif action.tool == "ec2_instance_profile_pivot":
                details = self._execute_ec2_instance_profile_pivot(client, action)
            else:
                return Observation(
                    success=False,
                    details={
                        "reason": "unsupported_aws_tool",
                        "tool": action.tool,
                        "execution_mode": "real",
                        "real_api_called": False,
                    },
                )
        except MissingActorCredentialsError as exc:
            return Observation(
                success=False,
                details={
                    "reason": "missing_actor_credentials",
                    "actor": exc.actor,
                    "tool": action.tool,
                    "execution_mode": "real",
                    "real_api_called": False,
                },
            )
        except Exception as exc:
            return Observation(
                success=False,
                details={
                    "reason": "aws_api_error",
                    "error": str(exc),
                    "tool": action.tool,
                    "execution_mode": "real",
                    "real_api_called": False,
                },
            )

        transition = self.fixture.execute(action)
        merged_details = {
            **transition.details,
            **details,
            "execution_mode": "real",
            "real_api_called": True,
        }
        return Observation(success=transition.success, details=merged_details)

    def _execute_iam_list_roles(self, client: AwsClient, action: Action) -> dict:
        region = _required_parameter(action, "region")
        identity = client.get_caller_identity(region=region)
        roles = client.list_roles(region=region)
        return {
            "details": "Executed sts:GetCallerIdentity and iam:ListRoles against AWS.",
            "aws_identity": {
                "account_id": identity["Account"],
                "arn": identity["Arn"],
            },
            "discovered_roles": roles,
            "aws_account_id": identity["Account"],
            "aws_region": region,
            "request_summary": {
                "api_calls": ["sts:GetCallerIdentity", "iam:ListRoles"],
            },
            "response_summary": {
                "roles_returned": len(roles),
            },
        }

    def _execute_iam_passrole(self, client: AwsClient, action: Action) -> dict:
        region = _required_parameter(action, "region")
        role_arn = action.parameters.get("role_arn") or action.target
        if not role_arn:
            raise ValueError("iam_passrole requires role_arn or target")
        session_name = action.parameters.get("session_name", "rastro-audit-session")
        source_credentials = self._credentials_for_actor(action.actor)
        assumed = client.assume_role(
            region=region,
            role_arn=role_arn,
            session_name=session_name,
            credentials=source_credentials,
        )
        credentials = assumed["Credentials"]
        self._assumed_credentials = {
            "AccessKeyId": credentials["AccessKeyId"],
            "SecretAccessKey": credentials["SecretAccessKey"],
            "SessionToken": credentials["SessionToken"],
        }
        self._assumed_role_arn = role_arn
        self._credentials_by_actor[role_arn] = self._assumed_credentials

        policy_action = action.parameters.get("policy_action", "s3:GetObject")
        policy_resource = action.parameters.get("policy_resource")
        if not policy_resource:
            raise ValueError("iam_passrole requires policy_resource")
        simulation = client.simulate_principal_policy(
            region=region,
            policy_source_arn=role_arn,
            action_names=[policy_action],
            resource_arns=[policy_resource],
        )
        caller = client.get_caller_identity(
            region=region,
            credentials=self._assumed_credentials,
        )
        decision = "implicitDeny"
        results = simulation.get("EvaluationResults", [])
        if results:
            decision = results[0].get("EvalDecision", decision)

        return {
            "granted_role": role_arn,
            "details": "Executed sts:AssumeRole and iam:SimulatePrincipalPolicy against AWS.",
            "assumed_identity": {
                "account_id": caller["Account"],
                "arn": caller["Arn"],
            },
            "simulated_policy_result": {
                "action": policy_action,
                "resource": policy_resource,
                "decision": decision,
            },
            "aws_account_id": caller["Account"],
            "aws_region": region,
            "request_summary": {
                "api_calls": ["sts:AssumeRole", "iam:SimulatePrincipalPolicy"],
                "role_arn": role_arn,
            },
            "response_summary": {
                "assumed_role_arn": role_arn,
                "policy_decision": decision,
            },
        }

    def _execute_s3_read_sensitive(self, client: AwsClient, action: Action) -> dict:
        region = _required_parameter(action, "region")
        bucket = _required_parameter(action, "bucket")
        object_key = _required_parameter(action, "object_key")
        response = client.get_object(
            region=region,
            bucket=bucket,
            object_key=object_key,
            credentials=self._credentials_for_actor(action.actor),
        )
        return {
            "details": f"Executed s3:GetObject against {bucket}/{object_key}.",
            "evidence": {
                "bucket": bucket,
                "object_key": object_key,
                "accessed_via": action.actor,
            },
            "aws_region": region,
            "request_summary": {
                "api_calls": ["s3:GetObject"],
                "bucket": bucket,
                "object_key": object_key,
            },
            "response_summary": {
                "content_length": response.get("ContentLength"),
                "etag": response.get("ETag"),
                "preview": response.get("Preview"),
            },
        }

    def _execute_s3_list_bucket(self, client: AwsClient, action: Action) -> dict:
        region = _required_parameter(action, "region")
        bucket = _required_parameter(action, "bucket")
        prefix = action.parameters.get("prefix")
        keys = client.list_objects(
            region=region,
            bucket=bucket,
            prefix=prefix,
            credentials=self._credentials_for_actor(action.actor),
        )
        return {
            "details": f"Executed s3:ListBucket against {bucket}.",
            "discovered_objects": keys,
            "aws_region": region,
            "request_summary": {
                "api_calls": ["s3:ListBucket"],
                "bucket": bucket,
                "prefix": prefix,
            },
            "response_summary": {
                "objects_returned": len(keys),
                "sample_keys": keys[:5],
            },
        }

    def _execute_secretsmanager_list_secrets(self, client: AwsClient, action: Action) -> dict:
        region = _required_parameter(action, "region")
        name_prefix = action.parameters.get("name_prefix")
        secrets = client.list_secrets(
            region=region,
            name_prefix=name_prefix,
            credentials=self._credentials_for_actor(action.actor),
        )
        return {
            "details": "Executed secretsmanager:ListSecrets against AWS.",
            "discovered_objects": secrets,
            "aws_region": region,
            "request_summary": {
                "api_calls": ["secretsmanager:ListSecrets"],
                "name_prefix": name_prefix,
            },
            "response_summary": {
                "secrets_returned": len(secrets),
                "sample_names": secrets[:5],
            },
        }

    def _execute_secretsmanager_read_secret(self, client: AwsClient, action: Action) -> dict:
        region = _required_parameter(action, "region")
        secret_id = _required_parameter(action, "secret_id")
        response = client.get_secret_value(
            region=region,
            secret_id=secret_id,
            credentials=self._credentials_for_actor(action.actor),
        )
        return {
            "details": f"Executed secretsmanager:GetSecretValue against {secret_id}.",
            "evidence": {
                "secret_id": secret_id,
                "accessed_via": action.actor,
            },
            "aws_region": region,
            "request_summary": {
                "api_calls": ["secretsmanager:GetSecretValue"],
                "secret_id": secret_id,
            },
            "response_summary": {
                "arn": response.get("ARN"),
                "name": response.get("Name"),
                "version_id": response.get("VersionId"),
                "preview": (response.get("SecretString") or "")[:256],
            },
        }

    def _execute_ssm_list_parameters(self, client: AwsClient, action: Action) -> dict:
        region = _required_parameter(action, "region")
        path = _required_parameter(action, "path")
        names = client.list_parameters_by_path(
            region=region,
            path=path,
            credentials=self._credentials_for_actor(action.actor),
        )
        return {
            "details": "Executed ssm:GetParametersByPath against AWS.",
            "discovered_objects": names,
            "aws_region": region,
            "request_summary": {
                "api_calls": ["ssm:GetParametersByPath"],
                "path": path,
            },
            "response_summary": {
                "parameters_returned": len(names),
                "sample_names": names[:5],
            },
        }

    def _execute_ssm_read_parameter(self, client: AwsClient, action: Action) -> dict:
        region = _required_parameter(action, "region")
        name = _required_parameter(action, "name")
        response = client.get_parameter(
            region=region,
            name=name,
            credentials=self._credentials_for_actor(action.actor),
        )
        return {
            "details": f"Executed ssm:GetParameter against {name}.",
            "evidence": {
                "parameter": name,
                "accessed_via": action.actor,
            },
            "aws_region": region,
            "request_summary": {
                "api_calls": ["ssm:GetParameter"],
                "name": name,
            },
            "response_summary": {
                "arn": response.get("ARN"),
                "name": response.get("Name"),
                "version": response.get("Version"),
                "type": response.get("Type"),
                "preview": (response.get("Value") or "")[:256],
            },
        }

    def _execute_ec2_instance_profile_pivot(self, client: AwsClient, action: Action) -> dict:
        region = _required_parameter(action, "region")
        resource_arn = action.parameters.get("resource_arn") or action.target
        if not resource_arn:
            raise ValueError("ec2_instance_profile_pivot requires resource_arn or target")

        instance_profile_arn = action.parameters.get("instance_profile_arn") or resource_arn
        instance_profile_name = _instance_profile_name_from_arn(instance_profile_arn)
        if not instance_profile_name:
            raise ValueError("ec2_instance_profile_pivot requires an IAM instance-profile ARN target")

        instance_id = action.parameters.get("instance_id")
        instance_details = None
        if instance_id:
            instance_details = client.describe_instance(
                region=region,
                instance_id=instance_id,
                credentials=self._credentials_for_actor(action.actor),
            )

        profile = client.get_instance_profile(
            region=region,
            instance_profile_name=instance_profile_name,
            credentials=self._credentials_for_actor(action.actor),
        )
        profile_arn = profile.get("Arn") or instance_profile_arn
        roles = profile.get("Roles") or []
        reached_role = roles[0] if roles else None
        associations = client.list_instance_profile_associations(
            region=region,
            instance_profile_arn=profile_arn,
            credentials=self._credentials_for_actor(action.actor),
        )
        credential_acquisition = self._acquire_pivot_credentials_if_configured(
            client=client,
            action=action,
            region=region,
            reached_role=reached_role,
        )

        return {
            "details": (
                "Executed iam:GetInstanceProfile and "
                f"ec2:DescribeIamInstanceProfileAssociations against {profile_arn}."
            ),
            "evidence": {
                "entry_surface_arn": resource_arn,
                "instance_profile_arn": profile_arn,
                "reached_role": reached_role,
                "instance": instance_details,
                "instance_associations": associations,
                **({"credential_acquisition": credential_acquisition} if credential_acquisition else {}),
            },
            "reached_role": reached_role,
            "aws_region": region,
            "request_summary": {
                "api_calls": [
                    *(
                        ["ec2:DescribeInstances"]
                        if instance_id
                        else []
                    ),
                    "iam:GetInstanceProfile",
                    "ec2:DescribeIamInstanceProfileAssociations",
                    *(
                        [
                            "sts:AssumeRole",
                            "sts:GetCallerIdentity",
                        ]
                        if credential_acquisition
                        else []
                    ),
                ],
                "entry_surface_arn": resource_arn,
                "instance_profile_arn": profile_arn,
                "instance_id": instance_id,
            },
            "response_summary": {
                "roles_returned": len(roles),
                "association_count": len(associations),
                "sample_instances": [item["InstanceId"] for item in associations[:3]],
                "public_ip": (instance_details or {}).get("PublicIpAddress"),
                **(
                    {"credentialed_identity": credential_acquisition.get("assumed_identity", {}).get("arn")}
                    if credential_acquisition
                    else {}
                ),
            },
        }

    def _credentials_for_actor(self, actor: str) -> AwsCredentials | None:
        credentials = self._credentials_by_actor.get(actor)
        if credentials is not None:
            return credentials
        if actor == self._base_actor_arn:
            return None
        raise MissingActorCredentialsError(actor)

    def _acquire_pivot_credentials_if_configured(
        self,
        client: AwsClient,
        action: Action,
        region: str,
        reached_role: str | None,
    ) -> dict | None:
        acquisition = action.parameters.get("credential_acquisition")
        if not acquisition or not reached_role:
            return None
        mode = acquisition.get("mode")
        if mode != "assume_role_surrogate":
            raise ValueError(f"unsupported_credential_acquisition_mode:{mode}")

        session_name = acquisition.get("session_name", "rastro-pivot-surrogate")
        source_credentials = self._credentials_for_actor(action.actor)
        assumed = client.assume_role(
            region=region,
            role_arn=reached_role,
            session_name=session_name,
            credentials=source_credentials,
        )
        credentials = assumed["Credentials"]
        actor_credentials = {
            "AccessKeyId": credentials["AccessKeyId"],
            "SecretAccessKey": credentials["SecretAccessKey"],
            "SessionToken": credentials["SessionToken"],
        }
        self._credentials_by_actor[reached_role] = actor_credentials
        assumed_identity = client.get_caller_identity(
            region=region,
            credentials=actor_credentials,
        )
        return {
            "mode": mode,
            "assumed_role_arn": reached_role,
            "assumed_identity": {
                "account_id": assumed_identity["Account"],
                "arn": assumed_identity["Arn"],
            },
        }


def _required_parameter(action: Action, key: str) -> str:
    value = action.parameters.get(key)
    if not value:
        raise ValueError(f"{action.tool or action.action_type.value} requires parameter {key}")
    return value


def _instance_profile_name_from_arn(value: str | None) -> str | None:
    if not value or ":instance-profile/" not in value:
        return None
    return value.rsplit("/", 1)[-1]


def _build_policy_denial(action: Action, scope: Scope) -> Observation | None:
    service = action.parameters.get("service")
    if service is not None and service not in scope.allowed_services:
        return Observation(
            success=False,
            details={
                "reason": "service_not_allowed",
                "service": service,
                "execution_mode": "real",
                "real_api_called": False,
            },
        )

    region = action.parameters.get("region")
    if region is not None and region not in scope.allowed_regions:
        return Observation(
            success=False,
            details={
                "reason": "region_not_allowed",
                "region": region,
                "execution_mode": "real",
                "real_api_called": False,
            },
        )

    account_id = _extract_account_id(action.actor) or _extract_account_id(action.target)
    if account_id is not None and account_id not in scope.aws_account_ids:
        return Observation(
            success=False,
            details={
                "reason": "account_not_allowed",
                "account_id": account_id,
                "execution_mode": "real",
                "real_api_called": False,
            },
        )

    if action.target is not None and action.target not in scope.allowed_resources:
        return Observation(
            success=False,
            details={
                "reason": "resource_not_allowed",
                "resource": action.target,
                "execution_mode": "real",
                "real_api_called": False,
            },
        )

    return None


def _extract_account_id(value: str | None) -> str | None:
    if not value or not value.startswith("arn:aws:"):
        return None
    parts = value.split(":")
    if len(parts) < 5:
        return None
    account_id = parts[4]
    return account_id or None
