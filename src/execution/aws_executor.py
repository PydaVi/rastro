from __future__ import annotations

from dataclasses import dataclass, field
import re

from core.domain import Action, ActionType, Observation, Scope
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
class RollbackTracker:
    """Records IAM mutations for guaranteed cleanup at end of campaign."""
    _pending: list[dict] = field(default_factory=list)

    def register_detach_role_policy(self, region: str, role_name: str, policy_arn: str) -> None:
        self._pending.append({
            "op": "detach_role_policy",
            "region": region,
            "role_name": role_name,
            "policy_arn": policy_arn,
        })

    def execute_all(self, client: AwsClient) -> list[str]:
        """Runs all registered rollbacks. Returns list of errors (best-effort)."""
        errors: list[str] = []
        for entry in reversed(self._pending):
            try:
                if entry["op"] == "detach_role_policy":
                    client.detach_role_policy(
                        region=entry["region"],
                        role_name=entry["role_name"],
                        policy_arn=entry["policy_arn"],
                    )
            except Exception as exc:
                errors.append(str(exc))
        self._pending.clear()
        return errors

    def is_empty(self) -> bool:
        return len(self._pending) == 0


@dataclass
class AwsRealExecutor:
    fixture: object
    scope: Scope
    client: AwsClient | None = None
    entry_profile: str | None = None
    _assumed_credentials: AwsCredentials | None = field(default=None, init=False)
    _assumed_role_arn: str | None = field(default=None, init=False)
    _credentials_by_actor: dict[str, AwsCredentials] = field(default_factory=dict, init=False)
    _base_actor_arn: str | None = field(default=None, init=False)
    _entry_assumed_identity_arn: str | None = field(default=None, init=False)
    rollback_tracker: RollbackTracker = field(default_factory=RollbackTracker, init=False)

    def execute(self, action: Action) -> Observation:
        client = self.client or Boto3AwsClient(profile_name=self.entry_profile)
        if self._base_actor_arn is None:
            self._base_actor_arn = action.actor
        self._ensure_entry_actor_credentials(client, action)
        denial = _build_policy_denial(action, self.scope)
        if denial is not None:
            return denial

        if action.action_type == ActionType.ANALYZE:
            details = {
                "details": "Executed analysis step without AWS API call.",
                "execution_mode": "real",
                "real_api_called": False,
            }
            if hasattr(self.fixture, "observe_real"):
                return self.fixture.observe_real(action, details)
            transition = self.fixture.execute(action)
            details = {**transition.details, **details}
            return Observation(success=transition.success, details=details)

        try:
            if action.tool == "iam_list_roles":
                details = self._execute_iam_list_roles(client, action)
            elif action.tool == "iam_passrole":
                details = self._execute_iam_passrole(client, action)
            elif action.tool == "iam_simulate_assume_role":
                details = self._execute_iam_simulate_assume_role(client, action)
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
            elif action.tool == "iam_create_policy_version":
                details = self._execute_iam_policy_abuse_probe(client, action, "iam:CreatePolicyVersion")
            elif action.tool == "iam_attach_role_policy":
                details = self._execute_iam_policy_abuse_probe(client, action, "iam:AttachRolePolicy")
            elif action.tool == "iam_attach_role_policy_mutate":
                details = self._execute_iam_attach_role_policy_mutate(client, action)
            elif action.tool == "iam_pass_role_service_create":
                details = self._execute_iam_policy_abuse_probe(client, action, "iam:PassRole")
            elif action.tool == "iam_simulate_target_access":
                details = self._execute_iam_simulate_target_access(client, action)
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
                    "real_api_called": True,
                },
            )

        details = {
            **details,
            "execution_mode": "real",
            "real_api_called": True,
        }
        if hasattr(self.fixture, "observe_real"):
            return self.fixture.observe_real(action, details)
        transition = self.fixture.execute(action)
        merged_details = {
            **transition.details,
            **details,
        }
        return Observation(success=transition.success, details=merged_details)

    def _execute_iam_list_roles(self, client: AwsClient, action: Action) -> dict:
        region = _required_parameter(action, "region")
        actor_credentials = self._credentials_for_actor(action.actor)
        identity = client.get_caller_identity(region=region, credentials=actor_credentials)
        roles = client.list_roles(region=region, credentials=actor_credentials)
        return {
            "details": "Executed sts:GetCallerIdentity and iam:ListRoles against AWS.",
            "declared_actor": action.actor,
            "effective_actor": action.actor,
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

    def _execute_iam_simulate_assume_role(self, client: AwsClient, action: Action) -> dict:
        region = _required_parameter(action, "region")
        role_arn = action.parameters.get("role_arn") or action.target
        if not role_arn:
            raise ValueError("iam_simulate_assume_role requires role_arn or target")
        simulation = client.simulate_principal_policy(
            region=region,
            policy_source_arn=action.actor,
            action_names=["sts:AssumeRole"],
            resource_arns=[role_arn],
            credentials=self._credentials_for_actor(action.actor),
        )
        decision = "implicitDeny"
        results = simulation.get("EvaluationResults", [])
        if results:
            decision = results[0].get("EvalDecision", decision)
        details = {
            "details": f"Simulated sts:AssumeRole against {role_arn}.",
            "effective_actor": action.actor,
            "request_summary": {
                "api_calls": ["iam:SimulatePrincipalPolicy"],
                "simulated_action": "sts:AssumeRole",
                "target_role_arn": role_arn,
            },
            "response_summary": {
                "policy_decision": decision,
            },
            "simulated_policy_result": {
                "action": "sts:AssumeRole",
                "resource": role_arn,
                "decision": decision,
            },
            "aws_region": region,
        }
        if decision.lower() == "allowed":
            details["granted_role"] = role_arn
        return details

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
        network_evidence = self._build_instance_network_evidence(
            client=client,
            region=region,
            actor=action.actor,
            resource_arn=resource_arn,
            instance_details=instance_details,
            target_group_arn=action.parameters.get("target_group_arn"),
            target_load_balancer_arn=action.parameters.get("target_load_balancer_arn"),
            request_path=action.parameters.get("request_path"),
        )
        request_api_calls = [
            *(
                ["ec2:DescribeInstances"]
                if instance_id
                else []
            ),
            "iam:GetInstanceProfile",
            "ec2:DescribeIamInstanceProfileAssociations",
            *network_evidence["api_calls"],
            *(
                [
                    "sts:AssumeRole",
                    "sts:GetCallerIdentity",
                ]
                if credential_acquisition
                else []
            ),
        ]

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
                **network_evidence["details"],
                **({"credential_acquisition": credential_acquisition} if credential_acquisition else {}),
            },
            "reached_role": reached_role,
            **network_evidence["status"],
            "aws_region": region,
            "request_summary": {
                "api_calls": request_api_calls,
                "entry_surface_arn": resource_arn,
                "instance_profile_arn": profile_arn,
                "instance_id": instance_id,
            },
            "response_summary": {
                "roles_returned": len(roles),
                "association_count": len(associations),
                "sample_instances": [item["InstanceId"] for item in associations[:3]],
                "public_ip": (instance_details or {}).get("PublicIpAddress"),
                "network_reachable_from_internet": network_evidence["status"]["network_reachable_from_internet"],
                "backend_reachable": network_evidence["status"]["backend_reachable"],
                **(
                    {"credentialed_identity": credential_acquisition.get("assumed_identity", {}).get("arn")}
                    if credential_acquisition
                    else {}
                ),
            },
        }

    def _execute_iam_policy_abuse_probe(
        self,
        client: AwsClient,
        action: Action,
        policy_action: str,
    ) -> dict:
        region = _required_parameter(action, "region")
        role_arn = action.parameters.get("role_arn") or action.target
        if not role_arn:
            raise ValueError(f"{action.tool} requires role_arn or target")
        simulation = client.simulate_principal_policy(
            region=region,
            policy_source_arn=action.actor,
            action_names=[policy_action],
            resource_arns=[role_arn],
            credentials=self._credentials_for_actor(action.actor),
        )
        decision = "implicitDeny"
        results = simulation.get("EvaluationResults", [])
        if results:
            decision = results[0].get("EvalDecision", decision)
        return {
            "details": f"Simulated {policy_action} against {role_arn}.",
            "request_summary": {
                "api_calls": ["iam:SimulatePrincipalPolicy"],
                "simulated_action": policy_action,
                "target_role_arn": role_arn,
            },
            "response_summary": {
                "policy_decision": decision,
            },
            "simulated_policy_result": {
                "action": policy_action,
                "resource": role_arn,
                "decision": decision,
            },
            "aws_region": region,
        }

    def _execute_iam_attach_role_policy_mutate(self, client: AwsClient, action: Action) -> dict:
        """Executa iam:AttachRolePolicy real e registra rollback automático."""
        region = _required_parameter(action, "region")
        role_arn = action.parameters.get("role_arn") or action.target
        if not role_arn:
            raise ValueError("iam_attach_role_policy_mutate requires role_arn or target")
        policy_arn = action.parameters.get("policy_arn", "arn:aws:iam::aws:policy/AdministratorAccess")
        role_name = role_arn.split("/")[-1]
        client.attach_role_policy(
            region=region,
            role_name=role_name,
            policy_arn=policy_arn,
            credentials=self._credentials_for_actor(action.actor),
        )
        self.rollback_tracker.register_detach_role_policy(
            region=region,
            role_name=role_name,
            policy_arn=policy_arn,
        )
        return {
            "details": f"Executed iam:AttachRolePolicy — attached {policy_arn} to {role_name}.",
            "mutation_executed": True,
            "request_summary": {
                "api_calls": ["iam:AttachRolePolicy"],
                "role_name": role_name,
                "policy_arn": policy_arn,
            },
            "response_summary": {
                "attached": True,
                "rollback_registered": True,
            },
            "aws_region": region,
            "execution_mode": "real",
            "real_api_called": True,
        }

    def _execute_iam_simulate_target_access(self, client: AwsClient, action: Action) -> dict:
        region = _required_parameter(action, "region")
        policy_action = _required_parameter(action, "policy_action")
        policy_resource = _required_parameter(action, "policy_resource")
        simulation = client.simulate_principal_policy(
            region=region,
            policy_source_arn=action.actor,
            action_names=[policy_action],
            resource_arns=[policy_resource],
            credentials=self._credentials_for_actor(action.actor),
        )
        decision = "implicitDeny"
        results = simulation.get("EvaluationResults", [])
        if results:
            decision = results[0].get("EvalDecision", decision)
        details = {
            "details": f"Simulated {policy_action} against {policy_resource}.",
            "effective_actor": action.actor,
            "request_summary": {
                "api_calls": ["iam:SimulatePrincipalPolicy"],
                "simulated_action": policy_action,
                "target_resource": policy_resource,
            },
            "response_summary": {
                "policy_decision": decision,
            },
            "simulated_policy_result": {
                "action": policy_action,
                "resource": policy_resource,
                "decision": decision,
            },
            "aws_region": region,
        }
        if decision.lower() == "allowed":
            details["evidence"] = {
                "policy_action": policy_action,
                "resource": policy_resource,
                "accessed_via": action.actor,
                "simulated": True,
            }
        return details

    def _build_instance_network_evidence(
        self,
        client: AwsClient,
        region: str,
        actor: str,
        resource_arn: str,
        instance_details: dict | None,
        target_group_arn: str | None = None,
        target_load_balancer_arn: str | None = None,
        request_path: str | None = None,
    ) -> dict:
        details: dict = {
            "entry_surface_kind": "ec2_instance",
        }
        status = {
            "network_reachable_from_internet": False,
            "backend_reachable": False,
        }
        api_calls: list[str] = []
        if not instance_details:
            return {"details": details, "status": status, "api_calls": api_calls}

        subnet_id = instance_details.get("SubnetId")
        vpc_id = instance_details.get("VpcId")
        security_group_ids = instance_details.get("SecurityGroupIds") or []
        public_ip = instance_details.get("PublicIpAddress")
        state = instance_details.get("State")

        details.update(
            {
                "entry_surface_arn": resource_arn,
                "public_ip": public_ip,
                "subnet_id": subnet_id,
                "vpc_id": vpc_id,
                "security_group_ids": security_group_ids,
                "instance_state": state,
            }
        )

        route_tables = client.list_route_tables(
            region=region,
            credentials=self._credentials_for_actor(actor),
        )
        subnets = client.list_subnets(
            region=region,
            credentials=self._credentials_for_actor(actor),
        )
        security_groups = client.list_security_groups(
            region=region,
            credentials=self._credentials_for_actor(actor),
        )
        internet_gateways = client.list_internet_gateways(
            region=region,
            credentials=self._credentials_for_actor(actor),
        )
        api_calls.extend(
            [
                "ec2:DescribeRouteTables",
                "ec2:DescribeSubnets",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeInternetGateways",
            ]
        )

        subnet = next((item for item in subnets if item.get("SubnetId") == subnet_id), None)
        gateway_ids = {
            gateway.get("InternetGatewayId")
            for gateway in internet_gateways
            if any(attachment.get("VpcId") == vpc_id for attachment in gateway.get("Attachments", []))
            and gateway.get("InternetGatewayId")
        }
        associated_route_tables = []
        route_to_igw = False
        for table in route_tables:
            if table.get("VpcId") != vpc_id:
                continue
            associations = table.get("Associations", [])
            subnet_match = any(association.get("SubnetId") == subnet_id for association in associations)
            main_match = any(association.get("Main") is True for association in associations)
            if not subnet_match and not main_match:
                continue
            associated_route_tables.append(table.get("RouteTableId"))
            for route in table.get("Routes", []):
                if route.get("DestinationCidrBlock") != "0.0.0.0/0":
                    continue
                if route.get("GatewayId") in gateway_ids:
                    route_to_igw = True
                    break

        security_group_evidence = []
        public_ingress = False
        for group in security_groups:
            if group.get("GroupId") not in security_group_ids:
                continue
            ingress_rules = group.get("IpPermissions", [])
            for permission in ingress_rules:
                cidrs = [item.get("CidrIp") for item in permission.get("IpRanges", []) if item.get("CidrIp")]
                ipv6_cidrs = [item.get("CidrIpv6") for item in permission.get("Ipv6Ranges", []) if item.get("CidrIpv6")]
                is_public = "0.0.0.0/0" in cidrs or "::/0" in ipv6_cidrs
                if is_public:
                    public_ingress = True
                security_group_evidence.append(
                    {
                        "group_id": group.get("GroupId"),
                        "from_port": permission.get("FromPort"),
                        "to_port": permission.get("ToPort"),
                        "ip_protocol": permission.get("IpProtocol"),
                        "public": is_public,
                    }
                )

        instance_network_proved = bool(public_ip and route_to_igw and public_ingress)
        instance_backend_proved = instance_network_proved and state == "running"

        details.update(
            {
                "network_path": {
                    "subnet_public_ip_on_launch": (subnet or {}).get("MapPublicIpOnLaunch"),
                    "internet_gateway_ids": sorted(gateway_ids),
                    "route_table_ids": associated_route_tables,
                    "route_to_internet_gateway": route_to_igw,
                    "security_group_public_ingress": public_ingress,
                    "security_group_rules": security_group_evidence,
                }
            }
        )
        if ":loadbalancer/" in resource_arn:
            alb_evidence = self._build_load_balancer_network_evidence(
                client=client,
                region=region,
                actor=actor,
                resource_arn=resource_arn,
                instance_id=instance_details.get("InstanceId"),
                target_group_arn=target_group_arn,
                request_path=request_path,
            )
            details["network_path"]["load_balancer"] = alb_evidence["details"]
            api_calls.extend(alb_evidence["api_calls"])
        status["network_reachable_from_internet"] = instance_network_proved
        status["backend_reachable"] = instance_backend_proved
        if ":loadbalancer/" in resource_arn:
            status["network_reachable_from_internet"] = alb_evidence["status"]["network_reachable_from_internet"]
            status["backend_reachable"] = alb_evidence["status"]["backend_reachable"]
        if resource_arn.startswith("arn:aws:apigateway:"):
            api_gateway_evidence = self._build_api_gateway_network_evidence(
                client=client,
                region=region,
                actor=actor,
                resource_arn=resource_arn,
                instance_id=instance_details.get("InstanceId"),
                target_group_arn=target_group_arn,
                target_load_balancer_arn=target_load_balancer_arn,
                request_path=request_path,
            )
            details["network_path"]["api_gateway"] = api_gateway_evidence["details"]
            api_calls.extend(api_gateway_evidence["api_calls"])
            status["network_reachable_from_internet"] = api_gateway_evidence["status"]["network_reachable_from_internet"]
            status["backend_reachable"] = api_gateway_evidence["status"]["backend_reachable"]
        return {"details": details, "status": status, "api_calls": api_calls}

    def _build_load_balancer_network_evidence(
        self,
        client: AwsClient,
        region: str,
        actor: str,
        resource_arn: str,
        instance_id: str | None,
        target_group_arn: str | None = None,
        request_path: str | None = None,
    ) -> dict:
        load_balancers = client.list_load_balancers(
            region=region,
            credentials=self._credentials_for_actor(actor),
        )
        listeners = client.list_listeners(
            region=region,
            load_balancer_arn=resource_arn,
            credentials=self._credentials_for_actor(actor),
        )
        listener_rules = []
        for listener in listeners:
            listener_arn = listener.get("ListenerArn")
            if not listener_arn:
                continue
            for rule in client.list_listener_rules(
                region=region,
                listener_arn=listener_arn,
                credentials=self._credentials_for_actor(actor),
            ):
                listener_rules.append(
                    {
                        **rule,
                        "ListenerArn": listener_arn,
                        "ListenerPort": listener.get("Port"),
                    }
                )
        target_groups = client.list_target_groups(
            region=region,
            credentials=self._credentials_for_actor(actor),
        )
        api_calls = [
            "elasticloadbalancing:DescribeLoadBalancers",
            "elasticloadbalancing:DescribeListeners",
            "elasticloadbalancing:DescribeTargetGroups",
        ]
        if listener_rules:
            api_calls.append("elasticloadbalancing:DescribeRules")
        load_balancer = next((item for item in load_balancers if item.get("LoadBalancerArn") == resource_arn), {})
        listener_target_group_arns = sorted(
            {
                target_group_arn
                for listener in listeners
                for target_group_arn in listener.get("TargetGroupArns", [])
                if target_group_arn
            }
            | {
                target_group_arn
                for rule in listener_rules
                for target_group_arn in rule.get("TargetGroupArns", [])
                if target_group_arn
            }
        )
        relevant_target_groups = [
            item for item in target_groups if item.get("TargetGroupArn") in listener_target_group_arns
        ]
        target_health_descriptions: dict[str, list[dict]] = {}
        for target_group in relevant_target_groups:
            current_target_group_arn = target_group.get("TargetGroupArn")
            if not current_target_group_arn:
                continue
            target_health_descriptions[current_target_group_arn] = client.describe_target_health(
                region=region,
                target_group_arn=current_target_group_arn,
                credentials=self._credentials_for_actor(actor),
            )
        if target_health_descriptions:
            api_calls.append("elasticloadbalancing:DescribeTargetHealth")

        listener_public = any(listener.get("Port") in {80, 443} for listener in listeners)
        matched_listener_rules = self._match_listener_rules(listener_rules, request_path)
        matched_rule_target_group_arns = sorted(
            {
                item
                for rule in matched_listener_rules
                for item in rule.get("TargetGroupArns", [])
                if item
            }
        )
        considered_target_group_arns = matched_rule_target_group_arns or listener_target_group_arns
        if target_group_arn and target_group_arn in listener_target_group_arns:
            considered_target_group_arns = [target_group_arn]
        listener_forwarding = bool(considered_target_group_arns)
        target_health = "unhealthy"
        matched_target_groups = []
        for target_group_arn, descriptions in target_health_descriptions.items():
            if target_group_arn not in considered_target_group_arns:
                continue
            if any(
                description.get("TargetId") == instance_id and description.get("State") == "healthy"
                for description in descriptions
            ):
                target_health = "healthy"
                matched_target_groups.append(target_group_arn)

        details = {
            "load_balancer_arn": resource_arn,
            "dns_name": load_balancer.get("DNSName"),
            "internet_facing": load_balancer.get("Scheme") == "internet-facing",
            "state": load_balancer.get("State"),
            "listener_public": listener_public,
            "listener_forwarding": listener_forwarding,
            "listener_ports": [listener.get("Port") for listener in listeners if listener.get("Port") is not None],
            "target_group_arns": listener_target_group_arns,
            "multiple_target_groups_observed": len(listener_target_group_arns) > 1,
            "matched_listener_rule_arns": [rule.get("RuleArn") for rule in matched_listener_rules if rule.get("RuleArn")],
            "matched_listener_rule_priorities": [
                rule.get("Priority")
                for rule in matched_listener_rules
                if rule.get("Priority") is not None
            ],
            "request_path": request_path,
            "matched_target_groups": matched_target_groups,
            "target_health": target_health,
        }
        status = {
            "network_reachable_from_internet": bool(
                details["internet_facing"] and details["dns_name"] and listener_public
            ),
            "backend_reachable": bool(
                details["internet_facing"]
                and listener_forwarding
                and target_health == "healthy"
            ),
        }
        return {"details": details, "status": status, "api_calls": api_calls}

    def _match_listener_rules(self, listener_rules: list[dict], request_path: str | None) -> list[dict]:
        if not request_path:
            return []
        matched = []
        for rule in listener_rules:
            for condition in rule.get("Conditions", []):
                if condition.get("Field") != "path-pattern":
                    continue
                patterns = condition.get("Values") or (condition.get("PathPatternConfig") or {}).get("Values", [])
                if any(self._path_matches_pattern(request_path, pattern) for pattern in patterns if pattern):
                    matched.append(rule)
                    break
        return matched

    def _path_matches_pattern(self, value: str, pattern: str) -> bool:
        regex = "^" + re.escape(pattern).replace("\\*", ".*").replace("\\?", ".") + "$"
        return bool(re.match(regex, value))

    def _build_api_gateway_network_evidence(
        self,
        client: AwsClient,
        region: str,
        actor: str,
        resource_arn: str,
        instance_id: str | None,
        target_group_arn: str | None,
        target_load_balancer_arn: str | None,
        request_path: str | None,
    ) -> dict:
        rest_api_id = _rest_api_id_from_arn(resource_arn)
        if not rest_api_id:
            return {
                "details": {
                    "rest_api_arn": resource_arn,
                    "public_stage": False,
                    "integration_active": False,
                    "target_load_balancer_arn": target_load_balancer_arn,
                },
                "status": {
                    "network_reachable_from_internet": False,
                    "backend_reachable": False,
                },
                "api_calls": [],
            }

        apis = client.list_rest_apis(
            region=region,
            credentials=self._credentials_for_actor(actor),
        )
        stages = client.list_api_stages(
            region=region,
            rest_api_id=rest_api_id,
            credentials=self._credentials_for_actor(actor),
        )
        integrations = client.list_api_integrations(
            region=region,
            rest_api_id=rest_api_id,
            credentials=self._credentials_for_actor(actor),
        )
        api_calls = [
            "apigateway:GET",
            "apigateway:GetStages",
            "apigateway:GetIntegration",
        ]
        api = next((item for item in apis if item.get("RestApiId") == rest_api_id), {})
        endpoint_types = ((api.get("EndpointConfiguration") or {}).get("types")) or []
        public_stage = bool(stages) and "PRIVATE" not in endpoint_types
        integration_active = bool(integrations)
        matched_integration_uris = [
            item.get("Uri")
            for item in integrations
            if item.get("Uri")
        ]

        downstream_evidence = None
        if target_load_balancer_arn:
            downstream_evidence = self._build_load_balancer_network_evidence(
                client=client,
                region=region,
                actor=actor,
                resource_arn=target_load_balancer_arn,
                instance_id=instance_id,
                target_group_arn=target_group_arn,
                request_path=request_path,
            )
            api_calls.extend(downstream_evidence["api_calls"])

        details = {
            "rest_api_arn": resource_arn,
            "rest_api_id": rest_api_id,
            "endpoint_types": endpoint_types,
            "stage_names": [item.get("StageName") for item in stages],
            "public_stage": public_stage,
            "integration_active": integration_active,
            "integration_uris": matched_integration_uris,
            "target_load_balancer_arn": target_load_balancer_arn,
        }
        if downstream_evidence:
            details["downstream_load_balancer"] = downstream_evidence["details"]
        status = {
            "network_reachable_from_internet": public_stage,
            "backend_reachable": integration_active,
        }
        if downstream_evidence:
            status["network_reachable_from_internet"] = (
                public_stage and downstream_evidence["status"]["network_reachable_from_internet"]
            )
            status["backend_reachable"] = (
                integration_active and downstream_evidence["status"]["backend_reachable"]
            )
        return {"details": details, "status": status, "api_calls": api_calls}

    def _credentials_for_actor(self, actor: str) -> AwsCredentials | None:
        credentials = self._credentials_by_actor.get(actor)
        if credentials is not None:
            return credentials
        if actor == self._base_actor_arn:
            return None
        raise MissingActorCredentialsError(actor)

    def _ensure_entry_actor_credentials(self, client: AwsClient, action: Action) -> None:
        actor = action.actor
        if actor != self._base_actor_arn:
            return
        if actor in self._credentials_by_actor:
            return
        if ":role/" not in actor:
            return
        region = action.parameters.get("region") or (self.scope.allowed_regions[0] if self.scope.allowed_regions else None)
        if not region:
            return
        assumed = client.assume_role(
            region=region,
            role_arn=actor,
            session_name="rastro-entry-session",
            credentials=None,
        )
        credentials = assumed["Credentials"]
        actor_credentials = {
            "AccessKeyId": credentials["AccessKeyId"],
            "SecretAccessKey": credentials["SecretAccessKey"],
            "SessionToken": credentials["SessionToken"],
        }
        self._credentials_by_actor[actor] = actor_credentials
        identity = client.get_caller_identity(region=region, credentials=actor_credentials)
        self._entry_assumed_identity_arn = identity.get("Arn")

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


def _rest_api_id_from_arn(value: str | None) -> str | None:
    if not value or "/restapis/" not in value:
        return None
    suffix = value.split("/restapis/", 1)[1]
    return suffix.split("/", 1)[0]


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
