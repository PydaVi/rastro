import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.main import _build_execution_surface, _restore_objective_target_access_actions, _stabilize_decision, app, execute_run, run
from core.attack_graph import AttackGraph
from core.audit import AuditLogger
from core.domain import Action, ActionType, Decision, Objective, Observation, Scope
from core.aws_dry_run_lab import AwsDryRunLab
from core.blind_real_runtime import BlindRealRuntime
from execution.aws_executor import AwsRealExecutor, AwsRealExecutorStub
from core.state import StateManager
from reporting.report import ReportGenerator
from execution.scope_enforcer import ScopeEnforcer
from execution.preflight import run_preflight
from core.fixture import Fixture
from core.sanitizer import write_sanitized_artifacts
from core.tool_registry import ToolRegistry
from operations.service import (
    load_authorization,
    load_target,
    run_assessment,
    run_campaign,
    run_discovery_driven_assessment,
    run_generated_campaign,
    write_assessment_summary,
)
from operations.models import AssessmentResult, CampaignResult
from operations.models import ProfileDefinition
from operations.discovery import run_foundation_discovery
from operations.campaign_synthesis import synthesize_foundation_campaigns
from operations.synthetic_catalog import get_mixed_synthetic_profile, get_synthetic_profile
from operations.target_selection import select_foundation_targets
from planner.action_shaping import shape_available_actions
from planner.ollama_planner import OllamaPlanner
from planner.openai_planner import _parse_response as parse_openai_response
from planner.mock_planner import DeterministicPlanner


runner = CliRunner()


class FakeAwsClient:
    def __init__(self):
        self.assume_role_calls = []
        self.get_object_calls = []
        self.parameter_path_calls = []

    def get_caller_identity(self, region: str, credentials=None):
        if credentials == {
            "AccessKeyId": "AKIA-BROKER",
            "SecretAccessKey": "secret-broker",
            "SessionToken": "token-broker",
        }:
            return {
                "Account": "123456789012",
                "Arn": "arn:aws:sts::123456789012:assumed-role/BrokerRole/rastro-broker-session",
            }
        if credentials == {
            "AccessKeyId": "AKIA-DATA",
            "SecretAccessKey": "secret-data",
            "SessionToken": "token-data",
        }:
            return {
                "Account": "123456789012",
                "Arn": "arn:aws:sts::123456789012:assumed-role/DataAccessRole/rastro-dataaccess-session",
            }
        if credentials:
            return {
                "Account": "123456789012",
                "Arn": "arn:aws:sts::123456789012:assumed-role/AuditRole/rastro-audit-session",
            }
        return {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/analyst",
        }

    def list_users(self, region: str, credentials=None):
        return [
            "arn:aws:iam::123456789012:user/analyst",
            "arn:aws:iam::123456789012:user/auditor",
        ]

    def list_roles(self, region: str, credentials=None):
        return ["arn:aws:iam::123456789012:role/AuditRole"]

    def get_role_details(self, region: str, role_name: str, credentials=None):
        return {
            "Arn": f"arn:aws:iam::123456789012:role/{role_name}",
            "AssumeRolePolicyDocument": {
                "Statement": [
                    {
                        "Principal": {
                            "AWS": "arn:aws:iam::123456789012:role/BrokerRole"
                        }
                    }
                ]
            },
            "AttachedPolicies": [
                {
                    "PolicyName": "AdministratorAccess" if role_name == "AuditRole" else "ReadOnlyAccess",
                    "PolicyArn": f"arn:aws:iam::aws:policy/{'AdministratorAccess' if role_name == 'AuditRole' else 'ReadOnlyAccess'}",
                }
            ],
            "InlinePolicyNames": ["CreatePolicyVersionInline"] if role_name == "AuditRole" else [],
            "PermissionsBoundary": None,
        }

    def assume_role(self, region: str, role_arn: str, session_name: str, credentials=None):
        self.assume_role_calls.append(
            {
                "region": region,
                "role_arn": role_arn,
                "session_name": session_name,
                "credentials": credentials,
            }
        )
        if role_arn.endswith(":role/BrokerRole"):
            return {
                "Credentials": {
                    "AccessKeyId": "AKIA-BROKER",
                    "SecretAccessKey": "secret-broker",
                    "SessionToken": "token-broker",
                }
            }
        if role_arn.endswith(":role/DataAccessRole"):
            return {
                "Credentials": {
                    "AccessKeyId": "AKIA-DATA",
                    "SecretAccessKey": "secret-data",
                    "SessionToken": "token-data",
                }
            }
        return {
            "Credentials": {
                "AccessKeyId": "AKIA...",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
            }
        }

    def simulate_principal_policy(
        self,
        region: str,
        policy_source_arn: str,
        action_names: list[str],
        resource_arns: list[str],
        credentials=None,
    ):
        return {
            "EvaluationResults": [
                {
                    "EvalDecision": "allowed",
                }
            ]
        }

    def get_object(self, region: str, bucket: str, object_key: str, credentials=None):
        self.get_object_calls.append(
            {
                "region": region,
                "bucket": bucket,
                "object_key": object_key,
                "credentials": credentials,
            }
        )
        return {
            "ContentLength": 24,
            "ETag": '"etag"',
            "Preview": "payroll-preview",
        }

    def list_objects(self, region: str, bucket: str, prefix=None, credentials=None):
        return ["payroll.csv", "notes.txt"]

    def list_buckets(self, region: str, credentials=None):
        return ["sensitive-finance-data", "public-reports"]

    def list_secrets(self, region: str, name_prefix=None, credentials=None):
        if name_prefix == "prod/":
            return ["prod/payroll-api-key"]
        if name_prefix == "archive/":
            return ["archive/payroll-history"]
        return ["reports/quarterly-summary"]

    def list_parameters_by_path(self, region: str, path: str, credentials=None):
        self.parameter_path_calls.append(path)
        if path == "/prod":
            return ["/prod/payroll/api_key"]
        if path == "/finance":
            return ["/finance/quarterly/reporting_key"]
        if path == "/customer":
            return ["/customer/payroll/runtime_key"]
        return []

    def get_secret_value(self, region: str, secret_id: str, credentials=None):
        return {
            "ARN": f"arn:aws:secretsmanager:{region}:123456789012:secret:{secret_id}",
            "Name": secret_id,
            "VersionId": "example-version",
            "SecretString": "payroll-api-key-preview",
        }

    def get_parameter(self, region: str, name: str, credentials=None):
        return {
            "ARN": f"arn:aws:ssm:{region}:123456789012:parameter/{name.lstrip('/')}",
            "Name": name,
            "Type": "SecureString",
            "Value": "parameter-preview",
            "Version": 1,
        }

    def get_instance_profile(self, region: str, instance_profile_name: str, credentials=None):
        return {
            "Arn": f"arn:aws:iam::123456789012:instance-profile/{instance_profile_name}",
            "InstanceProfileName": instance_profile_name,
            "Roles": ["arn:aws:iam::123456789012:role/PayrollAppInstanceRole"],
        }

    def list_instance_profile_associations(self, region: str, instance_profile_arn: str, credentials=None):
        return [
            {
                "InstanceId": "i-0123456789abcdef0",
                "State": "associated",
                "AssociationId": "iip-assoc-123",
            }
        ]

    def describe_instance(self, region: str, instance_id: str, credentials=None):
        return {
            "InstanceId": instance_id,
            "PublicIpAddress": "54.1.2.3",
            "PrivateIpAddress": "172.31.0.10",
            "State": "running",
            "SubnetId": "subnet-123",
            "VpcId": "vpc-123",
            "SecurityGroupIds": ["sg-123"],
            "IamInstanceProfileArn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
            "MetadataOptions": {"HttpTokens": "optional"},
        }

    def list_instance_profiles(self, region: str, credentials=None):
        return [
            {
                "Arn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
                "InstanceProfileName": "PayrollAppInstanceProfile",
                "Roles": ["arn:aws:iam::123456789012:role/PayrollAppInstanceRole"],
            }
        ]

    def list_instances(self, region: str, credentials=None):
        return [
            {
                "InstanceId": "i-0123456789abcdef0",
                "Arn": "arn:aws:ec2:us-east-1:550192603632:instance/i-0123456789abcdef0",
                "SubnetId": "subnet-123",
                "VpcId": "vpc-123",
                "PublicIpAddress": "54.1.2.3",
                "PrivateIpAddress": "172.31.0.10",
                "State": "running",
                "SecurityGroupIds": ["sg-123"],
                "IamInstanceProfileArn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
                "MetadataOptions": {"HttpTokens": "optional"},
            }
        ]

    def list_internet_gateways(self, region: str, credentials=None):
        return [
            {
                "InternetGatewayId": "igw-123",
                "Attachments": [{"VpcId": "vpc-123"}],
            }
        ]

    def list_route_tables(self, region: str, credentials=None):
        return [
            {
                "RouteTableId": "rtb-123",
                "VpcId": "vpc-123",
                "Associations": [{"SubnetId": "subnet-123"}],
                "Routes": [{"DestinationCidrBlock": "0.0.0.0/0", "GatewayId": "igw-123"}],
            }
        ]

    def list_subnets(self, region: str, credentials=None):
        return [
            {
                "SubnetId": "subnet-123",
                "VpcId": "vpc-123",
                "AvailabilityZone": "us-east-1a",
                "MapPublicIpOnLaunch": True,
            }
        ]

    def list_security_groups(self, region: str, credentials=None):
        return [
            {
                "GroupId": "sg-123",
                "VpcId": "vpc-123",
                "GroupName": "public-payroll-app",
                "IpPermissions": [
                    {"FromPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                    {"FromPort": 443, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                ],
            }
        ]

    def list_load_balancers(self, region: str, credentials=None):
        return [
            {
                "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge",
                "DNSName": "public-webhook-bridge-123.us-east-1.elb.amazonaws.com",
                "Scheme": "internet-facing",
                "VpcId": "vpc-123",
                "State": "active",
            }
        ]

    def list_rest_apis(self, region: str, credentials=None):
        return [
            {
                "RestApiId": "payroll-webhook-public",
                "Arn": "arn:aws:apigateway:us-east-1::/restapis/payroll-webhook-public",
                "Name": "payroll-webhook-public",
                "EndpointConfiguration": {"types": ["REGIONAL"]},
            }
        ]

    def list_api_stages(self, region: str, rest_api_id: str, credentials=None):
        return [
            {
                "StageName": "prod",
                "DeploymentId": "dep-123",
            }
        ]

    def list_target_groups(self, region: str, credentials=None):
        return [
            {
                "TargetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:550192603632:targetgroup/payroll-webhook-tg/123",
                "LoadBalancerArns": [
                    "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge"
                ],
                "TargetType": "instance",
                "Protocol": "HTTP",
                "Port": 80,
                "VpcId": "vpc-123",
                "HealthCheckProtocol": "HTTP",
            }
        ]

    def describe_target_health(self, region: str, target_group_arn: str, credentials=None):
        return [
            {
                "TargetId": "i-0123456789abcdef0",
                "Port": 80,
                "State": "healthy",
                "Reason": None,
                "Description": None,
            }
        ]

    def list_listeners(self, region: str, load_balancer_arn: str, credentials=None):
        return [
            {
                "ListenerArn": f"{load_balancer_arn}/listener/app/123/456",
                "Port": 443,
                "Protocol": "HTTPS",
                "TargetGroupArns": [
                    "arn:aws:elasticloadbalancing:us-east-1:550192603632:targetgroup/payroll-webhook-tg/123"
                ],
            }
        ]

    def list_listener_rules(self, region: str, listener_arn: str, credentials=None):
        return []

    def list_api_integrations(self, region: str, rest_api_id: str, credentials=None):
        return [
            {
                "ResourcePath": "/webhook",
                "HttpMethod": "POST",
                "Type": "HTTP_PROXY",
                "Uri": "http://172.31.0.10/webhook",
                "ConnectionType": "INTERNET",
            }
        ]


def test_fixture_expands_alias_actions_and_matches_alias_transition() -> None:
    fixture = Fixture(
        {
            "state": {
                "identities": {
                    "arn:aws:iam::123456789012:user/analyst": {
                        "available_actions": [
                            {
                                "action_type": "access_resource",
                                "target": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key",
                                "parameters": {
                                    "service": "secretsmanager",
                                    "region": "us-east-1",
                                    "secret_id": "prod/payroll-api-key",
                                },
                                "tool": "secretsmanager_read_secret",
                            }
                        ]
                    }
                }
            },
            "aliases": {
                "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key": [
                    "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/app/s1"
                ]
            },
            "transitions": [
                {
                    "action_type": "access_resource",
                    "actor": "arn:aws:iam::123456789012:user/analyst",
                    "target": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key",
                    "parameters": {
                        "service": "secretsmanager",
                        "region": "us-east-1",
                        "secret_id": "prod/payroll-api-key",
                    },
                    "observation": {
                        "evidence": {
                            "secret_id": "prod/payroll-api-key"
                        }
                    },
                }
            ],
        }
    )

    actions = fixture.enumerate_actions(None)
    alias_action = next(
        action
        for action in actions
        if action.target == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/app/s1"
    )

    assert alias_action.parameters["secret_id"] == "prod/app/s1"

    observation = fixture.execute(alias_action)

    assert observation.success is True
    assert observation.details["evidence"]["secret_id"] == "prod/payroll-api-key"

    def simulate_principal_policy(
        self,
        region: str,
        policy_source_arn: str,
        action_names: list[str],
        resource_arns: list[str],
        credentials=None,
    ):
        return {
            "EvaluationResults": [
                {
                    "EvalDecision": "allowed",
                }
            ]
        }

    def get_object(self, region: str, bucket: str, object_key: str, credentials=None):
        self.get_object_calls.append(
            {
                "region": region,
                "bucket": bucket,
                "object_key": object_key,
                "credentials": credentials,
            }
        )
        return {
            "ContentLength": 24,
            "ETag": '"etag"',
            "Preview": "payroll-preview",
        }

    def list_objects(self, region: str, bucket: str, prefix=None, credentials=None):
        return ["payroll.csv", "notes.txt"]

    def list_buckets(self, region: str, credentials=None):
        return ["sensitive-finance-data", "public-reports"]

    def list_secrets(self, region: str, name_prefix=None, credentials=None):
        if name_prefix == "prod/":
            return ["prod/payroll-api-key"]
        if name_prefix == "archive/":
            return ["archive/payroll-history"]
        return ["reports/quarterly-summary"]

    def list_parameters_by_path(self, region: str, path: str, credentials=None):
        self.parameter_path_calls.append(path)
        if path == "/prod":
            return ["/prod/payroll/api_key"]
        if path == "/finance":
            return ["/finance/quarterly/reporting_key"]
        if path == "/customer":
            return ["/customer/payroll/runtime_key"]
        return []

    def get_secret_value(self, region: str, secret_id: str, credentials=None):
        return {
            "ARN": f"arn:aws:secretsmanager:{region}:123456789012:secret:{secret_id}",
            "Name": secret_id,
            "VersionId": "example-version",
            "SecretString": "payroll-api-key-preview",
        }

    def get_parameter(self, region: str, name: str, credentials=None):
        return {
            "ARN": f"arn:aws:ssm:{region}:123456789012:parameter/{name.lstrip('/')}",
            "Name": name,
            "Type": "SecureString",
            "Value": "parameter-preview",
            "Version": 1,
        }

    def get_instance_profile(self, region: str, instance_profile_name: str, credentials=None):
        return {
            "Arn": f"arn:aws:iam::123456789012:instance-profile/{instance_profile_name}",
            "InstanceProfileName": instance_profile_name,
            "Roles": ["arn:aws:iam::123456789012:role/PayrollAppInstanceRole"],
        }

    def list_instance_profile_associations(self, region: str, instance_profile_arn: str, credentials=None):
        return [
            {
                "InstanceId": "i-0123456789abcdef0",
                "State": "associated",
                "AssociationId": "iip-assoc-123",
            }
        ]

    def describe_instance(self, region: str, instance_id: str, credentials=None):
        return {
            "InstanceId": instance_id,
            "PublicIpAddress": "54.1.2.3",
            "PrivateIpAddress": "172.31.0.10",
            "State": "running",
            "IamInstanceProfileArn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
            "MetadataOptions": {"HttpTokens": "optional"},
        }



def test_build_execution_surface_selects_real_executor_for_non_dry_run_aws() -> None:
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[ActionType.ENUMERATE],
        allowed_resources=["arn:aws:iam::123456789012:root"],
        max_steps=5,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "aws_dry_run_lab.json")
    surface = _build_execution_surface(environment=fixture, scope=scope)
    assert isinstance(surface, AwsRealExecutor)


def test_aws_real_executor_stub_returns_explicit_not_implemented() -> None:
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[ActionType.ENUMERATE],
        allowed_resources=["arn:aws:iam::123456789012:root"],
        max_steps=5,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    executor = AwsRealExecutorStub(scope)
    action = Action(
        action_type=ActionType.ENUMERATE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:iam::123456789012:root",
        parameters={"service": "iam"},
    )
    observation = executor.execute(action)
    assert observation.success is False
    assert observation.details["reason"] == "aws_real_execution_not_implemented"
    assert observation.details["execution_mode"] == "stub"


def test_aws_real_executor_executes_single_real_path() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "aws_dry_run_lab.json")
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[
            ActionType.ENUMERATE,
            ActionType.ASSUME_ROLE,
            ActionType.ACCESS_RESOURCE,
        ],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:iam::123456789012:role/AuditRole",
            "arn:aws:s3:::sensitive-finance-data/payroll.csv",
        ],
        max_steps=5,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "sts", "s3"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=FakeAwsClient())
    enumerate_action, assume_action = fixture.enumerate_actions(None)
    enumerate_observation = executor.execute(enumerate_action)
    assume_observation = executor.execute(assume_action)
    access_action = fixture.enumerate_actions(None)[1]
    access_observation = executor.execute(access_action)

    assert enumerate_observation.success is True
    assert enumerate_observation.details["execution_mode"] == "real"
    assert enumerate_observation.details["aws_identity"]["arn"] == "arn:aws:iam::123456789012:user/analyst"
    assert assume_observation.success is True
    assert assume_observation.details["granted_role"] == "arn:aws:iam::123456789012:role/AuditRole"
    assert assume_observation.details["simulated_policy_result"]["decision"] == "allowed"
    assert access_observation.success is True
    assert access_observation.details["response_summary"]["preview"] == "payroll-preview"


def test_aws_real_executor_supports_s3_object_discovery_path() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "aws_s3_discovery_lab.json")
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[
            ActionType.ENUMERATE,
            ActionType.ASSUME_ROLE,
            ActionType.ACCESS_RESOURCE,
        ],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:iam::123456789012:role/AuditRole",
            "arn:aws:s3:::sensitive-finance-data",
            "arn:aws:s3:::sensitive-finance-data/payroll.csv",
        ],
        max_steps=6,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "sts", "s3"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=FakeAwsClient())

    enumerate_action, assume_action = fixture.enumerate_actions(None)
    enumerate_observation = executor.execute(enumerate_action)
    assume_observation = executor.execute(assume_action)
    list_bucket_action = fixture.enumerate_actions(None)[1]
    list_bucket_observation = executor.execute(list_bucket_action)
    access_action = fixture.enumerate_actions(None)[1]
    access_observation = executor.execute(access_action)

    assert enumerate_observation.success is True
    assert assume_observation.success is True
    assert list_bucket_observation.success is True
    assert list_bucket_observation.details["request_summary"]["api_calls"] == ["s3:ListBucket"]
    assert "payroll.csv" in list_bucket_observation.details["discovered_objects"]
    assert access_observation.success is True


def test_aws_real_executor_handles_analyze_without_unbound_details() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_iam_s3_lab.json")
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[
            ActionType.ENUMERATE,
            ActionType.ASSUME_ROLE,
            ActionType.ACCESS_RESOURCE,
            ActionType.ANALYZE,
        ],
        allowed_resources=["arn:aws:s3:::bucket-a/payroll.csv"],
        max_steps=6,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "s3"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=FakeAwsClient())
    action = Action(
        action_type=ActionType.ANALYZE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target=None,
        parameters={},
    )

    observation = executor.execute(action)

    assert observation.success is False
    assert observation.details["reason"] == "no_transition"
    assert observation.details["execution_mode"] == "real"
    assert observation.details["real_api_called"] is False


def test_aws_real_executor_supports_secretsmanager_path() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "aws_secrets_branching_lab.json")
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[
            ActionType.ENUMERATE,
            ActionType.ASSUME_ROLE,
            ActionType.ACCESS_RESOURCE,
        ],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:iam::123456789012:role/RoleA",
            "arn:aws:iam::123456789012:role/RoleM",
            "arn:aws:iam::123456789012:role/RoleQ",
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:*",
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key",
        ],
        max_steps=6,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "sts", "secretsmanager"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=FakeAwsClient())

    enumerate_action = fixture.enumerate_actions(None)[0]
    enumerate_observation = executor.execute(enumerate_action)
    assume_action = next(
        action
        for action in fixture.enumerate_actions(None)
        if action.action_type == ActionType.ASSUME_ROLE
        and action.target == "arn:aws:iam::123456789012:role/RoleM"
    )
    assume_observation = executor.execute(assume_action)
    list_secret_action = next(
        action
        for action in fixture.enumerate_actions(None)
        if action.actor == "arn:aws:iam::123456789012:role/RoleM"
        and action.tool == "secretsmanager_list_secrets"
    )
    list_secret_observation = executor.execute(list_secret_action)
    read_secret_action = next(
        action
        for action in fixture.enumerate_actions(None)
        if action.actor == "arn:aws:iam::123456789012:role/RoleM"
        and action.tool == "secretsmanager_read_secret"
    )
    read_secret_observation = executor.execute(read_secret_action)

    assert enumerate_observation.success is True
    assert assume_observation.success is True
    assert list_secret_observation.success is True
    assert list_secret_observation.details["request_summary"]["api_calls"] == ["secretsmanager:ListSecrets"]
    assert "prod/payroll-api-key" in list_secret_observation.details["discovered_objects"]
    assert read_secret_observation.success is True
    assert read_secret_observation.details["request_summary"]["api_calls"] == ["secretsmanager:GetSecretValue"]
    assert read_secret_observation.details["response_summary"]["preview"] == "payroll-api-key-preview"


def test_aws_real_executor_uses_actor_credentials_for_role_chaining() -> None:
    fixture = Fixture.load(
        Path(__file__).resolve().parents[1] / "fixtures" / "aws_iam_role_chaining_direct_lab.json"
    )
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[
            ActionType.ENUMERATE,
            ActionType.ASSUME_ROLE,
            ActionType.ACCESS_RESOURCE,
        ],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:iam::123456789012:role/BrokerRole",
            "arn:aws:iam::123456789012:role/DataAccessRole",
            "arn:aws:s3:::sensitive-finance-data/payroll.csv",
        ],
        max_steps=6,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "sts", "s3"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    client = FakeAwsClient()
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=client)

    enumerate_action = fixture.enumerate_actions(None)[0]
    first_assume_action = next(
        action
        for action in fixture.enumerate_actions(None)
        if action.action_type == ActionType.ASSUME_ROLE
        and action.target == "arn:aws:iam::123456789012:role/BrokerRole"
    )

    executor.execute(enumerate_action)
    executor.execute(first_assume_action)

    second_assume_action = next(
        action
        for action in fixture.enumerate_actions(None)
        if action.action_type == ActionType.ASSUME_ROLE
        and action.actor == "arn:aws:iam::123456789012:role/BrokerRole"
    )
    second_assume_observation = executor.execute(second_assume_action)

    access_action = next(
        action
        for action in fixture.enumerate_actions(None)
        if action.action_type == ActionType.ACCESS_RESOURCE
    )
    access_observation = executor.execute(access_action)

    assert second_assume_observation.success is True
    assert client.assume_role_calls[0]["credentials"] is None
    assert client.assume_role_calls[1]["credentials"] == {
        "AccessKeyId": "AKIA-BROKER",
        "SecretAccessKey": "secret-broker",
        "SessionToken": "token-broker",
    }
    assert access_observation.success is True
    assert client.get_object_calls[-1]["credentials"] == {
        "AccessKeyId": "AKIA-DATA",
        "SecretAccessKey": "secret-data",
        "SessionToken": "token-data",
    }
    assert access_observation.details["evidence"]["accessed_via"] == "arn:aws:iam::123456789012:role/DataAccessRole"


def test_aws_real_executor_supports_compute_instance_profile_pivot() -> None:
    fixture = Fixture(
        {
            "name": "aws-compute-instance-profile-pivot-test",
            "state": {
                "flags": [],
                "identities": {
                    "arn:aws:iam::123456789012:user/platform-analyst": {
                        "available_actions": [
                            {
                                "action_type": "enumerate",
                                "target": "arn:aws:iam::123456789012:root",
                                "parameters": {"service": "iam", "region": "us-east-1"},
                                "tool": "iam_list_roles",
                            },
                            {
                                "action_type": "access_resource",
                                "target": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
                                "parameters": {
                                    "service": "ec2",
                                    "region": "us-east-1",
                                    "resource_arn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
                                },
                                "tool": "ec2_instance_profile_pivot",
                            },
                        ]
                    }
                },
            },
            "transitions": [
                {
                    "action_type": "enumerate",
                    "actor": "arn:aws:iam::123456789012:user/platform-analyst",
                    "target": "arn:aws:iam::123456789012:root",
                    "observation": {"details": "Listed roles."},
                },
                {
                    "action_type": "access_resource",
                    "actor": "arn:aws:iam::123456789012:user/platform-analyst",
                    "target": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
                    "observation": {
                        "details": "Pivoted to the compute-attached role.",
                        "evidence": {
                            "reached_role": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
                        },
                    },
                },
            ],
        }
    )
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[
            ActionType.ENUMERATE,
            ActionType.ACCESS_RESOURCE,
        ],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
            "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
        ],
        max_steps=4,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "ec2"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    client = FakeAwsClient()
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=client)

    enumerate_action = fixture.enumerate_actions(None)[0]
    enumerate_observation = executor.execute(enumerate_action)

    pivot_action = Action(
        action_type=ActionType.ACCESS_RESOURCE,
        actor="arn:aws:iam::123456789012:user/platform-analyst",
        target="arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
        parameters={
            "service": "ec2",
            "region": "us-east-1",
            "resource_arn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
        },
        tool="ec2_instance_profile_pivot",
    )
    pivot_observation = executor.execute(pivot_action)

    assert enumerate_observation.success is True
    assert pivot_observation.success is True
    assert pivot_observation.details["request_summary"]["api_calls"] == [
        "iam:GetInstanceProfile",
        "ec2:DescribeIamInstanceProfileAssociations",
    ]
    assert pivot_observation.details["reached_role"] == "arn:aws:iam::123456789012:role/PayrollAppInstanceRole"
    assert pivot_observation.details["response_summary"]["association_count"] == 1


def test_aws_real_executor_supports_external_entry_compute_pivot() -> None:
    fixture = Fixture(
        {
            "name": "aws-external-entry-compute-pivot-test",
            "state": {
                "flags": [],
                "identities": {
                    "arn:aws:iam::123456789012:user/platform-analyst": {
                        "available_actions": [
                            {
                                "action_type": "access_resource",
                                "target": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
                                "parameters": {
                                    "service": "ec2",
                                    "region": "us-east-1",
                                    "resource_arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
                                    "instance_id": "i-0123456789abcdef0",
                                    "instance_profile_arn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
                                },
                                "tool": "ec2_instance_profile_pivot",
                            }
                        ]
                    }
                },
            },
            "transitions": [
                {
                    "action_type": "access_resource",
                    "actor": "arn:aws:iam::123456789012:user/platform-analyst",
                    "target": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
                    "observation": {
                        "details": "Pivoted from public EC2 surface into the attached role.",
                        "evidence": {
                            "reached_role": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
                        },
                    },
                }
            ],
        }
    )
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[ActionType.ACCESS_RESOURCE],
        allowed_resources=[
            "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
            "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
            "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
        ],
        max_steps=3,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["ec2", "iam"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=FakeAwsClient())
    pivot_action = fixture.enumerate_actions(None)[0]
    pivot_observation = executor.execute(pivot_action)

    assert pivot_observation.success is True
    assert pivot_observation.details["request_summary"]["api_calls"] == [
        "ec2:DescribeInstances",
        "iam:GetInstanceProfile",
        "ec2:DescribeIamInstanceProfileAssociations",
        "ec2:DescribeRouteTables",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeInternetGateways",
    ]
    assert pivot_observation.details["response_summary"]["public_ip"] == "54.1.2.3"
    assert pivot_observation.details["response_summary"]["network_reachable_from_internet"] is True
    assert pivot_observation.details["response_summary"]["backend_reachable"] is True
    assert pivot_observation.details["network_reachable_from_internet"] is True
    assert pivot_observation.details["backend_reachable"] is True
    assert pivot_observation.details["evidence"]["network_path"]["route_to_internet_gateway"] is True
    assert pivot_observation.details["evidence"]["network_path"]["security_group_public_ingress"] is True
    assert pivot_observation.details["evidence"]["entry_surface_arn"].endswith(
        "instance/i-0123456789abcdef0"
    )


def test_aws_real_executor_supports_alb_external_entry_network_evidence() -> None:
    fixture = Fixture(
        {
            "name": "aws-alb-external-entry-compute-pivot-test",
            "state": {
                "flags": [],
                "identities": {
                    "arn:aws:iam::123456789012:user/platform-analyst": {
                        "available_actions": [
                            {
                                "action_type": "access_resource",
                                "target": "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge",
                                "parameters": {
                                    "service": "ec2",
                                    "region": "us-east-1",
                                    "resource_arn": "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge",
                                    "instance_id": "i-0123456789abcdef0",
                                    "instance_profile_arn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
                                },
                                "tool": "ec2_instance_profile_pivot",
                            }
                        ]
                    }
                },
            },
            "transitions": [
                {
                    "action_type": "access_resource",
                    "actor": "arn:aws:iam::123456789012:user/platform-analyst",
                    "target": "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge",
                    "observation": {
                        "details": "Pivoted from public ALB surface into the attached role.",
                        "evidence": {
                            "reached_role": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
                        },
                    },
                }
            ],
        }
    )
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[ActionType.ACCESS_RESOURCE],
        allowed_resources=[
            "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge",
            "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
            "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
        ],
        max_steps=3,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["ec2", "iam", "elasticloadbalancing"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=FakeAwsClient())
    pivot_action = fixture.enumerate_actions(None)[0]
    pivot_observation = executor.execute(pivot_action)

    assert pivot_observation.success is True
    assert pivot_observation.details["request_summary"]["api_calls"] == [
        "ec2:DescribeInstances",
        "iam:GetInstanceProfile",
        "ec2:DescribeIamInstanceProfileAssociations",
        "ec2:DescribeRouteTables",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeInternetGateways",
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth",
    ]
    load_balancer_path = pivot_observation.details["evidence"]["network_path"]["load_balancer"]
    assert load_balancer_path["internet_facing"] is True
    assert load_balancer_path["listener_forwarding"] is True
    assert load_balancer_path["target_health"] == "healthy"
    assert pivot_observation.details["network_reachable_from_internet"] is True
    assert pivot_observation.details["backend_reachable"] is True


def test_aws_real_executor_supports_api_gateway_external_entry_network_evidence() -> None:
    fixture = Fixture(
        {
            "name": "aws-apigw-external-entry-compute-pivot-test",
            "state": {
                "flags": [],
                "identities": {
                    "arn:aws:iam::123456789012:user/platform-analyst": {
                        "available_actions": [
                            {
                                "action_type": "access_resource",
                                "target": "arn:aws:apigateway:us-east-1::/restapis/payroll-webhook-public",
                                "parameters": {
                                    "service": "ec2",
                                    "region": "us-east-1",
                                    "resource_arn": "arn:aws:apigateway:us-east-1::/restapis/payroll-webhook-public",
                                    "instance_id": "i-0123456789abcdef0",
                                    "instance_profile_arn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
                                    "target_load_balancer_arn": "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge",
                                },
                                "tool": "ec2_instance_profile_pivot",
                            }
                        ]
                    }
                },
            },
            "transitions": [
                {
                    "action_type": "access_resource",
                    "actor": "arn:aws:iam::123456789012:user/platform-analyst",
                    "target": "arn:aws:apigateway:us-east-1::/restapis/payroll-webhook-public",
                    "observation": {
                        "details": "Pivoted from public API Gateway surface into the attached role.",
                        "evidence": {
                            "reached_role": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
                        },
                    },
                }
            ],
        }
    )
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[ActionType.ACCESS_RESOURCE],
        allowed_resources=[
            "arn:aws:apigateway:us-east-1::/restapis/payroll-webhook-public",
            "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge",
            "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
            "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
        ],
        max_steps=3,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["ec2", "iam", "elasticloadbalancing", "apigateway"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=FakeAwsClient())
    pivot_action = fixture.enumerate_actions(None)[0]
    pivot_observation = executor.execute(pivot_action)

    assert pivot_observation.success is True
    assert pivot_observation.details["request_summary"]["api_calls"] == [
        "ec2:DescribeInstances",
        "iam:GetInstanceProfile",
        "ec2:DescribeIamInstanceProfileAssociations",
        "ec2:DescribeRouteTables",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeInternetGateways",
        "apigateway:GET",
        "apigateway:GetStages",
        "apigateway:GetIntegration",
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth",
    ]
    api_gateway_path = pivot_observation.details["evidence"]["network_path"]["api_gateway"]
    assert api_gateway_path["public_stage"] is True
    assert api_gateway_path["integration_active"] is True
    assert api_gateway_path["target_load_balancer_arn"].endswith("public-webhook-bridge")
    assert pivot_observation.details["network_reachable_from_internet"] is True
    assert pivot_observation.details["backend_reachable"] is True


def test_aws_real_executor_supports_nlb_external_entry_network_evidence() -> None:
    class FakeNlbAwsClient(FakeAwsClient):
        def list_load_balancers(self, region: str, credentials=None):
            return [
                {
                    "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/net/public-webhook-bridge",
                    "DNSName": "public-webhook-bridge-123.us-east-1.elb.amazonaws.com",
                    "Scheme": "internet-facing",
                    "VpcId": "vpc-123",
                    "State": "active",
                }
            ]

        def list_target_groups(self, region: str, credentials=None):
            return [
                {
                    "TargetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:550192603632:targetgroup/payroll-webhook-ntg/123",
                    "LoadBalancerArns": [
                        "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/net/public-webhook-bridge"
                    ],
                    "TargetType": "instance",
                    "Protocol": "TCP",
                    "Port": 80,
                    "VpcId": "vpc-123",
                    "HealthCheckProtocol": "TCP",
                }
            ]

        def list_listeners(self, region: str, load_balancer_arn: str, credentials=None):
            return [
                {
                    "ListenerArn": f"{load_balancer_arn}/listener/net/123/456",
                    "Port": 80,
                    "Protocol": "TCP",
                    "TargetGroupArns": [
                        "arn:aws:elasticloadbalancing:us-east-1:550192603632:targetgroup/payroll-webhook-ntg/123"
                    ],
                }
            ]

    fixture = Fixture(
        {
            "name": "aws-nlb-external-entry-compute-pivot-test",
            "state": {
                "flags": [],
                "identities": {
                    "arn:aws:iam::123456789012:user/platform-analyst": {
                        "available_actions": [
                            {
                                "action_type": "access_resource",
                                "target": "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/net/public-webhook-bridge",
                                "parameters": {
                                    "service": "ec2",
                                    "region": "us-east-1",
                                    "resource_arn": "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/net/public-webhook-bridge",
                                    "instance_id": "i-0123456789abcdef0",
                                    "instance_profile_arn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
                                    "target_group_arn": "arn:aws:elasticloadbalancing:us-east-1:550192603632:targetgroup/payroll-webhook-ntg/123",
                                },
                                "tool": "ec2_instance_profile_pivot",
                            }
                        ]
                    }
                },
            },
            "transitions": [
                {
                    "action_type": "access_resource",
                    "actor": "arn:aws:iam::123456789012:user/platform-analyst",
                    "target": "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/net/public-webhook-bridge",
                    "observation": {
                        "details": "Pivoted from public NLB surface into the attached role.",
                        "evidence": {
                            "reached_role": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
                        },
                    },
                }
            ],
        }
    )
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[ActionType.ACCESS_RESOURCE],
        allowed_resources=[
            "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/net/public-webhook-bridge",
            "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
            "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
        ],
        max_steps=3,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["ec2", "iam", "elasticloadbalancing"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=FakeNlbAwsClient())
    pivot_action = fixture.enumerate_actions(None)[0]
    pivot_observation = executor.execute(pivot_action)

    assert pivot_observation.success is True
    assert pivot_observation.details["request_summary"]["api_calls"] == [
        "ec2:DescribeInstances",
        "iam:GetInstanceProfile",
        "ec2:DescribeIamInstanceProfileAssociations",
        "ec2:DescribeRouteTables",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeInternetGateways",
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth",
    ]
    load_balancer_path = pivot_observation.details["evidence"]["network_path"]["load_balancer"]
    assert load_balancer_path["internet_facing"] is True
    assert load_balancer_path["listener_public"] is True
    assert load_balancer_path["listener_forwarding"] is True
    assert load_balancer_path["target_health"] == "healthy"
    assert pivot_observation.details["network_reachable_from_internet"] is True
    assert pivot_observation.details["backend_reachable"] is True


def test_aws_real_executor_supports_alb_listener_rule_evidence() -> None:
    class FakeAlbRulesAwsClient(FakeAwsClient):
        def list_target_groups(self, region: str, credentials=None):
            return [
                {
                    "TargetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:550192603632:targetgroup/payroll-webhook-tg/123",
                    "LoadBalancerArns": [
                        "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge"
                    ],
                    "TargetType": "instance",
                    "Protocol": "HTTP",
                    "Port": 80,
                    "VpcId": "vpc-123",
                    "HealthCheckProtocol": "HTTP",
                },
                {
                    "TargetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:550192603632:targetgroup/decoy-webhook-tg/456",
                    "LoadBalancerArns": [
                        "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge"
                    ],
                    "TargetType": "instance",
                    "Protocol": "HTTP",
                    "Port": 80,
                    "VpcId": "vpc-123",
                    "HealthCheckProtocol": "HTTP",
                },
            ]

        def list_listener_rules(self, region: str, listener_arn: str, credentials=None):
            return [
                {
                    "RuleArn": f"{listener_arn}/rule/payroll",
                    "Priority": "10",
                    "IsDefault": False,
                    "TargetGroupArns": [
                        "arn:aws:elasticloadbalancing:us-east-1:550192603632:targetgroup/payroll-webhook-tg/123"
                    ],
                    "Conditions": [
                        {
                            "Field": "path-pattern",
                            "Values": ["/payroll/*"],
                            "PathPatternConfig": {"Values": ["/payroll/*"]},
                        }
                    ],
                },
                {
                    "RuleArn": f"{listener_arn}/rule/default",
                    "Priority": "default",
                    "IsDefault": True,
                    "TargetGroupArns": [
                        "arn:aws:elasticloadbalancing:us-east-1:550192603632:targetgroup/decoy-webhook-tg/456"
                    ],
                    "Conditions": [],
                },
            ]

        def describe_target_health(self, region: str, target_group_arn: str, credentials=None):
            if target_group_arn.endswith("/123"):
                return [
                    {
                        "TargetId": "i-0123456789abcdef0",
                        "Port": 80,
                        "State": "healthy",
                        "Reason": None,
                        "Description": None,
                    }
                ]
            return [
                {
                    "TargetId": "i-decoy",
                    "Port": 80,
                    "State": "healthy",
                    "Reason": None,
                    "Description": None,
                }
            ]

    fixture = Fixture(
        {
            "name": "aws-alb-rule-external-entry-compute-pivot-test",
            "state": {
                "flags": [],
                "identities": {
                    "arn:aws:iam::123456789012:user/platform-analyst": {
                        "available_actions": [
                            {
                                "action_type": "access_resource",
                                "target": "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge",
                                "parameters": {
                                    "service": "ec2",
                                    "region": "us-east-1",
                                    "resource_arn": "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge",
                                    "instance_id": "i-0123456789abcdef0",
                                    "instance_profile_arn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
                                    "target_group_arn": "arn:aws:elasticloadbalancing:us-east-1:550192603632:targetgroup/payroll-webhook-tg/123",
                                    "request_path": "/payroll/export.csv",
                                },
                                "tool": "ec2_instance_profile_pivot",
                            }
                        ]
                    }
                },
            },
            "transitions": [
                {
                    "action_type": "access_resource",
                    "actor": "arn:aws:iam::123456789012:user/platform-analyst",
                    "target": "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge",
                    "observation": {
                        "details": "Pivoted from rule-matched ALB surface into the attached role.",
                        "evidence": {
                            "reached_role": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
                        },
                    },
                }
            ],
        }
    )
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[ActionType.ACCESS_RESOURCE],
        allowed_resources=[
            "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge",
            "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
            "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
        ],
        max_steps=3,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["ec2", "iam", "elasticloadbalancing"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=FakeAlbRulesAwsClient())
    pivot_action = fixture.enumerate_actions(None)[0]
    pivot_observation = executor.execute(pivot_action)

    assert pivot_observation.success is True
    assert "elasticloadbalancing:DescribeRules" in pivot_observation.details["request_summary"]["api_calls"]
    load_balancer_path = pivot_observation.details["evidence"]["network_path"]["load_balancer"]
    assert load_balancer_path["multiple_target_groups_observed"] is True
    assert load_balancer_path["matched_listener_rule_priorities"] == ["10"]
    assert load_balancer_path["matched_target_groups"] == [
        "arn:aws:elasticloadbalancing:us-east-1:550192603632:targetgroup/payroll-webhook-tg/123"
    ]
    assert load_balancer_path["request_path"] == "/payroll/export.csv"


def test_aws_real_executor_can_acquire_surrogate_credentials_for_pivoted_role() -> None:
    fixture = Fixture(
        {
            "name": "aws-surrogate-pivot-credentials-test",
            "state": {
                "flags": [],
                "identities": {
                    "arn:aws:iam::123456789012:user/platform-analyst": {
                        "available_actions": [
                            {
                                "action_type": "access_resource",
                                "target": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
                                "parameters": {
                                    "service": "ec2",
                                    "region": "us-east-1",
                                    "resource_arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
                                    "instance_id": "i-0123456789abcdef0",
                                    "instance_profile_arn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
                                    "credential_acquisition": {
                                        "mode": "assume_role_surrogate",
                                        "session_name": "rastro-pivot-surrogate",
                                    },
                                },
                                "tool": "ec2_instance_profile_pivot",
                            }
                        ]
                    }
                },
            },
            "transitions": [
                {
                    "action_type": "access_resource",
                    "actor": "arn:aws:iam::123456789012:user/platform-analyst",
                    "target": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
                    "observation": {
                        "details": "Pivoted into compute role.",
                        "evidence": {
                            "reached_role": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
                        },
                    },
                }
            ],
        }
    )
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[ActionType.ACCESS_RESOURCE],
        allowed_resources=[
            "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
            "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
            "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
        ],
        max_steps=3,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["ec2", "iam", "sts"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    client = FakeAwsClient()
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=client)

    pivot_observation = executor.execute(fixture.enumerate_actions(None)[0])

    assert pivot_observation.success is True
    assert pivot_observation.details["evidence"]["credential_acquisition"]["mode"] == "assume_role_surrogate"
    assert client.assume_role_calls[-1]["role_arn"] == "arn:aws:iam::123456789012:role/PayrollAppInstanceRole"
    assert client.assume_role_calls[-1]["credentials"] is None


def test_aws_real_executor_requires_explicit_credentials_for_post_pivot_actor() -> None:
    fixture = Fixture(
        {
            "name": "aws-post-pivot-credentials-required-test",
            "state": {
                "flags": [],
                "identities": {
                    "arn:aws:iam::123456789012:user/platform-analyst": {
                        "available_actions": [
                            {
                                "action_type": "enumerate",
                                "target": "arn:aws:iam::123456789012:root",
                                "parameters": {"service": "iam", "region": "us-east-1"},
                                "tool": "iam_list_roles",
                            },
                            {
                                "action_type": "access_resource",
                                "target": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
                                "parameters": {
                                    "service": "ec2",
                                    "region": "us-east-1",
                                    "resource_arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
                                    "instance_id": "i-0123456789abcdef0",
                                    "instance_profile_arn": "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
                                },
                                "tool": "ec2_instance_profile_pivot",
                            },
                        ]
                    }
                },
            },
            "transitions": [
                {
                    "action_type": "enumerate",
                    "actor": "arn:aws:iam::123456789012:user/platform-analyst",
                    "target": "arn:aws:iam::123456789012:root",
                    "observation": {"details": "Listed roles."},
                },
                {
                    "action_type": "access_resource",
                    "actor": "arn:aws:iam::123456789012:user/platform-analyst",
                    "target": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
                    "observation": {
                        "details": "Pivoted into compute role.",
                        "reached_role": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
                    },
                    "update_identities": {
                        "arn:aws:iam::123456789012:role/PayrollAppInstanceRole": {
                            "available_actions": [
                                {
                                    "action_type": "assume_role",
                                    "target": "arn:aws:iam::123456789012:role/BrokerRole",
                                    "parameters": {
                                        "service": "sts",
                                        "region": "us-east-1",
                                        "role_arn": "arn:aws:iam::123456789012:role/BrokerRole",
                                        "session_name": "rastro-broker",
                                        "policy_action": "s3:GetObject",
                                        "policy_resource": "arn:aws:s3:::bucket/object",
                                    },
                                    "tool": "iam_passrole",
                                }
                            ]
                        }
                    },
                },
                {
                    "action_type": "assume_role",
                    "actor": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
                    "target": "arn:aws:iam::123456789012:role/BrokerRole",
                    "observation": {"granted_role": "arn:aws:iam::123456789012:role/BrokerRole"},
                },
            ],
        }
    )
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[ActionType.ENUMERATE, ActionType.ACCESS_RESOURCE, ActionType.ASSUME_ROLE],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
            "arn:aws:iam::123456789012:instance-profile/PayrollAppInstanceProfile",
            "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
            "arn:aws:iam::123456789012:role/BrokerRole",
        ],
        max_steps=4,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "ec2", "sts"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    client = FakeAwsClient()
    executor = AwsRealExecutor(fixture=fixture, scope=scope, client=client)

    executor.execute(fixture.enumerate_actions(None)[0])
    executor.execute(fixture.enumerate_actions(None)[1])

    assume_action = next(
        action
        for action in fixture.enumerate_actions(None)
        if action.action_type == ActionType.ASSUME_ROLE
    )
    assume_observation = executor.execute(assume_action)

    assert assume_observation.success is False
    assert assume_observation.details["reason"] == "missing_actor_credentials"
    assert assume_observation.details["actor"] == "arn:aws:iam::123456789012:role/PayrollAppInstanceRole"
    assert client.assume_role_calls == []


def test_shape_available_actions_filters_uncredentialed_actor_progression() -> None:
    fixture = Fixture(
        {
            "name": "uncredentialed-actor-filter-test",
            "state": {
                "flags": [],
                "identities": {
                    "arn:aws:iam::123456789012:user/platform-analyst": {
                        "available_actions": [
                            {
                                "action_type": "enumerate",
                                "target": "arn:aws:iam::123456789012:root",
                                "parameters": {"service": "iam", "region": "us-east-1"},
                                "tool": "iam_list_roles",
                            }
                        ]
                    }
                },
            },
            "transitions": [
                {
                    "action_type": "enumerate",
                    "actor": "arn:aws:iam::123456789012:user/platform-analyst",
                    "target": "arn:aws:iam::123456789012:root",
                    "observation": {"details": "Listed roles."},
                },
                {
                    "action_type": "access_resource",
                    "actor": "arn:aws:iam::123456789012:user/platform-analyst",
                    "target": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
                    "observation": {
                        "details": "Pivoted into compute role.",
                        "reached_role": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
                    },
                    "update_identities": {
                        "arn:aws:iam::123456789012:role/PayrollAppInstanceRole": {
                            "available_actions": [
                                {
                                    "action_type": "assume_role",
                                    "target": "arn:aws:iam::123456789012:role/BrokerRole",
                                    "parameters": {
                                        "service": "sts",
                                        "region": "us-east-1",
                                        "role_arn": "arn:aws:iam::123456789012:role/BrokerRole",
                                        "session_name": "rastro-broker",
                                        "policy_action": "s3:GetObject",
                                        "policy_resource": "arn:aws:s3:::bucket/object",
                                    },
                                    "tool": "iam_passrole",
                                }
                            ]
                        }
                    },
                },
            ],
        }
    )
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[ActionType.ENUMERATE, ActionType.ACCESS_RESOURCE, ActionType.ASSUME_ROLE],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
            "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
            "arn:aws:iam::123456789012:role/BrokerRole",
        ],
        max_steps=4,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "ec2", "sts"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )
    state = StateManager(
        objective=Objective(description="test", target="arn:aws:s3:::bucket/object", success_criteria={}),
        scope=scope,
        fixture=fixture,
        tool_registry=ToolRegistry.load(Path(__file__).resolve().parents[1] / "tools"),
    )

    enumerate_action = fixture.enumerate_actions(None)[0]
    state.apply_observation(
        enumerate_action,
        Observation(success=True, details={"details": "Listed roles."}),
        reason="enumerate",
    )
    pivot_action = Action(
        action_type=ActionType.ACCESS_RESOURCE,
        actor="arn:aws:iam::123456789012:user/platform-analyst",
        target="arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
        parameters={
            "service": "ec2",
            "region": "us-east-1",
            "resource_arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
        },
        tool="ec2_instance_profile_pivot",
    )
    state.apply_observation(
        pivot_action,
        Observation(
            success=True,
            details={"reached_role": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole"},
        ),
        reason="pivot",
    )
    assume_action = Action(
        action_type=ActionType.ASSUME_ROLE,
        actor="arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
        target="arn:aws:iam::123456789012:role/BrokerRole",
        parameters={
            "service": "sts",
            "region": "us-east-1",
            "role_arn": "arn:aws:iam::123456789012:role/BrokerRole",
            "session_name": "rastro-broker",
            "policy_action": "s3:GetObject",
            "policy_resource": "arn:aws:s3:::bucket/object",
        },
        tool="iam_passrole",
    )
    state.apply_observation(
        assume_action,
        Observation(
            success=False,
            details={
                "reason": "missing_actor_credentials",
                "actor": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
            },
        ),
        reason="missing creds",
    )

    shaped = shape_available_actions(state.snapshot(), fixture.enumerate_actions(None))

    assert all(action.actor != "arn:aws:iam::123456789012:role/PayrollAppInstanceRole" for action in shaped)


def test_profile_list_cli_shows_foundation_bundle() -> None:
    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0
    assert "aws-iam-s3" in result.stdout
    assert "bundle:aws-foundation" in result.stdout


def test_target_validate_cli_accepts_foundation_target(tmp_path: Path) -> None:
    target_path = tmp_path / "target.json"
    target_path.write_text(
        """
{
  "name": "local-aws-lab",
  "platform": "aws",
  "accounts": ["550192603632"],
  "allowed_regions": ["us-east-1"],
  "entry_roles": ["arn:aws:iam::550192603632:user/brainctl-user"]
}
""".strip()
    )

    result = runner.invoke(app, ["target", "validate", "--target", str(target_path)])

    assert result.exit_code == 0
    assert "Target valid: local-aws-lab" in result.stdout


def test_preflight_validate_cli_accepts_dry_run_scope(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scope_path = repo_root / "examples" / "scope_aws_dry_run.json"

    result = runner.invoke(app, ["preflight", "validate", "--scope", str(scope_path)])

    assert result.exit_code == 0
    assert '"ok": true' in result.stdout
    assert '"mode": "skipped"' in result.stdout


def test_run_foundation_discovery_writes_artifacts(tmp_path: Path) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)

    discovery_json, discovery_md, snapshot = run_foundation_discovery(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        client=FakeAwsClient(),
    )

    assert discovery_json.exists()
    assert discovery_md.exists()
    assert snapshot["summary"]["roles"] >= 1
    assert snapshot["summary"]["buckets"] == 2
    assert snapshot["summary"]["secrets"] == 1
    assert snapshot["summary"]["parameters"] == 2
    assert snapshot["summary"]["instance_profiles"] == 1
    assert snapshot["summary"]["instances"] == 1
    assert snapshot["summary"]["internet_gateways"] == 1
    assert snapshot["summary"]["route_tables"] == 1
    assert snapshot["summary"]["subnets"] == 1
    assert snapshot["summary"]["security_groups"] == 1
    assert snapshot["summary"]["load_balancers"] == 1
    assert snapshot["summary"]["api_gateways"] == 1
    assert snapshot["summary"]["target_groups"] == 1
    assert snapshot["summary"]["lb_listeners"] == 1
    assert snapshot["summary"]["api_integrations"] == 1
    assert snapshot["summary"]["relationships"] >= 5
    assert all(":role/aws-service-role/" not in resource["identifier"] for resource in snapshot["resources"])
    assert any(
        resource["identifier"] == "arn:aws:ssm:us-east-1:550192603632:parameter/prod/payroll/api_key"
        for resource in snapshot["resources"]
        if resource["resource_type"] == "secret.ssm_parameter"
    )
    assert any(
        resource["resource_type"] == "compute.ec2_instance"
        and resource["metadata"]["network_reachable_from_internet"] is True
        for resource in snapshot["resources"]
    )
    assert any(
        relationship["type"] == "routes_to_internet_gateway"
        for relationship in snapshot["relationships"]
    )
    assert any(
        relationship["type"] == "uses_instance_profile"
        for relationship in snapshot["relationships"]
    )
    assert any(
        resource["resource_type"] == "network.load_balancer"
        and resource["metadata"]["internet_facing"] is True
        for resource in snapshot["resources"]
    )
    assert any(
        resource["resource_type"] == "network.api_gateway"
        and resource["metadata"]["public_stage"] is True
        for resource in snapshot["resources"]
    )
    audit_role = next(
        resource
        for resource in snapshot["resources"]
        if resource["resource_type"] == "identity.role"
        and resource["identifier"] == "arn:aws:iam::123456789012:role/AuditRole"
    )
    assert "arn:aws:iam::123456789012:role/BrokerRole" in audit_role["metadata"]["trust_principals"]
    assert "AdministratorAccess" in audit_role["metadata"]["attached_policy_names"]
    assert "CreatePolicyVersionInline" in audit_role["metadata"]["inline_policy_names"]
    assert any(
        relationship["type"] == "can_assume"
        and relationship["source"] == "arn:aws:iam::123456789012:role/BrokerRole"
        and relationship["target"] == "arn:aws:iam::123456789012:role/AuditRole"
        for relationship in snapshot["relationships"]
    )


def test_target_selection_prioritizes_iam_privesc_role_signals(tmp_path: Path) -> None:
    discovery_snapshot = {
        "target": "aws-blind-real",
        "bundle": "aws-foundation",
        "caller_identity": {"Account": "123456789012"},
        "resources": [
            {
                "service": "iam",
                "resource_type": "identity.role",
                "identifier": "arn:aws:iam::123456789012:role/privesc-CreatePolicyVersion-role",
                "metadata": {
                    "trust_principals": ["*"],
                    "attached_policy_names": ["CreatePolicyVersionRole"],
                    "attached_policy_arns": ["arn:aws:iam::aws:policy/CreatePolicyVersionRole"],
                    "inline_policy_names": ["PassRoleInline"],
                },
            },
            {
                "service": "iam",
                "resource_type": "identity.role",
                "identifier": "arn:aws:iam::123456789012:role/boring-audit-role",
                "metadata": {
                    "trust_principals": ["arn:aws:iam::123456789012:role/BrokerRole"],
                    "attached_policy_names": ["ReadOnlyAccess"],
                    "attached_policy_arns": ["arn:aws:iam::aws:policy/ReadOnlyAccess"],
                    "inline_policy_names": [],
                },
            },
        ],
        "relationships": [],
    }

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        max_candidates_per_profile=5,
        bundle_name="aws-foundation",
    )

    role_candidates = [candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-role-chaining"]
    assert role_candidates[0]["resource_arn"] == "arn:aws:iam::123456789012:role/privesc-CreatePolicyVersion-role"
    assert "policy_escalation_signal" in role_candidates[0]["selection_reason"]


def test_target_selection_emits_dedicated_iam_heavy_privesc_profiles(tmp_path: Path) -> None:
    discovery_snapshot = {
        "target": "aws-iam-heavy",
        "bundle": "aws-iam-heavy",
        "caller_identity": {"Account": "123456789012"},
        "resources": [
            {
                "service": "iam",
                "resource_type": "identity.role",
                "identifier": "arn:aws:iam::123456789012:role/privesc-CreatePolicyVersion-role",
                "metadata": {
                    "trust_principals": ["*"],
                    "attached_policy_names": ["CreatePolicyVersionRole"],
                    "attached_policy_arns": ["arn:aws:iam::aws:policy/CreatePolicyVersionRole"],
                    "inline_policy_names": [],
                },
            },
            {
                "service": "iam",
                "resource_type": "identity.role",
                "identifier": "arn:aws:iam::123456789012:role/privesc-PassRole-role",
                "metadata": {
                    "trust_principals": ["arn:aws:iam::123456789012:user/analyst"],
                    "attached_policy_names": ["CodeBuildProjectRole"],
                    "attached_policy_arns": ["arn:aws:iam::aws:policy/CodeBuildProjectRole"],
                    "inline_policy_names": ["PassRoleInline"],
                },
            },
        ],
        "relationships": [],
    }

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        max_candidates_per_profile=5,
        bundle_name="aws-iam-heavy",
    )

    families = {(candidate["profile_family"], candidate["resource_arn"]) for candidate in payload["candidates"]}
    assert (
        "aws-iam-create-policy-version-privesc",
        "arn:aws:iam::123456789012:role/privesc-CreatePolicyVersion-role",
    ) in families
    assert (
        "aws-iam-pass-role-privesc",
        "arn:aws:iam::123456789012:role/privesc-PassRole-role",
    ) in families


def test_run_foundation_discovery_collects_public_compute_network_relationships(tmp_path: Path) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)

    _, _, snapshot = run_foundation_discovery(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        client=FakeAwsClient(),
    )

    resource_map = {resource["identifier"]: resource for resource in snapshot["resources"]}
    instance_arn = "arn:aws:ec2:us-east-1:550192603632:instance/i-0123456789abcdef0"
    subnet_arn = "arn:aws:ec2:us-east-1:550192603632:subnet/subnet-123"
    route_table_arn = "arn:aws:ec2:us-east-1:550192603632:route-table/rtb-123"
    internet_gateway_arn = "arn:aws:ec2:us-east-1:550192603632:internet-gateway/igw-123"
    security_group_arn = "arn:aws:ec2:us-east-1:550192603632:security-group/sg-123"

    assert resource_map[subnet_arn]["resource_type"] == "network.subnet"
    assert resource_map[route_table_arn]["metadata"]["routes_to_internet"] is True
    assert resource_map[security_group_arn]["metadata"]["public_ingress_ports"] == [80, 443]
    assert resource_map[instance_arn]["metadata"]["security_group_ids"] == ["sg-123"]

    assert {
        (relationship["source"], relationship["target"], relationship["type"])
        for relationship in snapshot["relationships"]
    } >= {
        (instance_arn, subnet_arn, "deployed_in_subnet"),
        (instance_arn, security_group_arn, "protected_by_security_group"),
        (subnet_arn, route_table_arn, "associated_with_route_table"),
        (route_table_arn, internet_gateway_arn, "routes_to_internet_gateway"),
    }


def test_run_foundation_discovery_collects_public_surfaces_metadata(tmp_path: Path) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)

    _, _, snapshot = run_foundation_discovery(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        client=FakeAwsClient(),
    )

    resource_map = {resource["identifier"]: resource for resource in snapshot["resources"]}
    alb_arn = "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge"
    api_arn = "arn:aws:apigateway:us-east-1::/restapis/payroll-webhook-public"

    assert resource_map[alb_arn]["metadata"]["exposure"] == "public"
    assert resource_map[alb_arn]["metadata"]["dns_public"] is True
    assert resource_map[api_arn]["metadata"]["exposure"] == "public"
    assert resource_map[api_arn]["metadata"]["public_stage"] is True


def test_run_foundation_discovery_collects_surface_to_backend_relationships(tmp_path: Path) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)

    _, _, snapshot = run_foundation_discovery(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        client=FakeAwsClient(),
    )

    resource_map = {resource["identifier"]: resource for resource in snapshot["resources"]}
    target_group_arn = "arn:aws:elasticloadbalancing:us-east-1:550192603632:targetgroup/payroll-webhook-tg/123"
    listener_arn = (
        "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge"
        "/listener/app/123/456"
    )
    integration_arn = (
        "arn:aws:apigateway:us-east-1::/restapis/payroll-webhook-public"
        "/integration/POST/webhook"
    )
    load_balancer_arn = "arn:aws:elasticloadbalancing:us-east-1:550192603632:loadbalancer/app/public-webhook-bridge"
    api_arn = "arn:aws:apigateway:us-east-1::/restapis/payroll-webhook-public"
    instance_arn = "arn:aws:ec2:us-east-1:550192603632:instance/i-0123456789abcdef0"

    assert resource_map[target_group_arn]["resource_type"] == "network.target_group"
    assert resource_map[listener_arn]["metadata"]["listener_forwarding"] is True
    assert resource_map[integration_arn]["metadata"]["integration_status"] == "active"
    assert resource_map[integration_arn]["metadata"]["target_instance"] == instance_arn

    assert {
        (relationship["source"], relationship["target"], relationship["type"])
        for relationship in snapshot["relationships"]
    } >= {
        (load_balancer_arn, listener_arn, "exposes_listener"),
        (listener_arn, target_group_arn, "forwards_to_target_group"),
        (load_balancer_arn, target_group_arn, "uses_target_group"),
        (api_arn, integration_arn, "uses_integration"),
        (integration_arn, instance_arn, "integrates_with_instance"),
    }


def test_selection_uses_discovered_listener_and_integration_relationships_for_external_entry(
    tmp_path: Path,
) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)

    _, _, snapshot = run_foundation_discovery(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "discovery",
        client=FakeAwsClient(),
    )

    snapshot["bundle"] = "aws-advanced"
    snapshot["resources"].append(
        {
            "service": "secretsmanager",
            "resource_type": "secret.secrets_manager",
            "identifier": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll/backend-db-password",
            "region": "us-east-1",
            "metadata": {
                "name": "prod/payroll/backend-db-password",
                "classification": "restricted",
                "reachable_roles": ["arn:aws:iam::123456789012:role/PayrollAppInstanceRole"],
            },
            "source": "synthetic-augmentation",
        }
    )
    snapshot["resources"].append(
        {
            "service": "iam",
            "resource_type": "identity.role",
            "identifier": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
            "region": "us-east-1",
            "metadata": {"workload": "ec2", "tier": "prod"},
            "source": "synthetic-augmentation",
        }
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=snapshot,
        output_dir=tmp_path / "selection",
        bundle_name="aws-advanced",
    )

    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")
    assert top_external["resource_arn"].endswith("prod/payroll/backend-db-password")
    assert "network_reachability_proved" in top_external["selection_reason"]
    assert "backend_reachability_proved" in top_external["selection_reason"]
    assert top_external["external_entry_reachability"]["network_reachable_from_internet"]["status"] == "proved"
    assert top_external["external_entry_reachability"]["backend_reachable"]["status"] == "proved"


def test_discovery_run_cli_reports_artifacts(tmp_path: Path, monkeypatch) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )

    def fake_discovery(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text("{}")
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, {"resources": [1, 2, 3]}

    monkeypatch.setattr("app.main.run_foundation_discovery", fake_discovery)

    result = runner.invoke(
        app,
        [
            "discovery",
            "run",
            "--bundle",
            "aws-foundation",
            "--target",
            str(target_path),
            "--authorization",
            str(authorization_path),
            "--out",
            str(tmp_path / "discovery"),
        ],
    )

    assert result.exit_code == 0
    assert "Discovery JSON:" in result.stdout
    assert "Discovery resources: 3" in result.stdout


def test_select_foundation_targets_scores_sensitive_resources(tmp_path: Path) -> None:
    discovery_snapshot = {
        "target": "local-aws-lab",
        "bundle": "aws-foundation",
        "resources": [
            {
                "service": "s3",
                "resource_type": "data_store.s3_object",
                "identifier": "arn:aws:s3:::sensitive-finance-data/payroll.csv",
                "region": "us-east-1",
                "metadata": {"bucket": "sensitive-finance-data", "object_key": "payroll.csv"},
            },
            {
                "service": "secretsmanager",
                "resource_type": "secret.secrets_manager",
                "identifier": "arn:aws:secretsmanager:us-east-1:550192603632:secret:prod/payroll-api-key",
                "region": "us-east-1",
                "metadata": {"name": "prod/payroll-api-key"},
            },
            {
                "service": "ssm",
                "resource_type": "secret.ssm_parameter",
                "identifier": "arn:aws:ssm:us-east-1:550192603632:parameter/prod/payroll/api_key",
                "region": "us-east-1",
                "metadata": {"name": "/prod/payroll/api_key"},
            },
            {
                "service": "iam",
                "resource_type": "identity.role",
                "identifier": "arn:aws:iam::550192603632:role/DataAccessRole",
                "region": "us-east-1",
                "metadata": {},
            },
        ],
    }

    json_path, md_path, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
    )

    assert json_path.exists()
    assert md_path.exists()
    assert payload["summary"]["candidates_total"] == 4
    secrets_candidate = next(
        candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-secrets"
    )
    role_candidate = next(
        candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-role-chaining"
    )
    assert secrets_candidate["confidence"] == "high"
    assert "keyword:payroll" in secrets_candidate["selection_reason"]
    assert role_candidate["resource_arn"].endswith(":role/DataAccessRole")


def test_target_selection_run_cli_reports_artifacts(tmp_path: Path) -> None:
    discovery_path = tmp_path / "discovery.json"
    discovery_path.write_text(
        json.dumps(
            {
                "target": "local-aws-lab",
                "bundle": "aws-foundation",
                "resources": [
                    {
                        "service": "s3",
                        "resource_type": "data_store.s3_object",
                        "identifier": "arn:aws:s3:::sensitive-finance-data/payroll.csv",
                        "region": "us-east-1",
                        "metadata": {},
                    }
                ],
            }
        )
    )

    result = runner.invoke(
        app,
        [
            "target-selection",
            "run",
            "--discovery",
            str(discovery_path),
            "--out",
            str(tmp_path / "targets"),
        ],
    )

    assert result.exit_code == 0
    assert "Target Candidates JSON:" in result.stdout
    assert "Target Candidates total:" in result.stdout


def test_synthesize_foundation_campaigns_writes_generated_scope_and_objective(tmp_path: Path) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)
    candidates_payload = {
        "bundle": "aws-foundation",
        "candidates": [
            {
                "id": "aws-iam-secrets:arn:aws:secretsmanager:us-east-1:550192603632:secret:prod/payroll-api-key",
                "resource_arn": "arn:aws:secretsmanager:us-east-1:550192603632:secret:prod/payroll-api-key",
                "resource_type": "secret.secrets_manager",
                "profile_family": "aws-iam-secrets",
                "score": 110,
                "confidence": "high",
            }
        ],
    }

    json_path, md_path, payload = synthesize_foundation_campaigns(
        candidates_payload=candidates_payload,
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
    )

    assert json_path.exists()
    assert md_path.exists()
    assert payload["summary"]["plans_total"] == 1
    plan = payload["plans"][0]
    generated_objective = Path(plan["generated_objective"])
    generated_scope = Path(plan["generated_scope"])
    assert generated_objective.exists()
    assert generated_scope.exists()
    assert "prod/payroll-api-key" in generated_objective.read_text()
    assert "prod/payroll-api-key" in generated_scope.read_text()


def test_campaign_synthesis_generates_target_based_objective_without_inherited_flag(tmp_path: Path) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    candidates_payload = {
        "bundle": "aws-advanced",
        "candidates": [
            {
                "id": "aws-external-entry-data:arn:aws:s3:::compute-payroll-dumps-prod/payroll/2026-03/payroll.csv",
                "resource_arn": "arn:aws:s3:::compute-payroll-dumps-prod/payroll/2026-03/payroll.csv",
                "resource_type": "data_store.s3_object",
                "profile_family": "aws-external-entry-data",
                "score": 140,
                "confidence": "high",
                "execution_fixture_set": "compute-pivot-app",
            }
        ],
    }

    _, _, payload = synthesize_foundation_campaigns(
        candidates_payload=candidates_payload,
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        profile_resolver=get_mixed_synthetic_profile,
    )

    generated_objective = Path(payload["plans"][0]["generated_objective"])
    objective_payload = json.loads(generated_objective.read_text())

    assert objective_payload["target"] == "arn:aws:s3:::compute-payroll-dumps-prod/payroll/2026-03/payroll.csv"
    assert objective_payload["success_criteria"]["mode"] == "target_observed"
    assert "flag" not in objective_payload["success_criteria"]


def test_campaign_synthesis_does_not_depend_on_profile_base_objective_file(tmp_path: Path) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    target = load_target(target_path)
    authorization = load_authorization(authorization_path).model_copy(update={"permitted_profiles": []})
    valid_scope_path = Path(__file__).resolve().parents[1] / "examples" / "scope_compute_pivot_app_iam_s3.json"

    def fake_profile_resolver(profile_name: str, _candidate: dict | None = None) -> ProfileDefinition:
        return ProfileDefinition(
            name=profile_name,
            bundle="test",
            description="Synthetic test profile",
            fixture_path=Path("/tmp/fixture-does-not-matter.json"),
            objective_path=tmp_path / "missing-objective.json",
            scope_path=valid_scope_path,
        )

    candidates_payload = {
        "bundle": "aws-foundation",
        "candidates": [
            {
                "id": "aws-iam-s3:arn:aws:s3:::compute-payroll-dumps-prod/payroll/2026-03/payroll.csv",
                "resource_arn": "arn:aws:s3:::compute-payroll-dumps-prod/payroll/2026-03/payroll.csv",
                "resource_type": "data_store.s3_object",
                "profile_family": "aws-iam-s3",
                "score": 90,
                "confidence": "high",
            }
        ],
    }

    _, _, payload = synthesize_foundation_campaigns(
        candidates_payload=candidates_payload,
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        profile_resolver=fake_profile_resolver,
    )

    generated_objective = Path(payload["plans"][0]["generated_objective"])
    objective_payload = json.loads(generated_objective.read_text())

    assert objective_payload["target"] == candidates_payload["candidates"][0]["resource_arn"]
    assert objective_payload["success_criteria"]["mode"] == "access_proved"
    assert payload["plans"][0]["fixture_path"] == "/tmp/fixture-does-not-matter.json"


def test_state_marks_objective_met_when_observation_reaches_aliased_target() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "compute_pivot_app_iam_compute_iam_lab.json")
    scope = Scope.model_validate_json(
        (Path(__file__).resolve().parents[1] / "examples" / "scope_compute_pivot_app_iam_compute_iam.json").read_text()
    )
    objective = Objective(
        description="Reach obfuscated compute pivot role",
        target="arn:aws:iam::123456789012:role/RA7",
        success_criteria={"mode": "target_observed"},
    )
    state = StateManager(
        objective=objective,
        scope=scope,
        fixture=AwsDryRunLab.from_fixture(fixture, scope),
        tool_registry=ToolRegistry.load(Path(__file__).resolve().parents[1] / "tools"),
    )
    actions = fixture.enumerate_actions(None)
    pivot_action = next(
        action
        for action in actions
        if action.target == "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/payroll-web"
    )
    observation = fixture.execute(pivot_action)
    state.apply_observation(pivot_action, observation, "reached obfuscated compute role")

    assert state.is_objective_met() is True


def test_state_requires_real_access_for_access_proved() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_iam_s3_lab.json")
    scope = Scope.model_validate_json(
        (Path(__file__).resolve().parents[1] / "examples" / "scope_internal_data_platform_iam_s3.json").read_text()
    )
    objective = Objective(
        description="Read target object with real proof",
        target="arn:aws:s3:::sensitive-finance-data/payroll.csv",
        success_criteria={"mode": "access_proved"},
    )
    state = StateManager(
        objective=objective,
        scope=scope,
        fixture=AwsDryRunLab.from_fixture(fixture, scope),
        tool_registry=ToolRegistry.load(Path(__file__).resolve().parents[1] / "tools"),
    )
    action = Action(
        action_type=ActionType.ACCESS_RESOURCE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:s3:::sensitive-finance-data/payroll.csv",
        parameters={"service": "s3"},
        tool="iam_simulate_target_access",
    )
    observation = Observation(
        success=True,
        details={"evidence": {"simulated": True}},
    )
    state.apply_observation(action, observation, "simulated access")

    assert state.is_objective_met() is False


def test_state_requires_evidence_for_access_proved() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_iam_s3_lab.json")
    scope = Scope.model_validate_json(
        (Path(__file__).resolve().parents[1] / "examples" / "scope_internal_data_platform_iam_s3.json").read_text()
    )
    objective = Objective(
        description="Read target object with real proof",
        target="arn:aws:s3:::sensitive-finance-data/payroll.csv",
        success_criteria={"mode": "access_proved"},
    )
    state = StateManager(
        objective=objective,
        scope=scope,
        fixture=AwsDryRunLab.from_fixture(fixture, scope),
        tool_registry=ToolRegistry.load(Path(__file__).resolve().parents[1] / "tools"),
    )
    action = Action(
        action_type=ActionType.ACCESS_RESOURCE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:s3:::sensitive-finance-data/payroll.csv",
        parameters={"service": "s3"},
        tool="iam_simulate_target_access",
    )
    observation = Observation(
        success=True,
        details={"simulated_policy_result": {"decision": "implicitDeny"}},
    )
    state.apply_observation(action, observation, "simulated access without evidence")

    assert state.is_objective_met() is False


def test_state_requires_real_assume_role_for_assume_role_proved() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_iam_s3_lab.json")
    scope = Scope.model_validate_json(
        (Path(__file__).resolve().parents[1] / "examples" / "scope_internal_data_platform_iam_s3.json").read_text()
    )
    objective = Objective(
        description="Assume role with real proof",
        target="arn:aws:iam::123456789012:role/AppRole",
        success_criteria={"mode": "assume_role_proved"},
    )
    state = StateManager(
        objective=objective,
        scope=scope,
        fixture=AwsDryRunLab.from_fixture(fixture, scope),
        tool_registry=ToolRegistry.load(Path(__file__).resolve().parents[1] / "tools"),
    )
    action = Action(
        action_type=ActionType.ASSUME_ROLE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:iam::123456789012:role/AppRole",
        parameters={"service": "iam"},
        tool="iam_simulate_assume_role",
    )
    observation = Observation(
        success=True,
        details={"granted_role": "arn:aws:iam::123456789012:role/AppRole"},
    )
    state.apply_observation(action, observation, "simulated assume role")

    assert state.is_objective_met() is False


def test_state_marks_objective_met_for_policy_probe_proved() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_iam_s3_lab.json")
    scope = Scope.model_validate_json(
        (Path(__file__).resolve().parents[1] / "examples" / "scope_internal_data_platform_iam_s3.json").read_text()
    )
    objective = Objective(
        description="Observe policy abuse opportunity",
        target="arn:aws:iam::123456789012:role/AppRole",
        success_criteria={"mode": "policy_probe_proved", "required_tool": "iam_create_policy_version"},
    )
    state = StateManager(
        objective=objective,
        scope=scope,
        fixture=AwsDryRunLab.from_fixture(fixture, scope),
        tool_registry=ToolRegistry.load(Path(__file__).resolve().parents[1] / "tools"),
    )
    action = Action(
        action_type=ActionType.ACCESS_RESOURCE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:iam::123456789012:role/AppRole",
        parameters={"service": "iam"},
        tool="iam_create_policy_version",
    )
    observation = Observation(
        success=True,
        details={"request_summary": {"api_calls": ["iam:SimulatePrincipalPolicy"]}},
    )
    state.apply_observation(action, observation, "policy abuse probe")

    assert state.is_objective_met() is True


def test_run_generated_campaign_can_execute_without_profile_resolver_when_plan_has_fixture_path(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    target = load_target(repo_root / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(repo_root / "examples" / "authorization_aws_foundation.local.json").model_copy(
        update={"permitted_profiles": []}
    )

    plan = {
        "profile": "aws-iam-s3",
        "fixture_path": str(repo_root / "fixtures" / "internal_data_platform_iam_s3_lab.json"),
        "generated_scope": str(repo_root / "examples" / "scope_internal_data_platform_iam_s3.json"),
        "generated_objective": str(repo_root / "examples" / "objective_internal_data_platform_iam_s3.json"),
    }

    def failing_profile_resolver(*args, **kwargs):
        raise AssertionError("profile_resolver should not be used when fixture_path is embedded in plan")

    result = run_generated_campaign(
        plan=plan,
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        runner=execute_run,
        max_steps=6,
        profile_resolver=failing_profile_resolver,
    )

    assert result.status == "passed"
    assert result.report_json is not None


def test_run_generated_campaign_builds_blind_real_runtime_without_fixture_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RASTRO_ENABLE_AWS_REAL", "1")
    target = load_target(Path("examples/target_aws_blind_real.json"))
    authorization = load_authorization(Path("examples/authorization_aws_blind_real.json"))
    scope_path = tmp_path / "scope.json"
    objective_path = tmp_path / "objective.json"
    scope_path.write_text(
        json.dumps(
            {
                "target": "aws",
                "allowed_actions": ["enumerate", "assume_role", "access_resource"],
                "allowed_resources": [
                    "arn:aws:s3:::pydavi-terraform-state/brain-k8s-lab/dev/terraform.tfstate",
                    "arn:aws:iam::123456789012:role/SyntheticRole",
                ],
                "max_steps": 6,
                "dry_run": True,
                "aws_account_ids": ["550192603632"],
                "allowed_regions": ["us-east-1"],
                "allowed_services": ["iam", "s3"],
                "authorized_by": "PydaVi",
                "authorized_at": "2026-04-04",
                "authorization_document": "docs/authorization-blind-real.md",
            }
        )
    )
    objective_path.write_text(
        json.dumps(
            {
                "description": "blind real s3 target",
                "target": "arn:aws:s3:::pydavi-terraform-state/brain-k8s-lab/dev/terraform.tfstate",
                "success_criteria": {"mode": "target_observed"},
            }
        )
    )
    plan = {
        "profile": "aws-iam-s3",
        "resource_arn": "arn:aws:s3:::pydavi-terraform-state/brain-k8s-lab/dev/terraform.tfstate",
        "generated_scope": str(scope_path),
        "generated_objective": str(objective_path),
        "fixture_path": str(Path("fixtures/mixed_generalization_iam_s3_lab.json")),
    }
    discovery_snapshot = {
        "caller_identity": {"Account": "550192603632"},
        "resources": [
            {
                "identifier": "arn:aws:iam::550192603632:role/brain-teste-4-dev-cw-role",
                "resource_type": "identity.role",
                "service": "iam",
                "metadata": {},
            }
        ],
    }
    calls: dict = {}

    def fake_runner(**kwargs):
        calls.update(kwargs)
        report_json = tmp_path / "report.json"
        report_md = tmp_path / "report.md"
        report_json.write_text("{}")
        report_md.write_text("# report\n")
        return {
            "objective_met": True,
            "preflight": {"ok": True, "details": {}},
            "report_json": report_json,
            "report_md": report_md,
            "attack_graph": tmp_path / "attack_graph.mmd",
        }

    result = run_generated_campaign(
        plan=plan,
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        runner=fake_runner,
        discovery_snapshot=discovery_snapshot,
    )

    assert result.status == "passed"
    assert calls["fixture_path"] is None
    assert calls.get("runtime_fixture") is not None
    runtime_fixture = calls["runtime_fixture"]
    actions = runtime_fixture.enumerate_actions(None)
    assert any(action.tool == "iam_passrole" for action in actions)
    assert any(action.tool == "s3_read_sensitive" for action in actions)
    assert any(action.tool == "iam_create_policy_version" for action in actions)
    assert any(action.tool == "iam_attach_role_policy" for action in actions)
    assert any(action.tool == "iam_pass_role_service_create" for action in actions)
    rewritten_scope = json.loads(scope_path.read_text())
    assert rewritten_scope["dry_run"] is False
    assert "arn:aws:iam::123456789012:role/SyntheticRole" not in rewritten_scope["allowed_resources"]
    assert "arn:aws:iam::550192603632:role/brain-teste-4-dev-cw-role" in rewritten_scope["allowed_resources"]


def test_run_generated_campaign_blind_real_privesc_profile_limits_policy_probe_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RASTRO_ENABLE_AWS_REAL", "1")
    target = load_target(Path("examples/target_aws_blind_real.json"))
    authorization = load_authorization(Path("examples/authorization_aws_blind_real.json")).model_copy(
        update={
            "permitted_profiles": [
                "aws-iam-create-policy-version-privesc",
            ]
        }
    )
    scope_path = tmp_path / "scope.json"
    objective_path = tmp_path / "objective.json"
    scope_path.write_text(
        json.dumps(
            {
                "target": "aws",
                "allowed_actions": ["enumerate", "assume_role", "access_resource"],
                "allowed_resources": ["arn:aws:iam::550192603632:role/privesc-CreatePolicyVersion-role"],
                "max_steps": 6,
                "dry_run": True,
                "aws_account_ids": ["550192603632"],
                "allowed_regions": ["us-east-1"],
                "allowed_services": ["iam"],
                "authorized_by": "PydaVi",
                "authorized_at": "2026-04-04",
                "authorization_document": "docs/authorization-blind-real.md",
            }
        )
    )
    objective_path.write_text(
        json.dumps(
            {
                "description": "blind real policy abuse probe",
                "target": "arn:aws:iam::550192603632:role/privesc-CreatePolicyVersion-role",
                "success_criteria": {
                    "mode": "policy_probe_proved",
                    "required_tool": "iam_create_policy_version",
                },
            }
        )
    )
    calls: dict = {}

    def fake_runner(**kwargs):
        calls.update(kwargs)
        report_json = tmp_path / "report.json"
        report_md = tmp_path / "report.md"
        report_json.write_text("{}")
        report_md.write_text("# report\n")
        return {
            "objective_met": True,
            "preflight": {"ok": True, "details": {}},
            "report_json": report_json,
            "report_md": report_md,
            "attack_graph": tmp_path / "attack_graph.mmd",
        }

    result = run_generated_campaign(
        plan={
            "id": "aws-iam-create-policy-version-privesc:test",
            "profile": "aws-iam-create-policy-version-privesc",
            "resource_arn": "arn:aws:iam::550192603632:role/privesc-CreatePolicyVersion-role",
            "generated_scope": str(scope_path),
            "generated_objective": str(objective_path),
        },
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        runner=fake_runner,
        discovery_snapshot={
            "caller_identity": {"Account": "550192603632"},
            "resources": [
                {
                    "identifier": "arn:aws:iam::550192603632:role/privesc-CreatePolicyVersion-role",
                    "resource_type": "identity.role",
                    "service": "iam",
                    "metadata": {},
                }
            ],
        },
    )

    assert result.status == "passed"
    runtime_fixture = calls["runtime_fixture"]
    tools = {action.tool for action in runtime_fixture.enumerate_actions(None)}
    assert "iam_create_policy_version" in tools
    assert "iam_attach_role_policy" not in tools
    assert "iam_pass_role_service_create" not in tools


def test_run_generated_campaign_uses_discovered_user_entry_identity_for_blind_real(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RASTRO_ENABLE_AWS_REAL", "1")
    target = load_target(Path("examples/target_aws_blind_real.json"))
    authorization = load_authorization(Path("examples/authorization_aws_blind_real.json"))
    scope_path = tmp_path / "scope.json"
    objective_path = tmp_path / "objective.json"
    scope_path.write_text(
        json.dumps(
            {
                "target": "aws",
                "allowed_actions": ["enumerate", "assume_role", "access_resource"],
                "allowed_resources": ["arn:aws:s3:::bucket-a/payroll.csv"],
                "max_steps": 6,
                "dry_run": True,
                "aws_account_ids": ["123456789012"],
                "allowed_regions": ["us-east-1"],
                "allowed_services": ["iam", "s3"],
                "authorized_by": "PydaVi",
                "authorized_at": "2026-04-04",
                "authorization_document": "docs/authorization-blind-real.md",
            }
        )
    )
    objective_path.write_text(
        json.dumps(
            {
                "description": "blind real per user",
                "target": "arn:aws:s3:::bucket-a/payroll.csv",
                "success_criteria": {"mode": "target_observed"},
            }
        )
    )
    calls: dict = {}

    def fake_runner(**kwargs):
        calls.update(kwargs)
        report_json = tmp_path / "report.json"
        report_md = tmp_path / "report.md"
        report_json.write_text("{}")
        report_md.write_text("# report\n")
        return {
            "objective_met": True,
            "preflight": {"ok": True, "details": {}},
            "report_json": report_json,
            "report_md": report_md,
            "attack_graph": tmp_path / "attack_graph.mmd",
        }

    result = run_generated_campaign(
        plan={
            "id": "aws-iam-s3:test-user",
            "profile": "aws-iam-s3",
            "resource_arn": "arn:aws:s3:::bucket-a/payroll.csv",
            "generated_scope": str(scope_path),
            "generated_objective": str(objective_path),
            "entry_identities": ["arn:aws:iam::123456789012:user/auditor"],
        },
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        runner=fake_runner,
        discovery_snapshot={
            "caller_identity": {"Account": "123456789012"},
            "resources": [
                {
                    "service": "iam",
                    "resource_type": "identity.role",
                    "identifier": "arn:aws:iam::123456789012:role/AppRole",
                    "region": "us-east-1",
                    "metadata": {},
                }
            ],
        },
    )

    assert result.status == "passed"
    runtime_fixture = calls["runtime_fixture"]
    actions = runtime_fixture.enumerate_actions(None)
    assert all(action.actor == "arn:aws:iam::123456789012:user/auditor" for action in actions)
    assert any(action.tool == "iam_simulate_assume_role" for action in actions)
    assert any(action.tool == "iam_simulate_target_access" for action in actions)


def test_run_generated_campaign_injects_planner_from_authorization_in_real_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RASTRO_ENABLE_AWS_REAL", "1")
    target = load_target(Path("examples/target_aws_blind_real.json"))
    authorization = load_authorization(Path("examples/authorization_aws_blind_real.json")).model_copy(
        update={"planner_config": {"backend": "openai", "model": "gpt-4o"}}
    )
    scope_path = tmp_path / "scope.json"
    objective_path = tmp_path / "objective.json"
    scope_path.write_text(
        json.dumps(
            {
                "target": "aws",
                "allowed_actions": ["enumerate", "assume_role", "access_resource"],
                "allowed_resources": ["arn:aws:s3:::bucket-a/payroll.csv"],
                "max_steps": 6,
                "dry_run": True,
                "planner": {"backend": "mock"},
                "aws_account_ids": ["123456789012"],
                "allowed_regions": ["us-east-1"],
                "allowed_services": ["iam", "s3"],
                "authorized_by": "PydaVi",
                "authorized_at": "2026-04-04",
                "authorization_document": "docs/authorization-blind-real.md",
            }
        )
    )
    objective_path.write_text(
        json.dumps(
            {
                "description": "planner injection test",
                "target": "arn:aws:s3:::bucket-a/payroll.csv",
                "success_criteria": {"mode": "target_observed"},
            }
        )
    )

    def fake_runner(**kwargs):
        report_json = tmp_path / "report.json"
        report_md = tmp_path / "report.md"
        report_json.write_text("{}")
        report_md.write_text("# report\n")
        return {
            "objective_met": True,
            "preflight": {"ok": True, "details": {}},
            "report_json": report_json,
            "report_md": report_md,
            "attack_graph": tmp_path / "attack_graph.mmd",
        }

    run_generated_campaign(
        plan={
            "profile": "aws-iam-s3",
            "resource_arn": "arn:aws:s3:::bucket-a/payroll.csv",
            "generated_scope": str(scope_path),
            "generated_objective": str(objective_path),
        },
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        runner=fake_runner,
        discovery_snapshot={
            "caller_identity": {"Account": "123456789012"},
            "resources": [],
        },
    )

    rewritten_scope = json.loads(scope_path.read_text())
    assert rewritten_scope["dry_run"] is False
    assert rewritten_scope["planner"]["backend"] == "openai"
    assert rewritten_scope["planner"]["model"] == "gpt-4o"


def test_run_generated_campaign_preserves_scope_planner_when_authorization_has_no_planner_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RASTRO_ENABLE_AWS_REAL", "1")
    target = load_target(Path("examples/target_aws_blind_real.json"))
    authorization = load_authorization(Path("examples/authorization_aws_blind_real.json"))
    assert authorization.planner_config is None
    scope_path = tmp_path / "scope.json"
    objective_path = tmp_path / "objective.json"
    scope_path.write_text(
        json.dumps(
            {
                "target": "aws",
                "allowed_actions": ["enumerate", "assume_role", "access_resource"],
                "allowed_resources": ["arn:aws:s3:::bucket-a/payroll.csv"],
                "max_steps": 6,
                "dry_run": True,
                "planner": {"backend": "mock"},
                "aws_account_ids": ["123456789012"],
                "allowed_regions": ["us-east-1"],
                "allowed_services": ["iam", "s3"],
                "authorized_by": "PydaVi",
                "authorized_at": "2026-04-04",
                "authorization_document": "docs/authorization-blind-real.md",
            }
        )
    )
    objective_path.write_text(
        json.dumps(
            {
                "description": "planner preservation test",
                "target": "arn:aws:s3:::bucket-a/payroll.csv",
                "success_criteria": {"mode": "target_observed"},
            }
        )
    )

    def fake_runner(**kwargs):
        report_json = tmp_path / "report.json"
        report_md = tmp_path / "report.md"
        report_json.write_text("{}")
        report_md.write_text("# report\n")
        return {
            "objective_met": True,
            "preflight": {"ok": True, "details": {}},
            "report_json": report_json,
            "report_md": report_md,
            "attack_graph": tmp_path / "attack_graph.mmd",
        }

    run_generated_campaign(
        plan={
            "profile": "aws-iam-s3",
            "resource_arn": "arn:aws:s3:::bucket-a/payroll.csv",
            "generated_scope": str(scope_path),
            "generated_objective": str(objective_path),
        },
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        runner=fake_runner,
        discovery_snapshot={
            "caller_identity": {"Account": "123456789012"},
            "resources": [],
        },
    )

    rewritten_scope = json.loads(scope_path.read_text())
    assert rewritten_scope["dry_run"] is False
    assert rewritten_scope["planner"]["backend"] == "mock"


def test_discovery_driven_assessment_expands_plans_for_discovered_users(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RASTRO_ENABLE_AWS_REAL", "1")
    from operations.models import TargetConfig
    target = TargetConfig(
        name="test-blind-real",
        accounts=["123456789012"],
        allowed_regions=["us-east-1"],
        entry_roles=[],
    )
    authorization = load_authorization(Path("examples/authorization_aws_blind_real.json"))
    discovery_snapshot = {
        "target": "aws-blind-real-assessment",
        "bundle": "aws-foundation",
        "caller_identity": {"Account": "123456789012"},
        "resources": [
            {
                "service": "iam",
                "resource_type": "identity.user",
                "identifier": "arn:aws:iam::123456789012:user/analyst",
                "region": "us-east-1",
                "metadata": {},
            },
            {
                "service": "iam",
                "resource_type": "identity.user",
                "identifier": "arn:aws:iam::123456789012:user/auditor",
                "region": "us-east-1",
                "metadata": {},
            },
        ],
        "relationships": [],
    }

    def fake_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    def fake_target_selector(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "bundle": "aws-foundation",
            "candidates": [
                {
                    "id": "cand:s3",
                    "resource_arn": "arn:aws:s3:::bucket-a/payroll.csv",
                    "resource_type": "data_store.s3_object",
                    "profile_family": "aws-iam-s3",
                    "score": 100,
                    "confidence": "high",
                }
            ],
        }
        p = output_dir / "target_candidates.json"
        m = output_dir / "target_candidates.md"
        p.write_text(json.dumps(payload, indent=2))
        m.write_text("# candidates\n")
        return p, m, payload

    seen_actors: list[str] = []

    def fake_runner(**kwargs):
        runtime_fixture = kwargs["runtime_fixture"]
        actors = {action.actor for action in runtime_fixture.enumerate_actions(None)}
        seen_actors.extend(sorted(actors))
        out = kwargs["output_dir"]
        out.mkdir(parents=True, exist_ok=True)
        report_json = out / "report.json"
        report_md = out / "report.md"
        actor = sorted(actors)[0]
        report_json.write_text(
            json.dumps(
                {
                    "objective": {"target": "arn:aws:s3:::bucket-a/payroll.csv"},
                    "executive_summary": {
                        "initial_identity": actor,
                        "effective_entry_identity": actor,
                        "final_resource": "arn:aws:s3:::bucket-a/payroll.csv",
                    },
                    "steps": [],
                }
            )
        )
        report_md.write_text("# report\n")
        return {
            "objective_met": True,
            "preflight": {"ok": True, "details": {}},
            "report_json": report_json,
            "report_md": report_md,
            "attack_graph": out / "attack_graph.mmd",
        }

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "assessment",
        runner=fake_runner,
        discovery_runner=fake_discovery_runner,
        target_selector=fake_target_selector,
        max_steps=4,
    )

    assert assessment.summary["campaigns_total"] == 2
    assert sorted(seen_actors) == [
        "arn:aws:iam::123456789012:user/analyst",
        "arn:aws:iam::123456789012:user/auditor",
    ]


# ---------------------------------------------------------------------------
# Bloco 1 — StrategicPlanner tests
# ---------------------------------------------------------------------------

def test_attack_hypothesis_schema_validates_valid_input() -> None:
    from planner.strategic_planner import AttackHypothesis
    h = AttackHypothesis(
        entry_identity="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:iam::123456789012:role/AdminRole",
        attack_class="role_chain",
        attack_steps=["sts:AssumeRole on AdminRole"],
        confidence="high",
        reasoning="Trust policy allows the entry identity.",
    )
    assert h.attack_class == "role_chain"
    assert h.confidence == "high"


def test_attack_hypothesis_rejects_invalid_attack_class() -> None:
    from pydantic import ValidationError
    from planner.strategic_planner import AttackHypothesis
    with pytest.raises(ValidationError):
        AttackHypothesis(
            entry_identity="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/AdminRole",
            attack_class="invalid_class",
            attack_steps=["step1"],
            confidence="high",
            reasoning="test",
        )


def test_attack_hypothesis_rejects_empty_attack_steps() -> None:
    from pydantic import ValidationError
    from planner.strategic_planner import AttackHypothesis
    with pytest.raises(ValidationError):
        AttackHypothesis(
            entry_identity="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/AdminRole",
            attack_class="role_chain",
            attack_steps=[],
            confidence="high",
            reasoning="test",
        )


def test_mock_strategic_planner_returns_hypotheses() -> None:
    from planner.strategic_mock import MockStrategicPlanner
    from planner.strategic_planner import AttackHypothesis
    from core.domain import ActionType, Scope, TargetType

    scope = Scope(
        target=TargetType.AWS,
        allowed_actions=[ActionType.ENUMERATE, ActionType.ASSUME_ROLE, ActionType.ACCESS_RESOURCE],
        allowed_resources=["*"],
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "s3", "secretsmanager"],
        authorized_by="tester",
        authorized_at="2026-04-16",
        authorization_document="docs/test.md",
    )
    snapshot = {
        "resources": [
            {
                "resource_type": "identity.role",
                "identifier": "arn:aws:iam::123456789012:role/AdminRole",
                "metadata": {"policy_escalation_signals": ["administratoraccess"]},
            },
            {
                "resource_type": "secret.secrets_manager",
                "identifier": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/key",
                "metadata": {"name": "prod-payroll-key"},
            },
            {
                "resource_type": "data_store.s3_object",
                "identifier": "arn:aws:s3:::payroll-data/2026/payroll.csv",
                "metadata": {},
            },
        ]
    }
    planner = MockStrategicPlanner()
    hypotheses = planner.plan_attacks(snapshot, ["arn:aws:iam::123456789012:user/analyst"], scope)

    assert len(hypotheses) == 3
    assert all(isinstance(h, AttackHypothesis) for h in hypotheses)
    assert all(h.entry_identity == "arn:aws:iam::123456789012:user/analyst" for h in hypotheses)
    assert all(len(h.attack_steps) >= 1 for h in hypotheses)


def test_mock_strategic_planner_detects_iam_privesc_from_escalation_signals() -> None:
    from planner.strategic_mock import MockStrategicPlanner
    from core.domain import ActionType, Scope, TargetType

    scope = Scope(
        target=TargetType.AWS,
        allowed_actions=[ActionType.ENUMERATE, ActionType.ASSUME_ROLE],
        allowed_resources=["*"],
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="t",
        authorized_at="2026-04-16",
        authorization_document="d",
    )
    snapshot = {
        "resources": [
            {
                "resource_type": "identity.role",
                "identifier": "arn:aws:iam::123456789012:role/PrivescRole",
                "metadata": {"policy_escalation_signals": ["createpolicyversion"]},
            },
        ]
    }
    planner = MockStrategicPlanner()
    hypotheses = planner.plan_attacks(snapshot, ["arn:aws:iam::123456789012:user/analyst"], scope)

    assert len(hypotheses) == 1
    assert hypotheses[0].attack_class == "iam_privesc"


def test_mock_strategic_planner_is_deterministic() -> None:
    from planner.strategic_mock import MockStrategicPlanner
    from core.domain import ActionType, Scope, TargetType

    scope = Scope(
        target=TargetType.AWS,
        allowed_actions=[ActionType.ENUMERATE],
        allowed_resources=["*"],
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="t",
        authorized_at="2026-04-16",
        authorization_document="d",
    )
    snapshot = {
        "resources": [
            {"resource_type": "identity.role", "identifier": "arn:aws:iam::123456789012:role/RoleA", "metadata": {}},
            {"resource_type": "secret.secrets_manager", "identifier": "arn:aws:secretsmanager:us-east-1:123456789012:secret:s1", "metadata": {}},
        ]
    }
    entry = ["arn:aws:iam::123456789012:user/analyst"]
    h1 = MockStrategicPlanner().plan_attacks(snapshot, entry, scope)
    h2 = MockStrategicPlanner().plan_attacks(snapshot, entry, scope)
    assert [h.model_dump() for h in h1] == [h.model_dump() for h in h2]


def test_mock_strategic_planner_returns_empty_for_no_entry_identities() -> None:
    from planner.strategic_mock import MockStrategicPlanner
    from core.domain import ActionType, Scope, TargetType

    scope = Scope(
        target=TargetType.AWS,
        allowed_actions=[ActionType.ENUMERATE],
        allowed_resources=["*"],
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="t",
        authorized_at="2026-04-16",
        authorization_document="d",
    )
    planner = MockStrategicPlanner()
    assert planner.plan_attacks({"resources": []}, [], scope) == []


def test_run_discovery_driven_with_strategic_planner_uses_hypotheses(tmp_path: Path) -> None:
    from planner.strategic_mock import MockStrategicPlanner

    target = load_target(Path("examples/target_aws_foundation.local.json"))
    authorization = load_authorization(Path("examples/authorization_aws_foundation.local.json")).model_copy(
        update={"permitted_profiles": []}
    )
    # Use the same account as target_aws_foundation.local.json (550192603632)
    account = "550192603632"
    discovery_snapshot = {
        "target": "test",
        "bundle": "aws-foundation",
        "caller_identity": {"Account": account},
        "resources": [
            {
                "resource_type": "identity.role",
                "identifier": f"arn:aws:iam::{account}:role/PayrollRole",
                "service": "iam",
                "metadata": {},
            },
            {
                "resource_type": "secret.secrets_manager",
                "identifier": f"arn:aws:secretsmanager:us-east-1:{account}:secret:prod/payroll-key",
                "service": "secretsmanager",
                "metadata": {"name": "prod-payroll-key"},
            },
        ],
        "relationships": [],
    }

    target_selector_calls: list = []

    def fake_target_selector(**kwargs):
        target_selector_calls.append(True)
        return (
            tmp_path / "candidates.json",
            tmp_path / "candidates.md",
            {"target": "test", "bundle": "aws-foundation", "derived_from": "fallback", "candidates": []},
        )

    def fake_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        p = output_dir / "discovery.json"
        m = output_dir / "discovery.md"
        p.write_text(json.dumps(discovery_snapshot))
        m.write_text("# discovery\n")
        return p, m, discovery_snapshot

    def fake_campaign_synthesizer(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        plan_json = output_dir / "campaign_plan.json"
        plan_md = output_dir / "campaign_plan.md"
        payload = {"plans": [], "summary": {"plans_total": 0}}
        plan_json.write_text(json.dumps(payload))
        plan_md.write_text("# plan\n")
        return plan_json, plan_md, payload

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "assessment",
        runner=execute_run,
        discovery_runner=fake_discovery_runner,
        target_selector=fake_target_selector,
        campaign_synthesizer=fake_campaign_synthesizer,
        strategic_planner=MockStrategicPlanner(),
        max_steps=4,
    )

    # strategic planner was used — rule-based target_selector must NOT have been called
    assert len(target_selector_calls) == 0
    assert "strategic_hypotheses_json" in assessment.artifacts
    assert Path(assessment.artifacts["strategic_hypotheses_json"]).exists()
    hypotheses_data = json.loads(Path(assessment.artifacts["strategic_hypotheses_json"]).read_text())
    assert len(hypotheses_data) == 2  # one per resource


def test_run_discovery_driven_strategic_planner_fallback_on_failure(tmp_path: Path) -> None:
    from planner.strategic_planner import StrategicPlanner

    class FailingStrategicPlanner(StrategicPlanner):
        def plan_attacks(self, *args, **kwargs):
            raise RuntimeError("LLM unavailable")

    target = load_target(Path("examples/target_aws_foundation.local.json"))
    authorization = load_authorization(Path("examples/authorization_aws_foundation.local.json")).model_copy(
        update={"permitted_profiles": []}
    )
    discovery_snapshot = {
        "target": "test",
        "bundle": "aws-foundation",
        "resources": [],
        "relationships": [],
    }

    target_selector_calls: list = []

    def fake_target_selector(**kwargs):
        target_selector_calls.append(True)
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        p = output_dir / "target_candidates.json"
        m = output_dir / "target_candidates.md"
        payload = {"target": "test", "bundle": "aws-foundation", "derived_from": "rule-based", "candidates": []}
        p.write_text(json.dumps(payload))
        m.write_text("# candidates\n")
        return p, m, payload

    def fake_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        p = output_dir / "discovery.json"
        m = output_dir / "discovery.md"
        p.write_text(json.dumps(discovery_snapshot))
        m.write_text("# discovery\n")
        return p, m, discovery_snapshot

    def fake_campaign_synthesizer(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        plan_json = output_dir / "campaign_plan.json"
        plan_md = output_dir / "campaign_plan.md"
        payload = {"plans": [], "summary": {"plans_total": 0}}
        plan_json.write_text(json.dumps(payload))
        plan_md.write_text("# plan\n")
        return plan_json, plan_md, payload

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "assessment",
        runner=execute_run,
        discovery_runner=fake_discovery_runner,
        target_selector=fake_target_selector,
        campaign_synthesizer=fake_campaign_synthesizer,
        strategic_planner=FailingStrategicPlanner(),
        max_steps=4,
    )

    # fallback activated — rule-based target_selector was called
    assert len(target_selector_calls) == 1
    assert "strategic_hypotheses_json" not in assessment.artifacts


def test_run_discovery_driven_without_strategic_planner_uses_rule_based(tmp_path: Path) -> None:
    target = load_target(Path("examples/target_aws_foundation.local.json"))
    authorization = load_authorization(Path("examples/authorization_aws_foundation.local.json")).model_copy(
        update={"permitted_profiles": []}
    )
    discovery_snapshot = {"target": "test", "resources": [], "relationships": []}

    target_selector_calls: list = []

    def fake_target_selector(**kwargs):
        target_selector_calls.append(True)
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        p = output_dir / "target_candidates.json"
        m = output_dir / "target_candidates.md"
        payload = {"target": "test", "bundle": "aws-foundation", "derived_from": "rule-based", "candidates": []}
        p.write_text(json.dumps(payload))
        m.write_text("")
        return p, m, payload

    def fake_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        p = output_dir / "discovery.json"
        m = output_dir / "discovery.md"
        p.write_text(json.dumps(discovery_snapshot))
        m.write_text("")
        return p, m, discovery_snapshot

    def fake_campaign_synthesizer(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        plan_json = output_dir / "campaign_plan.json"
        plan_md = output_dir / "campaign_plan.md"
        payload = {"plans": [], "summary": {"plans_total": 0}}
        plan_json.write_text(json.dumps(payload))
        plan_md.write_text("")
        return plan_json, plan_md, payload

    run_discovery_driven_assessment(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "assessment",
        runner=execute_run,
        discovery_runner=fake_discovery_runner,
        target_selector=fake_target_selector,
        campaign_synthesizer=fake_campaign_synthesizer,
        max_steps=4,
    )

    assert len(target_selector_calls) == 1


def test_hypotheses_to_candidates_payload_maps_attack_classes_to_profiles() -> None:
    from planner.strategic_planner import AttackHypothesis
    from operations.service import _hypotheses_to_candidates_payload

    hypotheses = [
        AttackHypothesis(
            entry_identity="arn:aws:iam::123:user/analyst",
            target="arn:aws:iam::123:role/AdminRole",
            attack_class="role_chain",
            attack_steps=["sts:AssumeRole on AdminRole"],
            confidence="high",
            reasoning="Trust policy allows analyst.",
        ),
        AttackHypothesis(
            entry_identity="arn:aws:iam::123:user/analyst",
            target="arn:aws:secretsmanager:us-east-1:123:secret:prod/key",
            attack_class="credential_access",
            attack_steps=["secretsmanager:GetSecretValue"],
            confidence="medium",
            reasoning="Role has access to secret.",
        ),
        AttackHypothesis(
            entry_identity="arn:aws:iam::123:user/analyst",
            target="arn:aws:iam::123:role/PrivescRole",
            attack_class="iam_privesc",
            attack_steps=["iam:CreatePolicyVersion on existing policy"],
            confidence="high",
            reasoning="Role can create policy versions.",
        ),
    ]
    payload = _hypotheses_to_candidates_payload(hypotheses, {"target": "test"}, "aws-iam-heavy")

    by_profile = {c["profile_family"]: c for c in payload["candidates"]}
    assert by_profile["aws-iam-role-chaining"]["resource_arn"] == "arn:aws:iam::123:role/AdminRole"
    assert by_profile["aws-iam-secrets"]["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123:secret:prod/key"
    assert by_profile["aws-iam-create-policy-version-privesc"]["resource_arn"] == "arn:aws:iam::123:role/PrivescRole"
    assert by_profile["aws-iam-role-chaining"]["score"] == 80
    assert by_profile["aws-iam-secrets"]["score"] == 50


def test_scope_enforce_hypotheses_filters_out_of_account_targets() -> None:
    from planner.strategic_planner import AttackHypothesis
    from operations.service import _scope_enforce_hypotheses
    from operations.models import TargetConfig

    target = TargetConfig(
        name="test",
        accounts=["111111111111"],
        allowed_regions=["us-east-1"],
        entry_roles=["arn:aws:iam::111111111111:user/analyst"],
    )
    hypotheses = [
        AttackHypothesis(
            entry_identity="arn:aws:iam::111111111111:user/analyst",
            target="arn:aws:iam::111111111111:role/InScopeRole",
            attack_class="role_chain",
            attack_steps=["assume role"],
            confidence="high",
            reasoning="in scope",
        ),
        AttackHypothesis(
            entry_identity="arn:aws:iam::111111111111:user/analyst",
            target="arn:aws:iam::999999999999:role/OutOfScopeRole",
            attack_class="role_chain",
            attack_steps=["assume role"],
            confidence="high",
            reasoning="out of scope",
        ),
    ]
    filtered = _scope_enforce_hypotheses(hypotheses, target)
    assert len(filtered) == 1
    assert filtered[0].target == "arn:aws:iam::111111111111:role/InScopeRole"


def test_strategic_planner_max_hypotheses_is_respected(tmp_path: Path) -> None:
    from planner.strategic_planner import AttackHypothesis, StrategicPlanner

    class BulkyStrategicPlanner(StrategicPlanner):
        def plan_attacks(self, discovery_snapshot, entry_identities, scope):
            return [
                AttackHypothesis(
                    entry_identity=entry_identities[0],
                    target=f"arn:aws:iam::123456789012:role/Role{i}",
                    attack_class="role_chain",
                    attack_steps=[f"assume Role{i}"],
                    confidence="low",
                    reasoning="generated",
                )
                for i in range(50)
            ]

    target = load_target(Path("examples/target_aws_foundation.local.json"))
    authorization = load_authorization(Path("examples/authorization_aws_foundation.local.json")).model_copy(
        update={"permitted_profiles": []}
    )
    discovery_snapshot = {"target": "test", "resources": [], "relationships": []}

    synthesizer_candidates: list = []

    def fake_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        p = output_dir / "discovery.json"
        m = output_dir / "discovery.md"
        p.write_text(json.dumps(discovery_snapshot))
        m.write_text("")
        return p, m, discovery_snapshot

    def fake_campaign_synthesizer(**kwargs):
        synthesizer_candidates.extend(kwargs["candidates_payload"].get("candidates", []))
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        plan_json = output_dir / "campaign_plan.json"
        plan_md = output_dir / "campaign_plan.md"
        payload = {"plans": [], "summary": {"plans_total": 0}}
        plan_json.write_text(json.dumps(payload))
        plan_md.write_text("")
        return plan_json, plan_md, payload

    run_discovery_driven_assessment(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "assessment",
        runner=execute_run,
        discovery_runner=fake_discovery_runner,
        campaign_synthesizer=fake_campaign_synthesizer,
        strategic_planner=BulkyStrategicPlanner(),
        max_hypotheses=5,
        max_steps=2,
    )

    assert len(synthesizer_candidates) <= 5


def test_action_shaping_prefers_direct_objective_access_globally() -> None:
    objective = Objective(
        description="read target object",
        target="arn:aws:s3:::bucket-a/payroll.csv",
        success_criteria={"mode": "target_observed"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=["enumerate", "assume_role", "access_resource"],
        allowed_resources=["arn:aws:s3:::bucket-a/payroll.csv", "arn:aws:iam::123456789012:role/AppRole"],
        dry_run=True,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "s3"],
        authorized_by="tester",
        authorized_at="2026-04-04",
        authorization_document="doc",
    )
    snapshot = StateManager(
        objective=objective,
        scope=scope,
        fixture=Fixture.load(Path("fixtures/mixed_generalization_iam_s3_lab.json")),
    ).snapshot()
    actions = [
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/AppRole",
            parameters={"service": "iam", "region": "us-east-1", "role_arn": "arn:aws:iam::123456789012:role/AppRole"},
            tool="iam_passrole",
        ),
        Action(
            action_type=ActionType.ACCESS_RESOURCE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:s3:::bucket-a/payroll.csv",
            parameters={"service": "s3", "region": "us-east-1", "bucket": "bucket-a", "object_key": "payroll.csv"},
            tool="s3_read_sensitive",
        ),
    ]

    shaped = shape_available_actions(snapshot, actions)

    assert len(shaped) == 1
    assert shaped[0].tool == "s3_read_sensitive"


def test_action_shaping_does_not_prefer_direct_access_for_assume_role_proved() -> None:
    objective = Objective(
        description="assume target role",
        target="arn:aws:iam::123456789012:role/AppRole",
        success_criteria={"mode": "assume_role_proved"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=["enumerate", "assume_role", "access_resource"],
        allowed_resources=["arn:aws:iam::123456789012:role/AppRole"],
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="tester",
        authorized_at="2026-04-04",
        authorization_document="doc",
    )
    snapshot = StateManager(
        objective=objective,
        scope=scope,
        fixture=Fixture.load(Path("fixtures/mixed_generalization_iam_s3_lab.json")),
    ).snapshot()
    actions = [
        Action(
            action_type=ActionType.ACCESS_RESOURCE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/AppRole",
            parameters={"service": "iam", "region": "us-east-1"},
            tool="iam_simulate_target_access",
        ),
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/AppRole",
            parameters={"service": "iam", "region": "us-east-1", "role_arn": "arn:aws:iam::123456789012:role/AppRole"},
            tool="iam_simulate_assume_role",
        ),
    ]

    shaped = shape_available_actions(snapshot, actions)

    assert any(action.tool == "iam_simulate_assume_role" for action in shaped)
    assert all(action.tool != "iam_simulate_target_access" for action in shaped)


def test_action_shaping_prefers_assume_role_over_analyze_for_assume_role_proved() -> None:
    objective = Objective(
        description="assume target role",
        target="arn:aws:iam::123456789012:role/AppRole",
        success_criteria={"mode": "assume_role_proved"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=["enumerate", "assume_role", "analyze"],
        allowed_resources=["arn:aws:iam::123456789012:role/AppRole"],
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="tester",
        authorized_at="2026-04-04",
        authorization_document="doc",
    )
    snapshot = StateManager(
        objective=objective,
        scope=scope,
        fixture=Fixture.load(Path("fixtures/mixed_generalization_iam_s3_lab.json")),
    ).snapshot()
    snapshot.active_branch_identities = ["arn:aws:iam::123456789012:user/analyst"]
    actions = [
        Action(
            action_type=ActionType.ANALYZE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target=None,
            parameters={},
            tool="analyze",
        ),
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/AppRole",
            parameters={"service": "iam", "region": "us-east-1", "role_arn": "arn:aws:iam::123456789012:role/AppRole"},
            tool="iam_simulate_assume_role",
        ),
    ]

    shaped = shape_available_actions(snapshot, actions)

    assert len(shaped) == 1
    assert shaped[0].action_type == ActionType.ASSUME_ROLE
    assert shaped[0].tool == "iam_simulate_assume_role"


def test_stabilize_decision_overrides_analyze_when_assume_role_commit_is_due() -> None:
    objective = Objective(
        description="assume target role",
        target="arn:aws:iam::123456789012:role/AppRole",
        success_criteria={"mode": "assume_role_proved"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=["enumerate", "assume_role", "analyze"],
        allowed_resources=["arn:aws:iam::123456789012:role/AppRole"],
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="tester",
        authorized_at="2026-04-04",
        authorization_document="doc",
    )
    snapshot = StateManager(
        objective=objective,
        scope=scope,
        fixture=Fixture.load(Path("fixtures/mixed_generalization_iam_s3_lab.json")),
    ).snapshot()
    snapshot.should_commit_to_pivot = True
    available_actions = [
        Action(
            action_type=ActionType.ANALYZE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target=None,
            parameters={},
            tool="analyze",
        ),
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/AppRole",
            parameters={"service": "iam", "region": "us-east-1", "role_arn": "arn:aws:iam::123456789012:role/AppRole"},
            tool="iam_simulate_assume_role",
        ),
    ]
    decision = Decision(
        action=available_actions[0],
        reason="No viable action.",
        planner_metadata={"planner_backend": "mock"},
    )

    stabilized = _stabilize_decision(snapshot, available_actions, decision)

    assert stabilized.action.action_type == ActionType.ASSUME_ROLE
    assert stabilized.planner_metadata["decision_stabilized"] is True
    assert stabilized.planner_metadata["stabilization_reason"] == "assume_role_commit_after_enumeration"


def test_action_shaping_filters_repeated_enumeration_with_null_target() -> None:
    objective = Objective(
        description="assume target role",
        target="arn:aws:iam::123456789012:role/AppRole",
        success_criteria={"mode": "assume_role_proved"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=["enumerate", "assume_role", "access_resource"],
        allowed_resources=["arn:aws:iam::123456789012:role/AppRole"],
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="tester",
        authorized_at="2026-04-04",
        authorization_document="doc",
    )
    snapshot = StateManager(
        objective=objective,
        scope=scope,
        fixture=Fixture.load(Path("fixtures/mixed_generalization_iam_s3_lab.json")),
    ).snapshot()
    snapshot.attempted_enumerations = [{"actor": "arn:aws:iam::123456789012:user/analyst", "target": "*"}]
    actions = [
        Action(
            action_type=ActionType.ENUMERATE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target=None,
            parameters={"service": "iam", "region": "us-east-1"},
            tool="iam_list_roles",
        ),
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/AppRole",
            parameters={"service": "iam", "region": "us-east-1", "role_arn": "arn:aws:iam::123456789012:role/AppRole"},
            tool="iam_simulate_assume_role",
        ),
    ]

    shaped = shape_available_actions(snapshot, actions)

    assert len(shaped) == 1
    assert shaped[0].tool == "iam_simulate_assume_role"


def test_real_execution_restores_direct_objective_access_even_if_tool_preconditions_filter_it() -> None:
    objective = Objective(
        description="read target object",
        target="arn:aws:s3:::bucket-a/payroll.csv",
        success_criteria={"mode": "target_observed"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=["enumerate", "assume_role", "access_resource"],
        allowed_resources=["arn:aws:s3:::bucket-a/payroll.csv"],
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "s3"],
        authorized_by="tester",
        authorized_at="2026-04-04",
        authorization_document="doc",
    )
    snapshot = StateManager(
        objective=objective,
        scope=scope,
        fixture=Fixture.load(Path("fixtures/mixed_generalization_iam_s3_lab.json")),
    ).snapshot()
    access_action = Action(
        action_type=ActionType.ACCESS_RESOURCE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:s3:::bucket-a/payroll.csv",
        parameters={"service": "s3", "region": "us-east-1", "bucket": "bucket-a", "object_key": "payroll.csv"},
        tool="s3_read_sensitive",
    )

    restored = _restore_objective_target_access_actions(snapshot, [access_action], [], scope)

    assert restored == [access_action]


def test_real_execution_does_not_restore_direct_access_for_assume_role_proved() -> None:
    objective = Objective(
        description="assume target role",
        target="arn:aws:iam::123456789012:role/AppRole",
        success_criteria={"mode": "assume_role_proved"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=["enumerate", "assume_role", "access_resource"],
        allowed_resources=["arn:aws:iam::123456789012:role/AppRole"],
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="tester",
        authorized_at="2026-04-04",
        authorization_document="doc",
    )
    snapshot = StateManager(
        objective=objective,
        scope=scope,
        fixture=Fixture.load(Path("fixtures/mixed_generalization_iam_s3_lab.json")),
    ).snapshot()
    access_action = Action(
        action_type=ActionType.ACCESS_RESOURCE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:iam::123456789012:role/AppRole",
        parameters={"service": "iam", "region": "us-east-1"},
        tool="iam_simulate_target_access",
    )

    restored = _restore_objective_target_access_actions(snapshot, [access_action], [], scope)

    assert restored == []


def test_write_assessment_summary_prefers_effective_entry_identity_for_findings(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    (campaign_dir / "report.json").write_text(
        json.dumps(
            {
                "objective": {"target": "arn:aws:s3:::bucket-a/payroll.csv"},
                "executive_summary": {
                    "initial_identity": "arn:aws:iam::123456789012:role/starting-role",
                    "effective_entry_identity": "arn:aws:iam::123456789012:role/starting-role",
                    "actual_caller_identity": "arn:aws:sts::123456789012:assumed-role/starting-role/rastro-entry-session",
                    "final_resource": "arn:aws:s3:::bucket-a/payroll.csv",
                    "proof": {"bucket": "bucket-a", "object_key": "payroll.csv"},
                },
                "execution_policy": {"allowed_services": ["s3"]},
                "mitre_techniques": [],
                "steps": [],
            }
        )
    )
    (campaign_dir / "report.md").write_text("# report\n")
    result = AssessmentResult(
        bundle="aws-foundation",
        target="lab",
        campaigns=[
            CampaignResult(
                status="passed",
                profile="aws-iam-s3",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "scope.json",
                objective_met=True,
                preflight_ok=True,
                report_json=campaign_dir / "report.json",
                report_md=campaign_dir / "report.md",
            )
        ],
    )

    write_assessment_summary(result, tmp_path)

    findings = json.loads((tmp_path / "assessment_findings.json").read_text())
    assert findings["findings"][0]["entry_point"] == "arn:aws:iam::123456789012:role/starting-role"


def test_campaign_synthesis_can_use_candidate_embedded_paths_without_profile_resolver(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    target = load_target(repo_root / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(repo_root / "examples" / "authorization_aws_foundation.local.json").model_copy(
        update={"permitted_profiles": []}
    )

    candidates_payload = {
        "bundle": "aws-advanced",
        "candidates": [
            {
                "id": "aws-external-entry-data:arn:aws:s3:::compute-payroll-dumps-prod/payroll/2026-03/payroll.csv",
                "resource_arn": "arn:aws:s3:::compute-payroll-dumps-prod/payroll/2026-03/payroll.csv",
                "resource_type": "data_store.s3_object",
                "profile_family": "aws-external-entry-data",
                "score": 140,
                "confidence": "high",
                "execution_fixture_set": "compute-pivot-app",
                "fixture_path": str(repo_root / "fixtures" / "compute_pivot_app_external_entry_lab.json"),
                "scope_template_path": str(repo_root / "examples" / "scope_compute_pivot_app_external_entry.json"),
                "external_entry_reachability": {
                    "network_reachable_from_internet": {"status": "proved", "evidence": ["surface"]},
                    "backend_reachable": {"status": "proved", "evidence": ["instance"]},
                    "credential_acquisition_possible": {"status": "structural", "evidence": ["role"]},
                    "data_path_exploitable": {"status": "not_observed", "evidence": None},
                },
            }
        ],
    }

    def failing_profile_resolver(*args, **kwargs):
        raise AssertionError("profile_resolver should not be used when candidate embeds fixture/scope paths")

    _, md_path, payload = synthesize_foundation_campaigns(
        candidates_payload=candidates_payload,
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        profile_resolver=failing_profile_resolver,
    )

    assert payload["plans"][0]["fixture_path"].endswith("compute_pivot_app_external_entry_lab.json")
    assert payload["plans"][0]["external_entry_reachability"]["network_reachable_from_internet"]["status"] == "proved"
    assert "external_entry_reachability=network=proved, backend=proved, credentials=structural" in md_path.read_text()


def test_mixed_generalization_variant_p_supports_enterprise_discovery_driven_end_to_end_without_profile_resolver(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_p.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_p_no_resolver",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_campaign_synthesis_run_cli_reports_artifacts(tmp_path: Path) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    candidates_path = tmp_path / "target_candidates.json"
    candidates_path.write_text(
        json.dumps(
            {
                "bundle": "aws-foundation",
                "candidates": [
                    {
                        "id": "aws-iam-s3:arn:aws:s3:::sensitive-finance-data/payroll.csv",
                        "resource_arn": "arn:aws:s3:::sensitive-finance-data/payroll.csv",
                        "resource_type": "data_store.s3_object",
                        "profile_family": "aws-iam-s3",
                        "score": 90,
                        "confidence": "high",
                    }
                ],
            }
        )
    )

    result = runner.invoke(
        app,
        [
            "campaign-synthesis",
            "run",
            "--candidates",
            str(candidates_path),
            "--target",
            str(target_path),
            "--authorization",
            str(authorization_path),
            "--out",
            str(tmp_path / "campaign-plan"),
        ],
    )

    assert result.exit_code == 0
    assert "Campaign Plan JSON:" in result.stdout
    assert "Campaign Plans total: 1" in result.stdout


def test_internal_data_platform_variant_a_drives_foundation_targets(tmp_path: Path) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "internal_data_platform_variant_a.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
    )

    top_s3 = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-s3")
    top_secret = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-secrets")
    top_ssm = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-ssm")

    assert top_s3["resource_arn"] == "arn:aws:s3:::idp-prod-payroll-data/payroll/2026-03.csv"
    assert top_secret["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert top_ssm["resource_arn"] == "arn:aws:ssm:us-east-1:123456789012:parameter/prod/payroll/api_key"


@pytest.mark.parametrize(
    ("fixture_name", "expected_role"),
    [
        ("internal_data_platform_variant_b.discovery.json", "arn:aws:iam::123456789012:role/PayrollDataAccessRole"),
        ("internal_data_platform_variant_c.discovery.json", "arn:aws:iam::123456789012:role/PayrollDataAccessRole"),
    ],
)
def test_internal_data_platform_variants_b_c_keep_data_access_role_on_top(
    tmp_path: Path, fixture_name: str, expected_role: str
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / fixture_name).read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
    )

    role_candidate = next(
        candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-role-chaining"
    )
    assert role_candidate["resource_arn"] == expected_role


def test_run_foundation_discovery_uses_target_override_for_ssm_prefixes(tmp_path: Path) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    target.discovery_ssm_prefixes = ["/customer"]
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    client = FakeAwsClient()

    _, _, snapshot = run_foundation_discovery(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        client=client,
    )

    assert client.parameter_path_calls == ["/customer"]
    assert snapshot["discovery_config"]["ssm_prefixes"] == ["/customer"]
    assert any(
        resource["identifier"] == "arn:aws:ssm:us-east-1:550192603632:parameter/customer/payroll/runtime_key"
        for resource in snapshot["resources"]
    )


def test_run_foundation_discovery_uses_profile_default_ssm_prefixes(tmp_path: Path) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    client = FakeAwsClient()

    _, _, snapshot = run_foundation_discovery(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        client=client,
    )

    assert client.parameter_path_calls == ["/app", "/finance", "/prod", "/shared"]
    assert snapshot["discovery_config"]["ssm_prefixes"] == ["/app", "/finance", "/prod", "/shared"]


def test_state_snapshot_derives_tool_postcondition_flags() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "internal_data_platform_iam_s3_lab.json")
    scope = Scope.model_validate_json(
        (Path(__file__).resolve().parents[1] / "examples" / "scope_internal_data_platform_iam_s3.json").read_text()
    )
    tool_registry = ToolRegistry.load(Path(__file__).resolve().parents[1] / "tools")
    state = StateManager(
        objective=Objective.model_validate_json(
            (Path(__file__).resolve().parents[1] / "examples" / "objective_internal_data_platform_iam_s3.json").read_text()
        ),
        scope=scope,
        fixture=AwsDryRunLab.from_fixture(fixture, scope),
        tool_registry=tool_registry,
    )
    first_action = fixture.enumerate_actions(None)[0]
    observation = fixture.execute(first_action)
    state.apply_observation(first_action, observation, "enumerated roles")

    snapshot = state.snapshot()
    assert "iam_roles_listed" in snapshot.fixture_state["flags"]


def test_state_marks_objective_met_when_successful_action_hits_objective_target() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "internal_data_platform_iam_s3_lab.json")
    scope = Scope.model_validate_json(
        (Path(__file__).resolve().parents[1] / "examples" / "scope_internal_data_platform_iam_s3.json").read_text()
    )
    objective = Objective.model_validate_json(
        (Path(__file__).resolve().parents[1] / "examples" / "objective_internal_data_platform_iam_s3.json").read_text()
    )
    tool_registry = ToolRegistry.load(Path(__file__).resolve().parents[1] / "tools")
    state = StateManager(
        objective=objective,
        scope=scope,
        fixture=AwsDryRunLab.from_fixture(fixture, scope),
        tool_registry=tool_registry,
    )

    enumerate_action = fixture.enumerate_actions(None)[0]
    state.apply_observation(enumerate_action, fixture.execute(enumerate_action), "enumerated roles")
    assume_action = next(
        action
        for action in fixture.enumerate_actions(None)
        if action.action_type == ActionType.ASSUME_ROLE
        and action.target == "arn:aws:iam::123456789012:role/PlatformAuditRole"
    )
    state.apply_observation(assume_action, fixture.execute(assume_action), "assumed role")
    access_action = next(
        action
        for action in fixture.enumerate_actions(None)
        if action.action_type == ActionType.ACCESS_RESOURCE
        and action.target == "arn:aws:s3:::idp-prod-payroll-data/payroll/2026-03.csv"
    )
    state.apply_observation(access_action, fixture.execute(access_action), "read payroll object")

    assert state.is_objective_met() is True


def test_state_marks_objective_met_when_tool_postcondition_flag_is_active() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "compute_pivot_app_iam_compute_iam_lab.json")
    scope = Scope.model_validate_json(
        (Path(__file__).resolve().parents[1] / "examples" / "scope_compute_pivot_app_iam_compute_iam.json").read_text()
    )
    objective = Objective.model_validate_json(
        (Path(__file__).resolve().parents[1] / "examples" / "objective_compute_pivot_app_iam_compute_iam.json").read_text()
    )
    tool_registry = ToolRegistry.load(Path(__file__).resolve().parents[1] / "tools")
    state = StateManager(
        objective=objective,
        scope=scope,
        fixture=AwsDryRunLab.from_fixture(fixture, scope),
        tool_registry=tool_registry,
    )

    enumerate_action = fixture.enumerate_actions(None)[0]
    state.apply_observation(enumerate_action, fixture.execute(enumerate_action), "enumerated roles")
    pivot_action = next(
        action
        for action in fixture.enumerate_actions(None)
        if action.action_type == ActionType.ACCESS_RESOURCE
        and action.target == "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/payroll-web"
    )
    state.apply_observation(pivot_action, fixture.execute(pivot_action), "pivoted to compute role")

    assert state.is_objective_met() is True


def test_successful_pivot_promotes_reached_role_to_active_branch_identity() -> None:
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "compute_pivot_app_external_entry_lab.json")
    scope = Scope.model_validate_json(
        (Path(__file__).resolve().parents[1] / "examples" / "scope_compute_pivot_app_external_entry.json").read_text()
    )
    objective = Objective.model_validate_json(
        (Path(__file__).resolve().parents[1] / "examples" / "objective_compute_pivot_app_external_entry.json").read_text()
    )
    tool_registry = ToolRegistry.load(Path(__file__).resolve().parents[1] / "tools")
    state = StateManager(
        objective=objective,
        scope=scope,
        fixture=AwsDryRunLab.from_fixture(fixture, scope),
        tool_registry=tool_registry,
    )

    enumerate_action = fixture.enumerate_actions(None)[0]
    state.apply_observation(enumerate_action, fixture.execute(enumerate_action), "enumerated roles")
    pivot_action = next(
        action
        for action in fixture.enumerate_actions(None)
        if action.target == "arn:aws:apigateway:us-east-1::/restapis/payroll-webhook-public"
    )
    state.apply_observation(pivot_action, fixture.execute(pivot_action), "pivoted from public surface")

    snapshot = state.snapshot()
    available = fixture.enumerate_actions(None)
    filtered = tool_registry.filter_actions(available, snapshot.fixture_state.get("flags", []))
    shaped = shape_available_actions(snapshot, filtered)

    assert "arn:aws:iam::123456789012:role/PayrollAppInstanceRole" in snapshot.active_branch_identities
    assert any(action.actor == "arn:aws:iam::123456789012:role/PayrollAppInstanceRole" for action in filtered)
    assert all(action.actor == "arn:aws:iam::123456789012:role/PayrollAppInstanceRole" for action in shaped)


def test_campaign_synthesis_merges_scope_accounts_from_candidate_resources(tmp_path: Path) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )

    _, _, payload = synthesize_foundation_campaigns(
        candidates_payload={
            "bundle": "aws-foundation",
            "candidates": [
                {
                    "id": "aws-iam-s3:arn:aws:s3:::idp-prod-payroll-data/payroll/2026-03.csv",
                    "profile_family": "aws-iam-s3",
                    "resource_arn": "arn:aws:s3:::idp-prod-payroll-data/payroll/2026-03.csv",
                    "score": 85,
                    "confidence": "high",
                }
            ],
        },
        target=target,
        authorization=authorization,
        output_dir=tmp_path,
        profile_resolver=lambda name: get_synthetic_profile("internal-data-platform", name),
    )

    generated_scope = Path(payload["plans"][0]["generated_scope"])
    scope = Scope.model_validate_json(generated_scope.read_text())
    assert "123456789012" in scope.aws_account_ids
    assert "550192603632" in scope.aws_account_ids


@pytest.mark.parametrize(
    "variant_name",
    [
        "internal_data_platform_variant_a.discovery.json",
        "internal_data_platform_variant_b.discovery.json",
        "internal_data_platform_variant_c.discovery.json",
    ],
)
def test_internal_data_platform_variants_support_discovery_driven_end_to_end(
    tmp_path: Path, variant_name: str
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / variant_name).read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / variant_name.replace(".discovery.json", ""),
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=lambda name: get_synthetic_profile("internal-data-platform", name),
        max_steps=8,
    )

    assert assessment.summary["campaigns_total"] == 4
    assert assessment.summary["campaigns_passed"] == 4


def test_serverless_business_app_variant_a_has_coherent_serverless_inventory(tmp_path: Path) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "serverless_business_app_variant_a.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
    )

    top_secret = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-secrets")
    top_ssm = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-ssm")

    assert discovery_snapshot["summary"]["roles"] == 5
    assert any(resource["resource_type"] == "compute.lambda_function" for resource in discovery_snapshot["resources"])
    assert any(resource["resource_type"] == "network.api_gateway" for resource in discovery_snapshot["resources"])
    assert top_secret["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert top_ssm["resource_arn"] == "arn:aws:ssm:us-east-1:123456789012:parameter/prod/payroll/api_key"


def test_serverless_business_app_variant_a_supports_foundation_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "serverless_business_app_variant_a.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "serverless_variant_a",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=lambda name: get_synthetic_profile("serverless-business-app", name),
        max_steps=8,
    )

    assert assessment.summary["campaigns_total"] == 4
    assert assessment.summary["campaigns_passed"] == 4


def test_serverless_business_app_variant_a_selects_advanced_lambda_and_kms_targets(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "serverless_business_app_variant_a.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-advanced",
    )

    top_lambda = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-lambda-data")
    assert top_lambda["resource_arn"] == "arn:aws:lambda:us-east-1:123456789012:function:payroll-handler"


def test_serverless_business_app_variant_b_adds_kms_without_breaking_foundation_selection(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "serverless_business_app_variant_b.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
    )

    top_secret = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-secrets")
    top_ssm = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-ssm")
    top_role = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-role-chaining")

    assert any(resource["resource_type"] == "crypto.kms_key" for resource in discovery_snapshot["resources"])
    assert any(resource["identifier"].endswith(":role/PayrollDecryptRole") for resource in discovery_snapshot["resources"])
    assert top_secret["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert top_ssm["resource_arn"] == "arn:aws:ssm:us-east-1:123456789012:parameter/prod/payroll/api_key"
    assert top_role["resource_arn"] == "arn:aws:iam::123456789012:role/PayrollHandlerRole"

    _, _, advanced_payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path / "advanced",
        bundle_name="aws-advanced",
    )
    top_kms = next(candidate for candidate in advanced_payload["candidates"] if candidate["profile_family"] == "aws-iam-kms-data")
    assert top_kms["resource_arn"] == "arn:aws:kms:us-east-1:123456789012:key/payroll-runtime"


def test_serverless_business_app_variant_c_keeps_foundation_targets_stable_under_public_api_noise(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "serverless_business_app_variant_c.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
    )

    top_secret = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-secrets")
    top_ssm = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-ssm")
    top_role = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-role-chaining")

    assert any(
        resource["identifier"] == "arn:aws:apigateway:us-east-1::/restapis/admin-public-bridge"
        for resource in discovery_snapshot["resources"]
    )
    assert top_secret["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert top_ssm["resource_arn"] == "arn:aws:ssm:us-east-1:123456789012:parameter/prod/payroll/api_key"
    assert top_role["resource_arn"] == "arn:aws:iam::123456789012:role/PayrollHandlerRole"


@pytest.mark.parametrize(
    "variant_name",
    [
        "serverless_business_app_variant_b.discovery.json",
        "serverless_business_app_variant_c.discovery.json",
    ],
)
def test_serverless_business_app_variants_b_c_support_foundation_discovery_driven_end_to_end(
    tmp_path: Path, variant_name: str
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / variant_name).read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / variant_name.replace(".discovery.json", ""),
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=lambda name: get_synthetic_profile("serverless-business-app", name),
        max_steps=8,
    )

    assert assessment.summary["campaigns_total"] == 4
    assert assessment.summary["campaigns_passed"] == 4


def test_serverless_business_app_variant_a_supports_advanced_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "serverless_business_app_variant_a.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-advanced",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "serverless_advanced_variant_a",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=lambda name: get_synthetic_profile("serverless-business-app", name),
        max_steps=8,
    )

    assert assessment.summary["campaigns_total"] == 5
    assert assessment.summary["campaigns_passed"] == 5


def test_serverless_business_app_variant_b_supports_advanced_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "serverless_business_app_variant_b.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-advanced",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "serverless_advanced_variant_b",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=lambda name: get_synthetic_profile("serverless-business-app", name),
        max_steps=8,
    )

    assert assessment.summary["campaigns_total"] == 6
    assert assessment.summary["campaigns_passed"] == 6


def test_serverless_business_app_variant_c_supports_advanced_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "serverless_business_app_variant_c.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-advanced",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "serverless_advanced_variant_c",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=lambda name: get_synthetic_profile("serverless-business-app", name),
        max_steps=8,
    )

    assert assessment.summary["campaigns_total"] == 6
    assert assessment.summary["campaigns_passed"] == 6


def test_compute_pivot_app_variant_a_has_coherent_compute_inventory_and_foundation_targets(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "compute_pivot_app_variant_a.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
    )

    top_s3 = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-s3")
    top_secret = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-secrets")
    top_ssm = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-ssm")

    assert any(resource["resource_type"] == "compute.instance_profile" for resource in discovery_snapshot["resources"])
    assert any(resource["resource_type"] == "compute.ec2_instance" for resource in discovery_snapshot["resources"])
    assert any(resource["resource_type"] == "network.load_balancer" for resource in discovery_snapshot["resources"])
    assert top_s3["resource_arn"] == "arn:aws:s3:::compute-payroll-dumps-prod/payroll/2026-03/payroll.csv"
    assert top_secret["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll/backend-db-password"
    assert top_ssm["resource_arn"] == "arn:aws:ssm:us-east-1:123456789012:parameter/prod/payroll/api_key"


def test_compute_pivot_app_variant_a_supports_foundation_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "compute_pivot_app_variant_a.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "compute_pivot_variant_a",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=lambda name: get_synthetic_profile("compute-pivot-app", name),
        max_steps=8,
    )

    assert assessment.summary["campaigns_total"] == 4
    assert assessment.summary["campaigns_passed"] == 4


def test_compute_pivot_app_variant_a_selects_compute_pivot_target_with_structural_signals(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "compute_pivot_app_variant_a.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-advanced",
    )

    top_compute = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-compute-iam")

    assert top_compute["resource_arn"] == "arn:aws:iam::123456789012:role/PayrollAppInstanceRole"
    assert "compute_linked_role" in top_compute["selection_reason"]
    assert "instance_profile_signal" in top_compute["selection_reason"]
    assert "public_compute_reachability" in top_compute["selection_reason"]


def test_compute_pivot_app_variant_a_supports_advanced_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "compute_pivot_app_variant_a.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-advanced",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "compute_pivot_advanced_variant_a",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=lambda name: get_synthetic_profile("compute-pivot-app", name),
        max_steps=8,
    )

    assert assessment.summary["campaigns_total"] == 5
    assert assessment.summary["campaigns_passed"] == 5


def test_compute_pivot_app_variant_b_selects_external_entry_target_from_structural_reachability(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "compute_pivot_app_variant_b.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-advanced",
    )

    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")
    assert top_external["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll/backend-db-password"
    assert "external_reachability_signal" in top_external["selection_reason"]
    assert "public_path_roles" in top_external["signals"]
    assert top_external["external_entry_reachability"]["network_reachable_from_internet"]["status"] == "structural"
    assert top_external["external_entry_reachability"]["backend_reachable"]["status"] == "structural"
    assert top_external["external_entry_reachability"]["credential_acquisition_possible"]["status"] == "structural"


def test_external_entry_selection_uses_api_gateway_and_alb_backend_reachability_signals(
    tmp_path: Path,
) -> None:
    discovery_snapshot = {
        "target": "compute-pivot-app-reachability-variant",
        "bundle": "aws-advanced",
        "caller_identity": {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/platform-analyst",
        },
        "resources": [
            {
                "service": "iam",
                "resource_type": "identity.role",
                "identifier": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
                "region": "us-east-1",
                "metadata": {"workload": "ec2", "tier": "prod"},
            },
            {
                "service": "ec2",
                "resource_type": "compute.instance_profile",
                "identifier": "arn:aws:iam::123456789012:instance-profile/PayrollAppProfile",
                "region": "us-east-1",
                "metadata": {"role": "arn:aws:iam::123456789012:role/PayrollAppInstanceRole"},
            },
            {
                "service": "ec2",
                "resource_type": "compute.ec2_instance",
                "identifier": "arn:aws:ec2:us-east-1:123456789012:instance/i-payrollapp04",
                "region": "us-east-1",
                "metadata": {
                    "name": "runtime-node-04",
                    "instance_profile": "arn:aws:iam::123456789012:instance-profile/PayrollAppProfile",
                    "subnet_id": "subnet-123",
                    "security_group_ids": ["sg-123"],
                },
            },
            {
                "service": "apigateway",
                "resource_type": "network.api_gateway",
                "identifier": "arn:aws:apigateway:us-east-1::/restapis/runtime-edge",
                "region": "us-east-1",
                "metadata": {
                    "exposure": "public",
                    "public_stage": True,
                    "integration_status": "active",
                    "target_instance": "arn:aws:ec2:us-east-1:123456789012:instance/i-payrollapp04",
                },
            },
            {
                "service": "elasticloadbalancing",
                "resource_type": "network.load_balancer",
                "identifier": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/runtime-edge",
                "region": "us-east-1",
                "metadata": {
                    "exposure": "public",
                    "listener_public": True,
                    "listener_forwarding": True,
                    "target_health": "healthy",
                    "target_instance": "arn:aws:ec2:us-east-1:123456789012:instance/i-payrollapp04",
                },
            },
            {
                "service": "secretsmanager",
                "resource_type": "secret.secrets_manager",
                "identifier": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/app/s1",
                "region": "us-east-1",
                "metadata": {
                    "name": "prod/app/s1",
                    "classification": "restricted",
                    "reachable_roles": ["arn:aws:iam::123456789012:role/PayrollAppInstanceRole"],
                },
            },
        ],
        "relationships": [],
    }

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-advanced",
    )

    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")

    assert "network_reachability_proved" in top_external["selection_reason"]
    assert "backend_reachability_proved" in top_external["selection_reason"]
    assert top_external["external_entry_reachability"]["network_reachable_from_internet"]["status"] == "proved"
    assert top_external["external_entry_reachability"]["backend_reachable"]["status"] == "proved"


def test_compute_pivot_app_variant_b_supports_advanced_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "compute_pivot_app_variant_b.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-advanced",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "compute_pivot_advanced_variant_b",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=lambda name: get_synthetic_profile("compute-pivot-app", name),
        max_steps=8,
    )

    assert assessment.summary["campaigns_total"] == 6
    assert assessment.summary["campaigns_passed"] == 6


def test_compute_pivot_app_variant_c_selects_cross_account_and_multi_step_targets(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "compute_pivot_app_variant_c.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_cross = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-cross-account-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_cross["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key"
    assert "cross_account_target" in top_cross["selection_reason"]
    assert "cross_account_roles" in top_cross["signals"]

    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key"
    assert "multi_step_chain" in top_multi["selection_reason"]
    assert top_multi["signals"]["pivot_chain"] == [
        "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
        "arn:aws:iam::123456789012:role/AnalyticsBrokerRole",
        "arn:aws:iam::210987654321:role/FinanceWarehouseDeepRole",
    ]


def test_compute_pivot_app_variant_c_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "compute_pivot_app_variant_c.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "compute_pivot_enterprise_variant_c",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=lambda name: get_synthetic_profile("compute-pivot-app", name),
        max_steps=9,
    )

    assert assessment.summary["campaigns_total"] == 7
    assert assessment.summary["campaigns_passed"] == 7


def test_mixed_generalization_variant_prefers_structural_candidates_over_lexical_noise(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_a.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_secrets = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-secrets")
    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")
    top_cross = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-cross-account-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_secrets["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert top_external["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert top_cross["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key"
    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key"
    assert top_multi["score_components"]["structural"] > top_multi["score_components"]["lexical"]
    assert "explicit_profile_mapping" in top_external["selection_reason"]
    assert "chain_depth_signal" in top_multi["selection_reason"]


def test_campaign_synthesis_can_dedupe_same_target_to_more_expressive_profile(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_a.discovery.json").read_text()
    )

    _, _, candidates_payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path / "candidates",
        bundle_name="aws-enterprise",
    )

    _, _, plan_payload = synthesize_foundation_campaigns(
        candidates_payload=candidates_payload,
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "plans",
        dedupe_resource_targets=True,
        profile_resolver=get_mixed_synthetic_profile,
    )

    profiles_by_resource = {plan["resource_arn"]: plan["profile"] for plan in plan_payload["plans"]}
    assert (
        profiles_by_resource["arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key"]
        == "aws-multi-step-data"
    )
    assert (
        profiles_by_resource["arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"]
        == "aws-external-entry-data"
    )


def test_mixed_generalization_variant_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_a.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_a",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=9,
    )
    assessment_json, assessment_md = write_assessment_summary(assessment, tmp_path / "mixed_generalization_variant_a")

    assert assessment.summary["campaigns_total"] == 8
    assert assessment.summary["campaigns_passed"] == 8
    assert assessment_json.exists()
    assert assessment_md.exists()
    findings_md = tmp_path / "mixed_generalization_variant_a" / "assessment_findings.md"
    assert findings_md.exists()
    findings_text = findings_md.read_text()
    assert "aws-external-entry-data" in findings_text
    assert "aws-multi-step-data" in findings_text


def test_mixed_generalization_variant_b_inferrs_profiles_without_curated_candidate_mapping(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_b.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")
    top_cross = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-cross-account-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_external["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert "inferred_profile_mapping" in top_external["selection_reason"]
    assert "aws-external-entry-data" in top_external["signals"]["inferred_profiles"]
    assert top_cross["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key"
    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key"
    assert top_external["execution_fixture_set"] == "mixed-generalization"


def test_mixed_generalization_variant_p_infers_execution_fixture_sets_structurally(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_p.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    by_profile = {candidate["profile_family"]: candidate for candidate in payload["candidates"]}

    assert by_profile["aws-external-entry-data"]["execution_fixture_set"] == "mixed-generalization"
    assert by_profile["aws-iam-compute-iam"]["execution_fixture_set"] == "compute-pivot-app"
    assert by_profile["aws-iam-lambda-data"]["execution_fixture_set"] == "serverless-business-app"
    assert by_profile["aws-iam-kms-data"]["execution_fixture_set"] == "serverless-business-app"
    assert by_profile["aws-cross-account-data"]["execution_fixture_set"] == "mixed-generalization"
    assert by_profile["aws-multi-step-data"]["execution_fixture_set"] == "mixed-generalization"
    assert by_profile["aws-external-entry-data"]["fixture_path"].endswith("mixed_generalization_external_entry_lab.json")
    assert by_profile["aws-iam-lambda-data"]["scope_template_path"].endswith(
        "scope_serverless_business_app_iam_lambda_data.json"
    )


def test_mixed_generalization_variant_p_infers_execution_fixture_sets_structurally(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_p.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    by_profile = {candidate["profile_family"]: candidate for candidate in payload["candidates"]}

    assert by_profile["aws-external-entry-data"]["execution_fixture_set"] == "mixed-generalization"
    assert by_profile["aws-iam-compute-iam"]["execution_fixture_set"] == "compute-pivot-app"
    assert by_profile["aws-iam-lambda-data"]["execution_fixture_set"] == "serverless-business-app"
    assert by_profile["aws-iam-kms-data"]["execution_fixture_set"] == "serverless-business-app"
    assert by_profile["aws-cross-account-data"]["execution_fixture_set"] == "mixed-generalization"
    assert by_profile["aws-multi-step-data"]["execution_fixture_set"] == "mixed-generalization"


def test_mixed_generalization_variant_b_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_b.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_b",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=9,
    )

    assert assessment.summary["campaigns_total"] == 8
    assert assessment.summary["campaigns_passed"] == 8


def test_mixed_generalization_variant_c_keeps_best_targets_on_top_under_same_surface_competition(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_c.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_s3 = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-s3")
    top_secrets = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-secrets")
    top_ssm = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-ssm")
    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_s3["resource_arn"] == "arn:aws:s3:::mixed-payroll-data-prod/payroll/2026-03/payroll.csv"
    assert top_secrets["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert top_ssm["resource_arn"] == "arn:aws:ssm:us-east-1:123456789012:parameter/prod/payroll/api_key"
    assert top_external["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key"


def test_mixed_generalization_variant_c_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_c.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_c",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=9,
    )

    assert assessment.summary["campaigns_total"] == 8
    assert assessment.summary["campaigns_passed"] == 8


def test_mixed_generalization_variant_d_prefers_higher_quality_public_entry_path(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_d.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")
    assert top_external["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert "public_role_quality_signal" in top_external["selection_reason"]
    assert top_external["signals"]["public_role_score"] > 0
    webhook = next(
        candidate
        for candidate in payload["candidates"]
        if candidate["profile_family"] == "aws-external-entry-data"
        and candidate["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-webhook-password"
    )
    assert webhook["signals"]["public_role_score"] < top_external["signals"]["public_role_score"]


def test_mixed_generalization_resolver_uses_execution_fixture_set_from_plan() -> None:
    serverless_profile = get_mixed_synthetic_profile(
        "aws-iam-kms-data",
        {"execution_fixture_set": "serverless-business-app", "resource_arn": "arn:aws:kms:us-east-1:123456789012:key/payroll-runtime"},
    )
    compute_profile = get_mixed_synthetic_profile(
        "aws-external-entry-data",
        {"execution_fixture_set": "compute-pivot-app", "resource_arn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"},
    )
    mixed_profile = get_mixed_synthetic_profile(
        "aws-iam-s3",
        {"execution_fixture_set": "mixed-generalization", "resource_arn": "arn:aws:s3:::mixed-payroll-data-prod/payroll/2026-03/payroll.csv"},
    )

    assert "serverless_business_app_unified_lab.json" in str(serverless_profile.fixture_path)
    assert "compute_pivot_app_unified_lab.json" in str(compute_profile.fixture_path)
    assert "mixed_generalization_iam_s3_lab.json" in str(mixed_profile.fixture_path)


def test_mixed_generalization_variant_d_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_d.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_d",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=9,
    )

    assert assessment.summary["campaigns_total"] == 8
    assert assessment.summary["campaigns_passed"] == 8


def test_mixed_generalization_variant_e_prefers_deeper_multi_step_but_keeps_cross_account_direct(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_e.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")
    top_cross = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-cross-account-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_external["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert top_cross["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key"
    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-master-api-key"
    assert top_multi["signals"]["chain_depth"] == 4


def test_mixed_generalization_variant_e_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_e.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_e",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_mixed_generalization_variant_f_infers_structural_paths_from_relationships(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_f.discovery.json").read_text()
    )

    resource_map = {resource["identifier"]: resource for resource in discovery_snapshot["resources"]}
    assert "reachable_roles" not in resource_map[
        "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-master-api-key"
    ]["metadata"]
    assert "pivot_chain" not in resource_map[
        "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-master-api-key"
    ]["metadata"]

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")
    top_cross = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-cross-account-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_external["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert top_cross["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key"
    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-master-api-key"
    assert top_cross["signals"]["pivot_chain"] == [
        "arn:aws:iam::123456789012:role/PayrollAppInstanceRole",
        "arn:aws:iam::123456789012:role/AnalyticsBrokerRole",
        "arn:aws:iam::210987654321:role/FinanceWarehouseDeepRole",
    ]
    assert top_multi["signals"]["chain_depth"] == 4
    assert top_multi["signals"]["reachable_roles"] == [
        "arn:aws:iam::210987654321:role/FinanceWarehouseRelayRole",
    ]


def test_mixed_generalization_variant_f_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_f.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_f",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_mixed_generalization_variant_g_removes_semantic_tags_and_stays_stable(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_g.discovery.json").read_text()
    )

    for resource in discovery_snapshot["resources"]:
        assert "semantic_tags" not in resource.get("metadata", {})

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")
    top_cross = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-cross-account-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_external["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert top_cross["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key"
    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-master-api-key"


def test_mixed_generalization_variant_g_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_g.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_g",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_mixed_generalization_variant_h_obfuscates_pivot_names_and_stays_stable(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_h.discovery.json").read_text()
    )

    role_ids = {
        resource["identifier"]
        for resource in discovery_snapshot["resources"]
        if resource["resource_type"] == "identity.role"
    }
    assert "arn:aws:iam::123456789012:role/PayrollAppInstanceRole" not in role_ids
    assert "arn:aws:iam::123456789012:role/LegacyWebhookBridgeRole" not in role_ids

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")
    top_cross = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-cross-account-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_external["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key"
    assert top_cross["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key"
    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-master-api-key"
    assert top_external["signals"]["public_path_roles"] == ["arn:aws:iam::123456789012:role/RA7"]


def test_mixed_generalization_variant_h_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_h.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_h",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_mixed_generalization_variant_i_obfuscates_enterprise_target_names(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_i.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_cross = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-cross-account-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_cross["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/ops/core-api-key"
    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/ops/core-master-api-key"
    assert "finance" not in top_cross["resource_arn"]
    assert "warehouse" not in top_multi["resource_arn"]


def test_mixed_generalization_variant_i_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_i.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_i",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_mixed_generalization_variant_j_reduces_enterprise_keyword_support(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_j.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_cross = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-cross-account-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_cross["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/ops/core-a"
    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/ops/core-b"
    assert "api_key" not in top_cross["signals"]["keyword_hits"]
    assert "api_key" not in top_multi["signals"]["keyword_hits"]
    assert top_multi["score_components"]["structural"] > top_multi["score_components"]["lexical"]


def test_mixed_generalization_variant_j_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_j.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_j",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_mixed_generalization_variant_k_obfuscates_local_s3_and_ssm_targets(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_k.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_s3 = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-s3")
    top_ssm = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-ssm")

    assert top_s3["resource_arn"] == "arn:aws:s3:::mixed-payroll-data-prod/data/2026-03/r1.bin"
    assert top_ssm["resource_arn"] == "arn:aws:ssm:us-east-1:123456789012:parameter/prod/app/cfg_a"
    assert "api_key" not in top_ssm["signals"]["keyword_hits"]


def test_mixed_generalization_variant_k_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_k.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_k",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_mixed_generalization_variant_l_obfuscates_local_secret_and_shifts_external_entry(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_l.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_secrets = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-secrets")
    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")

    assert top_secrets["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/sys/kv_a"
    assert top_external["resource_arn"] == "arn:aws:s3:::mixed-payroll-data-prod/data/2026-03/r1.bin"
    assert top_external["resource_type"] == "data_store.s3_object"


def test_mixed_generalization_variant_l_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_l.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_l",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_mixed_generalization_variant_m_further_obfuscates_local_secret_and_preserves_external_entry(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_m.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_secrets = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-secrets")
    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")

    assert top_secrets["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/app/s1"
    assert top_external["resource_arn"] == "arn:aws:s3:::mixed-payroll-data-prod/data/2026-03/r1.bin"
    assert top_external["resource_type"] == "data_store.s3_object"


def test_mixed_generalization_variant_m_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_m.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_m",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_mixed_generalization_variant_n_obfuscates_enterprise_deep_targets_with_low_lexical_support(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_n.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_cross = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-cross-account-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_cross["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/x/t1"
    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/x/t2"
    assert top_cross["score_components"]["structural"] > top_cross["score_components"]["lexical"]
    assert top_multi["score_components"]["structural"] > top_multi["score_components"]["lexical"]


def test_mixed_generalization_variant_n_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_n.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_n",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_mixed_generalization_variant_o_uses_fixture_alias_support_for_local_and_enterprise_targets(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_o.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_secrets = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-secrets")
    top_cross = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-cross-account-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_secrets["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/r/a1"
    assert top_cross["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/r/e1"
    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/r/e2"


def test_mixed_generalization_variant_o_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_o.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_o",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_mixed_generalization_variant_p_reduces_curated_metadata_and_preserves_selection(
    tmp_path: Path,
) -> None:
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_p.discovery.json").read_text()
    )

    _, _, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=tmp_path,
        bundle_name="aws-enterprise",
    )

    top_secrets = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-iam-secrets")
    top_external = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-external-entry-data")
    top_cross = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-cross-account-data")
    top_multi = next(candidate for candidate in payload["candidates"] if candidate["profile_family"] == "aws-multi-step-data")

    assert top_secrets["resource_arn"] == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/r/a1"
    assert top_external["resource_arn"] == "arn:aws:s3:::mixed-payroll-data-prod/data/2026-03/r1.bin"
    assert top_cross["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/r/e1"
    assert top_multi["resource_arn"] == "arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/r/e2"


def test_mixed_generalization_variant_p_supports_enterprise_discovery_driven_end_to_end(
    tmp_path: Path,
) -> None:
    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json")
    authorization = load_authorization(
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    authorization = authorization.model_copy(update={"permitted_profiles": []})
    discovery_snapshot = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_variant_p.discovery.json").read_text()
    )

    def synthetic_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text(json.dumps(discovery_snapshot, indent=2))
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, discovery_snapshot

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-enterprise",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "mixed_generalization_variant_p",
        runner=execute_run,
        discovery_runner=synthetic_discovery_runner,
        profile_resolver=get_mixed_synthetic_profile,
        dedupe_resource_targets=True,
        max_steps=10,
    )

    assert assessment.summary["campaigns_total"] == 9
    assert assessment.summary["campaigns_passed"] == 9


def test_run_discovery_driven_assessment_generates_artifacts_and_campaigns(tmp_path: Path) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)

    def fake_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        report_json = output_dir / "report.json"
        report_md = output_dir / "report.md"
        graph = output_dir / "attack_graph.mmd"
        report_json.write_text("{}")
        report_md.write_text("# report\n")
        graph.write_text("graph TD\n")
        return {
            "objective_met": True,
            "preflight": {"ok": True, "details": {"account_id": "550192603632"}},
            "report_json": report_json,
            "report_md": report_md,
            "attack_graph": graph,
        }

    def fake_discovery_runner(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery_json = output_dir / "discovery.json"
        discovery_md = output_dir / "discovery.md"
        discovery_json.write_text("{}")
        discovery_md.write_text("# discovery\n")
        return discovery_json, discovery_md, {"target": "local-aws-lab", "bundle": "aws-foundation", "resources": []}

    def fake_target_selector(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        candidates_json = output_dir / "target_candidates.json"
        candidates_md = output_dir / "target_candidates.md"
        candidates_json.write_text("{}")
        candidates_md.write_text("# candidates\n")
        return candidates_json, candidates_md, {
            "bundle": "aws-foundation",
            "candidates": [
                {
                    "id": "aws-iam-s3:arn:aws:s3:::sensitive-finance-data/payroll.csv",
                    "profile_family": "aws-iam-s3",
                    "resource_arn": "arn:aws:s3:::sensitive-finance-data/payroll.csv",
                    "score": 90,
                    "confidence": "high",
                },
                {
                    "id": "aws-iam-secrets:arn:aws:secretsmanager:us-east-1:550192603632:secret:prod/payroll-api-key",
                    "profile_family": "aws-iam-secrets",
                    "resource_arn": "arn:aws:secretsmanager:us-east-1:550192603632:secret:prod/payroll-api-key",
                    "score": 110,
                    "confidence": "high",
                },
                {
                    "id": "aws-iam-ssm:arn:aws:ssm:us-east-1:550192603632:parameter/prod/payroll/api_key",
                    "profile_family": "aws-iam-ssm",
                    "resource_arn": "arn:aws:ssm:us-east-1:550192603632:parameter/prod/payroll/api_key",
                    "score": 105,
                    "confidence": "high",
                },
                {
                    "id": "aws-iam-role-chaining:arn:aws:iam::550192603632:role/DataAccessRole",
                    "profile_family": "aws-iam-role-chaining",
                    "resource_arn": "arn:aws:iam::550192603632:role/DataAccessRole",
                    "score": 40,
                    "confidence": "medium",
                },
            ],
        }

    def fake_campaign_synthesizer(**kwargs):
        output_dir = kwargs["output_dir"]
        generated = output_dir / "generated"
        generated.mkdir(parents=True, exist_ok=True)
        campaign_plan_json = output_dir / "campaign_plan.json"
        campaign_plan_md = output_dir / "campaign_plan.md"
        campaign_plan_json.write_text("{}")
        campaign_plan_md.write_text("# plan\n")
        plans = []
        for candidate in kwargs["candidates_payload"]["candidates"]:
            profile = candidate["profile_family"]
            plan_dir = generated / profile
            plan_dir.mkdir(parents=True, exist_ok=True)
            objective = plan_dir / "objective.generated.json"
            scope = plan_dir / "scope.generated.json"
            objective.write_text("{}")
            scope.write_text('{"allowed_actions": ["enumerate", "access_resource"], "allowed_resources": ["*"]}')
            plans.append(
                {
                    "profile": profile,
                    "generated_objective": str(objective),
                    "generated_scope": str(scope),
                }
            )
        return campaign_plan_json, campaign_plan_md, {"plans": plans}

    assessment = run_discovery_driven_assessment(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "assessment",
        runner=fake_runner,
        discovery_runner=fake_discovery_runner,
        target_selector=fake_target_selector,
        campaign_synthesizer=fake_campaign_synthesizer,
    )

    assert assessment.summary["assessment_ok"] is True
    assert len(assessment.campaigns) == 4
    assert "discovery_json" in assessment.artifacts
    assert Path(assessment.artifacts["campaign_plan_json"]).exists()


def test_assessment_run_cli_supports_discovery_driven(tmp_path: Path, monkeypatch) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )

    def fake_discovery_assessment(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        campaign_dir = output_dir / "campaigns" / "aws-iam-s3"
        campaign_dir.mkdir(parents=True, exist_ok=True)
        (campaign_dir / "report.json").write_text(
            json.dumps(
                {
                    "objective": {"target": "arn:aws:s3:::sensitive-finance-data/payroll.csv"},
                    "executive_summary": {
                        "initial_identity": "arn:aws:iam::550192603632:user/brainctl-user",
                        "final_resource": "arn:aws:s3:::sensitive-finance-data/payroll.csv",
                    },
                    "execution_policy": {"allowed_services": ["iam", "sts", "s3"]},
                    "mitre_techniques": [],
                    "steps": [],
                }
            )
        )
        (campaign_dir / "report.md").write_text("# report\n")
        return AssessmentResult(
            bundle="aws-foundation",
            target="local-aws-lab",
            summary={"assessment_ok": True, "campaigns_total": 1},
            artifacts={"discovery_json": str(output_dir / "discovery.json")},
            campaigns=[
                CampaignResult(
                    status="passed",
                    profile="aws-iam-s3",
                    output_dir=campaign_dir,
                    generated_scope=campaign_dir / "scope.generated.json",
                    objective_met=True,
                    preflight_ok=True,
                    report_json=campaign_dir / "report.json",
                    report_md=campaign_dir / "report.md",
                )
            ],
        )

    monkeypatch.setattr("app.main.run_discovery_driven_assessment", fake_discovery_assessment)

    result = runner.invoke(
        app,
        [
            "assessment",
            "run",
            "--bundle",
            "aws-foundation",
            "--target",
            str(target_path),
            "--authorization",
            str(authorization_path),
            "--out",
            str(tmp_path / "assessment"),
            "--discovery-driven",
        ],
    )

    assert result.exit_code == 0
    assert "Assessment JSON:" in result.stdout
    assert "Assessment MD:" in result.stdout
    assert "Findings JSON:" in result.stdout
    assert "Findings MD:" in result.stdout


def test_campaign_and_assessment_orchestration_use_runner(tmp_path: Path) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        report_json = output_dir / "report.json"
        report_md = output_dir / "report.md"
        graph = output_dir / "attack_graph.mmd"
        report_json.write_text("{}")
        report_md.write_text("# report\n")
        graph.write_text("graph TD\n")
        return {
            "objective_met": True,
            "preflight": {"ok": True, "details": {"account_id": "550192603632"}},
            "report_json": report_json,
            "report_md": report_md,
            "attack_graph": graph,
        }

    campaign = run_campaign(
        profile_name="aws-iam-s3",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "campaign",
        runner=fake_runner,
    )
    assessment = run_assessment(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "assessment",
        runner=fake_runner,
    )

    assert campaign.objective_met is True
    assert campaign.status == "passed"
    assert campaign.preflight_ok is True
    assert calls[0]["fixture_path"].name == "aws_role_choice_lab.local.json"
    assert (tmp_path / "campaign" / "aws-iam-s3.scope.json").exists()
    assert len(assessment.campaigns) == 4
    assert assessment.summary["campaigns_total"] == 4
    assert assessment.summary["assessment_ok"] is True


def test_write_assessment_summary_includes_preflight_and_scope(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    (campaign_dir / "report.json").write_text(
        json.dumps(
            {
                "objective": {
                    "target": "arn:aws:s3:::sensitive-finance-data/payroll.csv",
                },
                "executive_summary": {
                    "initial_identity": "arn:aws:iam::550192603632:user/brainctl-user",
                    "final_resource": "arn:aws:s3:::sensitive-finance-data/payroll.csv",
                    "proof": {
                        "bucket": "sensitive-finance-data",
                        "object_key": "payroll.csv",
                    },
                },
                "execution_policy": {
                    "allowed_services": ["iam", "sts", "s3"],
                },
                "mitre_techniques": [
                    {"mitre_id": "T1530"},
                ],
                "steps": [
                    {
                        "action": {
                            "actor": "arn:aws:iam::550192603632:user/brainctl-user",
                            "target": "arn:aws:iam::550192603632:role/AuditRole",
                        }
                    },
                    {
                        "action": {
                            "actor": "arn:aws:iam::550192603632:role/AuditRole",
                            "target": "arn:aws:s3:::sensitive-finance-data/payroll.csv",
                        }
                    },
                ],
            }
        )
    )
    (campaign_dir / "report.md").write_text("# report\n")

    result = AssessmentResult(
        bundle="aws-foundation",
        target="local-aws-lab",
        campaigns=[
            CampaignResult(
                status="passed",
                profile="aws-iam-s3",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "aws-iam-s3.scope.json",
                objective_met=True,
                preflight_ok=True,
                preflight_details={"account_id": "550192603632"},
                report_json=campaign_dir / "report.json",
                report_md=campaign_dir / "report.md",
            )
        ],
    )

    _, assessment_md = write_assessment_summary(result, tmp_path)

    content = assessment_md.read_text()
    assert result.summary["assessment_ok"] is True
    assert "Campaigns preflight failed: 0" in content
    assert "Assessment OK: True" in content
    assert "Campaigns passed: 1" in content
    assert "scope=" in content
    assert "report=" in content
    assert result.artifacts["assessment_findings_json"].endswith("assessment_findings.json")
    findings_md = Path(result.artifacts["assessment_findings_md"])
    assert findings_md.exists()
    findings_content = findings_md.read_text()
    assert "IAM -> S3 exposure" in findings_content
    assert "s3://sensitive-finance-data/payroll.csv" in findings_content


def test_write_assessment_summary_external_entry_uses_maturity_language(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    (campaign_dir / "report.json").write_text(
        json.dumps(
            {
                "objective": {
                    "target": "arn:aws:s3:::compute-payroll-dumps-prod/payroll/2026-03/payroll.csv",
                },
                "executive_summary": {
                    "initial_identity": "arn:aws:iam::550192603632:user/brainctl-user",
                    "final_resource": "arn:aws:s3:::compute-payroll-dumps-prod/payroll/2026-03/payroll.csv",
                    "proof": {
                        "entry_surface": "payroll-webhook-public",
                        "reached_role": "arn:aws:iam::550192603632:role/PublicPayrollAppRole",
                    },
                    "external_entry_maturity": {
                        "applicable": True,
                        "classification": "public_exposure_structurally_linked_to_privileged_path",
                        "network_reachable_from_internet": {"status": "structural", "evidence": None},
                        "backend_reachable": {"status": "structural", "evidence": None},
                        "credential_acquisition_possible": {"status": "proved", "evidence": None},
                        "data_path_exploitable": {"status": "proved", "evidence": None},
                    },
                },
                "execution_policy": {
                    "allowed_services": ["ec2", "iam", "sts", "s3"],
                },
                "mitre_techniques": [],
                "steps": [],
            }
        )
    )
    (campaign_dir / "report.md").write_text("# report\n")

    result = AssessmentResult(
        bundle="aws-advanced",
        target="local-aws-lab",
        campaigns=[
            CampaignResult(
                status="passed",
                profile="aws-external-entry-data",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "aws-external-entry-data.scope.json",
                objective_met=True,
                preflight_ok=True,
                preflight_details={"account_id": "550192603632"},
                report_json=campaign_dir / "report.json",
                report_md=campaign_dir / "report.md",
            )
        ],
    )

    write_assessment_summary(result, tmp_path)

    findings_content = Path(result.artifacts["assessment_findings_md"]).read_text()
    assert "Public exposure structurally linked to privileged path." in findings_content
    assert "public exploit path proved end-to-end" not in findings_content


def test_write_assessment_summary_deduplicates_findings_with_same_report(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    report_json = campaign_dir / "report.json"
    report_json.write_text(
        json.dumps(
            {
                "objective": {"target": "arn:aws:s3:::sensitive-finance-data/payroll.csv"},
                "executive_summary": {
                    "initial_identity": "arn:aws:iam::123456789012:user/analyst",
                    "final_resource": "arn:aws:s3:::sensitive-finance-data/payroll.csv",
                    "proof": {"bucket": "sensitive-finance-data", "object_key": "payroll.csv"},
                },
                "execution_policy": {"allowed_services": ["s3"]},
                "mitre_techniques": [],
                "steps": [
                    {
                        "action": {
                            "action_type": "access_resource",
                            "actor": "arn:aws:iam::123456789012:user/analyst",
                            "target": "arn:aws:s3:::sensitive-finance-data/payroll.csv",
                        },
                        "observation": {"success": True, "details": {"evidence": {"bucket": "sensitive-finance-data"}}},
                    }
                ],
            }
        )
    )
    (campaign_dir / "report.md").write_text("# report\n")
    result = AssessmentResult(
        bundle="aws-foundation",
        target="lab",
        campaigns=[
            CampaignResult(
                status="passed",
                campaign_id="plan-1",
                profile="aws-iam-s3",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "a.scope.json",
                objective_met=True,
                preflight_ok=True,
                report_json=report_json,
                report_md=campaign_dir / "report.md",
            ),
            CampaignResult(
                status="passed",
                campaign_id="plan-2",
                profile="aws-iam-s3",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "b.scope.json",
                objective_met=True,
                preflight_ok=True,
                report_json=report_json,
                report_md=campaign_dir / "report.md",
            ),
        ],
    )

    write_assessment_summary(result, tmp_path)

    findings = json.loads((tmp_path / "assessment_findings.json").read_text())
    assert findings["summary"]["findings_total"] == 1
    assert findings["summary"]["source_campaign_findings_total"] == 2
    assert findings["summary"]["distinct_paths_total"] == 1
    assert findings["summary"]["principal_multiplicity_total"] == 1
    assert findings["summary"]["additional_principal_observations"] == 0
    assert findings["summary"]["validated_findings"] == 1
    finding = findings["findings"][0]
    assert finding["principal_multiplicity"] == 1
    assert finding["finding_state"] == "validated_impact"
    assert finding["distinct_path_key"]


def test_write_assessment_summary_collapses_same_path_across_multiple_principals(tmp_path: Path) -> None:
    campaign_a = tmp_path / "campaign-a"
    campaign_b = tmp_path / "campaign-b"
    campaign_a.mkdir(parents=True, exist_ok=True)
    campaign_b.mkdir(parents=True, exist_ok=True)

    report_payload = {
        "objective": {"target": "arn:aws:s3:::sensitive-finance-data/payroll.csv"},
        "executive_summary": {
            "final_resource": "arn:aws:s3:::sensitive-finance-data/payroll.csv",
        },
        "execution_policy": {"allowed_services": ["s3"]},
        "mitre_techniques": [],
        "steps": [
            {
                "action": {
                    "action_type": "access_resource",
                    "tool": "s3_read_sensitive",
                    "target": "arn:aws:s3:::sensitive-finance-data/payroll.csv",
                },
                "observation": {
                    "success": True,
                    "details": {"evidence": {"bucket": "sensitive-finance-data"}},
                },
            }
        ],
    }
    report_a = {
        **report_payload,
        "executive_summary": {
            **report_payload["executive_summary"],
            "effective_entry_identity": "arn:aws:iam::123456789012:user/analyst",
        },
        "steps": [
            {
                **report_payload["steps"][0],
                "action": {
                    **report_payload["steps"][0]["action"],
                    "actor": "arn:aws:iam::123456789012:user/analyst",
                },
            }
        ],
    }
    report_b = {
        **report_payload,
        "executive_summary": {
            **report_payload["executive_summary"],
            "effective_entry_identity": "arn:aws:iam::123456789012:user/auditor",
        },
        "steps": [
            {
                **report_payload["steps"][0],
                "action": {
                    **report_payload["steps"][0]["action"],
                    "actor": "arn:aws:iam::123456789012:user/auditor",
                },
            }
        ],
    }
    (campaign_a / "report.json").write_text(json.dumps(report_a))
    (campaign_b / "report.json").write_text(json.dumps(report_b))
    (campaign_a / "report.md").write_text("# report\n")
    (campaign_b / "report.md").write_text("# report\n")

    result = AssessmentResult(
        bundle="aws-foundation",
        target="lab",
        campaigns=[
            CampaignResult(
                status="passed",
                campaign_id="plan-1",
                profile="aws-iam-s3",
                output_dir=campaign_a,
                generated_scope=campaign_a / "scope.json",
                objective_met=True,
                preflight_ok=True,
                report_json=campaign_a / "report.json",
                report_md=campaign_a / "report.md",
            ),
            CampaignResult(
                status="passed",
                campaign_id="plan-2",
                profile="aws-iam-s3",
                output_dir=campaign_b,
                generated_scope=campaign_b / "scope.json",
                objective_met=True,
                preflight_ok=True,
                report_json=campaign_b / "report.json",
                report_md=campaign_b / "report.md",
            ),
        ],
    )

    write_assessment_summary(result, tmp_path)

    findings = json.loads((tmp_path / "assessment_findings.json").read_text())
    assert findings["summary"]["findings_total"] == 1
    assert findings["summary"]["source_campaign_findings_total"] == 2
    assert findings["summary"]["distinct_paths_total"] == 1
    assert findings["summary"]["principal_multiplicity_total"] == 2
    assert findings["summary"]["additional_principal_observations"] == 1
    assert findings["summary"]["paths_with_multiple_principals"] == 1
    assert findings["summary"]["principal_multiplicity_by_profile"]["aws-iam-s3"] == 2
    finding = findings["findings"][0]
    assert finding["principal_multiplicity"] == 2
    assert finding["entry_points"] == [
        "arn:aws:iam::123456789012:user/analyst",
        "arn:aws:iam::123456789012:user/auditor",
    ]
    assert finding["finding_state"] == "exploited"
    assert "access_resource:s3_read_sensitive:objective_target" in finding["distinct_path_key"]
    findings_md = (tmp_path / "assessment_findings.md").read_text()
    assert "Distinct paths total: 1" in findings_md
    assert "Additional principal observations: 1" in findings_md


def test_role_chaining_without_proof_is_observed_not_validated(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    (campaign_dir / "report.json").write_text(
        json.dumps(
            {
                "objective": {"target": "arn:aws:iam::123456789012:role/TargetRole"},
                "executive_summary": {
                    "initial_identity": "arn:aws:iam::123456789012:user/analyst",
                    "final_resource": "arn:aws:iam::123456789012:role/TargetRole",
                    "proof": None,
                },
                "execution_policy": {"allowed_services": ["iam"]},
                "mitre_techniques": [],
                "steps": [
                    {
                        "action": {
                            "action_type": "enumerate",
                            "actor": "arn:aws:iam::123456789012:user/analyst",
                            "target": None,
                        },
                        "observation": {"success": True, "details": {"discovered_roles": ["arn:aws:iam::123456789012:role/TargetRole"]}},
                    }
                ],
            }
        )
    )
    (campaign_dir / "report.md").write_text("# report\n")

    result = AssessmentResult(
        bundle="aws-foundation",
        target="lab",
        campaigns=[
            CampaignResult(
                status="passed",
                profile="aws-iam-role-chaining",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "scope.json",
                objective_met=True,
                preflight_ok=True,
                report_json=campaign_dir / "report.json",
                report_md=campaign_dir / "report.md",
            )
        ],
    )

    write_assessment_summary(result, tmp_path)

    findings = json.loads((tmp_path / "assessment_findings.json").read_text())
    finding = findings["findings"][0]
    assert finding["status"] == "observed"
    assert finding["evidence_level"] == "observed"
    assert finding["profile"] == "aws-iam-role-chaining"
    assert finding["finding_state"] == "observed"
    assert "minimum proof" in finding["evidence_summary"]


def test_role_chaining_objective_not_met_still_surfaces_observed_finding(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    (campaign_dir / "report.json").write_text(
        json.dumps(
            {
                "objective": {"target": "arn:aws:iam::123456789012:role/TargetRole"},
                "executive_summary": {
                    "initial_identity": "arn:aws:iam::123456789012:user/analyst",
                    "final_resource": "arn:aws:iam::123456789012:role/TargetRole",
                    "proof": None,
                },
                "execution_policy": {"allowed_services": ["iam"]},
                "mitre_techniques": [],
                "steps": [
                    {
                        "action": {
                            "action_type": "assume_role",
                            "actor": "arn:aws:iam::123456789012:user/analyst",
                            "target": "arn:aws:iam::123456789012:role/TargetRole",
                            "tool": "iam_simulate_assume_role",
                        },
                        "observation": {
                            "success": True,
                            "details": {
                                "granted_role": "arn:aws:iam::123456789012:role/TargetRole",
                                "request_summary": {"api_calls": ["iam:SimulatePrincipalPolicy"]},
                                "simulated_policy_result": {"action": "sts:AssumeRole", "decision": "allowed"},
                            },
                        },
                    }
                ],
            }
        )
    )
    (campaign_dir / "report.md").write_text("# report\n")

    result = AssessmentResult(
        bundle="aws-foundation",
        target="lab",
        campaigns=[
            CampaignResult(
                status="objective_not_met",
                profile="aws-iam-role-chaining",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "scope.json",
                objective_met=False,
                preflight_ok=True,
                report_json=campaign_dir / "report.json",
                report_md=campaign_dir / "report.md",
            )
        ],
    )

    write_assessment_summary(result, tmp_path)

    findings = json.loads((tmp_path / "assessment_findings.json").read_text())
    assert findings["summary"]["findings_total"] == 1
    finding = findings["findings"][0]
    assert finding["profile"] == "aws-iam-role-chaining-simulated"
    assert finding["status"] == "observed"
    assert finding["finding_state"] == "reachable"


def test_distinct_path_key_collapses_repeated_identical_simulation_steps(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    report_json = campaign_dir / "report.json"
    report_json.write_text(
        json.dumps(
            {
                "objective": {"target": "arn:aws:iam::123456789012:role/AppRole"},
                "executive_summary": {
                    "initial_identity": "arn:aws:iam::123456789012:user/analyst",
                    "final_resource": "arn:aws:iam::123456789012:role/AppRole",
                    "simulated_policy_result": {
                        "action": "sts:AssumeRole",
                        "resource": "arn:aws:iam::123456789012:role/AppRole",
                        "decision": "allowed",
                    },
                    "proof": None,
                },
                "execution_policy": {"allowed_services": ["iam"]},
                "steps": [
                    {
                        "action": {
                            "action_type": "assume_role",
                            "actor": "arn:aws:iam::123456789012:user/analyst",
                            "target": "arn:aws:iam::123456789012:role/AppRole",
                            "tool": "iam_simulate_assume_role",
                        },
                        "observation": {
                            "success": True,
                            "details": {
                                "simulated_policy_result": {"decision": "allowed"},
                            },
                        },
                    },
                    {
                        "action": {
                            "action_type": "assume_role",
                            "actor": "arn:aws:iam::123456789012:user/analyst",
                            "target": "arn:aws:iam::123456789012:role/AppRole",
                            "tool": "iam_simulate_assume_role",
                        },
                        "observation": {
                            "success": True,
                            "details": {
                                "simulated_policy_result": {"decision": "allowed"},
                            },
                        },
                    },
                ],
            }
        )
    )
    (campaign_dir / "report.md").write_text("# report\n")
    result = AssessmentResult(
        bundle="aws-iam-role-chaining-only",
        target="lab",
        campaigns=[
            CampaignResult(
                status="objective_not_met",
                profile="aws-iam-role-chaining",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "scope.json",
                objective_met=False,
                preflight_ok=True,
                report_json=campaign_dir / "report.json",
                report_md=campaign_dir / "report.md",
            )
        ],
    )

    write_assessment_summary(result, tmp_path)

    findings = json.loads((tmp_path / "assessment_findings.json").read_text())
    finding = findings["findings"][0]
    assert finding["distinct_path_key"].count("iam_simulate_assume_role") == 1


def test_assessment_finding_state_validated_impact(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    report_json = campaign_dir / "report.json"
    report_json.write_text(
        json.dumps(
            {
                "objective": {"target": "arn:aws:s3:::bucket-a/payroll.csv"},
                "executive_summary": {
                    "initial_identity": "arn:aws:iam::123456789012:user/analyst",
                    "final_resource": "arn:aws:s3:::bucket-a/payroll.csv",
                    "proof": {"bucket": "bucket-a", "object_key": "payroll.csv"},
                },
                "execution_policy": {"allowed_services": ["s3"]},
                "steps": [
                    {
                        "action": {
                            "action_type": "access_resource",
                            "actor": "arn:aws:iam::123456789012:user/analyst",
                            "target": "arn:aws:s3:::bucket-a/payroll.csv",
                        },
                        "observation": {"success": True, "details": {"evidence": {"bucket": "bucket-a"}}},
                    }
                ],
            }
        )
    )
    (campaign_dir / "report.md").write_text("# report\n")
    result = AssessmentResult(
        bundle="aws-foundation",
        target="lab",
        campaigns=[
            CampaignResult(
                status="passed",
                campaign_id="plan-validated-impact",
                profile="aws-iam-s3",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "scope.json",
                objective_met=True,
                preflight_ok=True,
                report_json=report_json,
                report_md=campaign_dir / "report.md",
            )
        ],
    )
    write_assessment_summary(result, tmp_path)

    findings = json.loads((tmp_path / "assessment_findings.json").read_text())
    finding = findings["findings"][0]
    assert finding["finding_state"] == "validated_impact"


def test_policy_probe_findings_remain_observed(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    report_json = campaign_dir / "report.json"
    report_json.write_text(
        json.dumps(
            {
                "objective": {"target": "arn:aws:iam::123456789012:role/privesc-CreatePolicyVersion-role"},
                "executive_summary": {
                    "initial_identity": "arn:aws:iam::123456789012:user/analyst",
                    "final_resource": "arn:aws:iam::123456789012:role/privesc-CreatePolicyVersion-role",
                    "simulated_policy_result": {
                        "action": "iam:CreatePolicyVersion",
                        "resource": "arn:aws:iam::123456789012:role/privesc-CreatePolicyVersion-role",
                        "decision": "allowed",
                    },
                    "proof": None,
                },
                "execution_policy": {"allowed_services": ["iam"]},
                "steps": [
                    {
                        "action": {
                            "action_type": "access_resource",
                            "actor": "arn:aws:iam::123456789012:user/analyst",
                            "target": "arn:aws:iam::123456789012:role/privesc-CreatePolicyVersion-role",
                            "tool": "iam_create_policy_version",
                        },
                        "observation": {
                            "success": True,
                            "details": {
                                "request_summary": {"api_calls": ["iam:SimulatePrincipalPolicy"]},
                                "simulated_policy_result": {
                                    "action": "iam:CreatePolicyVersion",
                                    "decision": "allowed",
                                },
                            },
                        },
                    }
                ],
            }
        )
    )
    (campaign_dir / "report.md").write_text("# report\n")
    result = AssessmentResult(
        bundle="aws-iam-heavy",
        target="lab",
        campaigns=[
            CampaignResult(
                status="passed",
                campaign_id="plan-policy-probe",
                profile="aws-iam-create-policy-version-privesc",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "scope.json",
                objective_met=True,
                preflight_ok=True,
                report_json=report_json,
                report_md=campaign_dir / "report.md",
            )
        ],
    )

    write_assessment_summary(result, tmp_path)

    findings = json.loads((tmp_path / "assessment_findings.json").read_text())
    finding = findings["findings"][0]
    assert finding["status"] == "observed"
    assert finding["evidence_level"] == "observed"
    assert finding["finding_state"] == "reachable"
    assert "policy simulation" in finding["evidence_summary"].lower()


def test_role_chaining_simulation_finding_exposes_simulation_proof_mode(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    report_json = campaign_dir / "report.json"
    report_json.write_text(
        json.dumps(
            {
                "objective": {"target": "arn:aws:iam::123456789012:role/AppRole"},
                "executive_summary": {
                    "initial_identity": "arn:aws:iam::123456789012:user/analyst",
                    "final_resource": "arn:aws:iam::123456789012:role/AppRole",
                    "simulated_policy_result": {
                        "action": "sts:AssumeRole",
                        "resource": "arn:aws:iam::123456789012:role/AppRole",
                        "decision": "allowed",
                    },
                    "proof": None,
                },
                "execution_policy": {"allowed_services": ["iam"]},
                "steps": [
                    {
                        "action": {
                            "action_type": "assume_role",
                            "actor": "arn:aws:iam::123456789012:user/analyst",
                            "target": "arn:aws:iam::123456789012:role/AppRole",
                            "tool": "iam_simulate_assume_role",
                        },
                        "observation": {
                            "success": True,
                            "details": {
                                "request_summary": {"api_calls": ["iam:SimulatePrincipalPolicy"]},
                                "simulated_policy_result": {
                                    "action": "sts:AssumeRole",
                                    "decision": "allowed",
                                },
                            },
                        },
                    }
                ],
            }
        )
    )
    (campaign_dir / "report.md").write_text("# report\n")
    result = AssessmentResult(
        bundle="aws-iam-role-chaining-only",
        target="lab",
        campaigns=[
            CampaignResult(
                status="objective_not_met",
                profile="aws-iam-role-chaining",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "scope.json",
                objective_met=False,
                preflight_ok=True,
                report_json=campaign_dir / "report.json",
                report_md=campaign_dir / "report.md",
            )
        ],
    )

    write_assessment_summary(result, tmp_path)

    findings = json.loads((tmp_path / "assessment_findings.json").read_text())
    finding = findings["findings"][0]
    assert finding["profile"] == "aws-iam-role-chaining-simulated"
    assert finding["proof_mode"] == "simulation"
    assert finding["finding_state"] == "reachable"
    assert "simulation opportunity" in finding["title"].lower()
    assert findings["summary"]["proof_modes"]["simulation"] == 1


def test_role_chaining_implicit_deny_stays_observed_not_reachable(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    report_json = campaign_dir / "report.json"
    report_json.write_text(
        json.dumps(
            {
                "objective": {"target": "arn:aws:iam::123456789012:role/AppRole"},
                "executive_summary": {
                    "initial_identity": "arn:aws:iam::123456789012:user/analyst",
                    "final_resource": "arn:aws:iam::123456789012:role/AppRole",
                    "simulated_policy_result": {
                        "action": "sts:AssumeRole",
                        "resource": "arn:aws:iam::123456789012:role/AppRole",
                        "decision": "implicitDeny",
                    },
                    "proof": None,
                },
                "execution_policy": {"allowed_services": ["iam"]},
                "steps": [
                    {
                        "action": {
                            "action_type": "assume_role",
                            "actor": "arn:aws:iam::123456789012:user/analyst",
                            "target": "arn:aws:iam::123456789012:role/AppRole",
                            "tool": "iam_simulate_assume_role",
                        },
                        "observation": {
                            "success": True,
                            "details": {
                                "request_summary": {"api_calls": ["iam:SimulatePrincipalPolicy"]},
                                "simulated_policy_result": {
                                    "action": "sts:AssumeRole",
                                    "decision": "implicitDeny",
                                },
                            },
                        },
                    }
                ],
            }
        )
    )
    (campaign_dir / "report.md").write_text("# report\n")
    result = AssessmentResult(
        bundle="aws-iam-role-chaining-only",
        target="lab",
        campaigns=[
            CampaignResult(
                status="objective_not_met",
                profile="aws-iam-role-chaining",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "scope.json",
                objective_met=False,
                preflight_ok=True,
                report_json=campaign_dir / "report.json",
                report_md=campaign_dir / "report.md",
            )
        ],
    )

    write_assessment_summary(result, tmp_path)

    findings = json.loads((tmp_path / "assessment_findings.json").read_text())
    finding = findings["findings"][0]
    assert finding["profile"] == "aws-iam-role-chaining-simulated"
    assert finding["status"] == "observed"
    assert finding["finding_state"] == "observed"
    assert "did not prove" in finding["evidence_summary"].lower()


def test_simulated_s3_policy_result_without_evidence_stays_observed(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    report_json = campaign_dir / "report.json"
    report_json.write_text(
        json.dumps(
            {
                "objective": {"target": "arn:aws:s3:::bucket-a/payroll.csv"},
                "executive_summary": {
                    "initial_identity": "arn:aws:iam::123456789012:user/analyst",
                    "final_resource": "arn:aws:s3:::bucket-a/payroll.csv",
                    "simulated_policy_result": {
                        "action": "s3:GetObject",
                        "resource": "arn:aws:s3:::bucket-a/payroll.csv",
                        "decision": "implicitDeny",
                    },
                    "proof": None,
                },
                "execution_policy": {"allowed_services": ["s3"]},
                "steps": [
                    {
                        "action": {
                            "action_type": "access_resource",
                            "actor": "arn:aws:iam::123456789012:user/analyst",
                            "target": "arn:aws:s3:::bucket-a/payroll.csv",
                            "tool": "iam_simulate_target_access",
                        },
                        "observation": {
                            "success": True,
                            "details": {
                                "request_summary": {"api_calls": ["iam:SimulatePrincipalPolicy"]},
                                "simulated_policy_result": {
                                    "action": "s3:GetObject",
                                    "decision": "implicitDeny",
                                },
                            },
                        },
                    }
                ],
            }
        )
    )
    (campaign_dir / "report.md").write_text("# report\n")
    result = AssessmentResult(
        bundle="aws-iam-heavy",
        target="lab",
        campaigns=[
            CampaignResult(
                status="objective_not_met",
                campaign_id="plan-sim-s3",
                profile="aws-iam-s3",
                output_dir=campaign_dir,
                generated_scope=campaign_dir / "scope.json",
                objective_met=False,
                preflight_ok=True,
                report_json=report_json,
                report_md=campaign_dir / "report.md",
            )
        ],
    )

    write_assessment_summary(result, tmp_path)

    findings = json.loads((tmp_path / "assessment_findings.json").read_text())
    assert findings["summary"]["findings_total"] == 0

def test_run_campaign_marks_preflight_failure_without_crashing(tmp_path: Path) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)

    def fake_runner(**kwargs):
        raise ValueError("AWS preflight failed: account mismatch")

    campaign = run_campaign(
        profile_name="aws-iam-s3",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "campaign",
        runner=fake_runner,
    )

    assert campaign.status == "preflight_failed"
    assert campaign.objective_met is False
    assert campaign.report_md is None
    assert "preflight failed" in campaign.error.lower()


def test_run_assessment_preserves_failed_campaigns_and_continues(tmp_path: Path) -> None:
    target_path = Path(__file__).resolve().parents[1] / "examples" / "target_aws_foundation.local.json"
    authorization_path = (
        Path(__file__).resolve().parents[1] / "examples" / "authorization_aws_foundation.local.json"
    )
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs["fixture_path"].name)
        if "aws_role_choice_lab.local.json" in kwargs["fixture_path"].name:
            raise RuntimeError("AWS preflight failed: account mismatch")
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        report_json = output_dir / "report.json"
        report_md = output_dir / "report.md"
        graph = output_dir / "attack_graph.mmd"
        report_json.write_text("{}")
        report_md.write_text("# report\n")
        graph.write_text("graph TD\n")
        return {
            "objective_met": True,
            "preflight": {"ok": True, "details": {"account_id": "550192603632"}},
            "report_json": report_json,
            "report_md": report_md,
            "attack_graph": graph,
        }

    assessment = run_assessment(
        bundle_name="aws-foundation",
        target=target,
        authorization=authorization,
        output_dir=tmp_path / "assessment",
        runner=fake_runner,
    )

    assert len(assessment.campaigns) == 4
    assert assessment.campaigns[0].status == "preflight_failed"
    assert sum(1 for campaign in assessment.campaigns if campaign.status == "passed") == 3
    assert assessment.summary["campaigns_preflight_failed"] == 1
    assert assessment.summary["assessment_ok"] is False


def test_preflight_accepts_allowed_account_and_roles() -> None:
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[ActionType.ENUMERATE, ActionType.ASSUME_ROLE],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:iam::123456789012:role/AuditRole",
        ],
        max_steps=5,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )

    result = run_preflight(scope, client=FakeAwsClient())

    assert result.ok is True
    assert result.details["account_id"] == "123456789012"


def test_preflight_rejects_missing_role() -> None:
    scope = Scope.model_construct(
        target="aws",
        allowed_actions=[ActionType.ENUMERATE, ActionType.ASSUME_ROLE],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:iam::123456789012:role/DoesNotExistRole",
        ],
        max_steps=5,
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
        planner=None,
    )

    result = run_preflight(scope, client=FakeAwsClient())

    assert result.ok is False
    assert result.details["reason"] == "required_roles_missing"


def test_report_includes_preflight_block(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "aws_dry_run_lab.json"
    objective_path = repo_root / "examples" / "objective_aws_dry_run.json"
    scope_path = repo_root / "examples" / "scope_aws_dry_run.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=5,
        seed=1,
    )

    report = (tmp_path / "report.json").read_text()
    report_md = (tmp_path / "report.md").read_text()

    assert '"preflight"' in report
    assert '"mode": "skipped"' in report
    assert "## Preflight" in report_md

def test_scope_enforcer_blocks_out_of_scope() -> None:
    scope = Scope(
        allowed_actions=[ActionType.ENUMERATE],
        allowed_resources=["account"],
        max_steps=5,
    )
    enforcer = ScopeEnforcer(scope)
    action = Action(
        action_type=ActionType.ASSUME_ROLE,
        actor="analyst",
        target="AuditRole",
        parameters={},
    )
    assert enforcer.validate(action) is False


def test_fixture_transition() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "iam_lab.json"
    fixture = Fixture.load(fixture_path)
    action = Action(
        action_type=ActionType.ASSUME_ROLE,
        actor="analyst",
        target="AuditRole",
        parameters={},
    )
    observation = fixture.execute(action)
    assert observation.success is True
    assert fixture.state_copy()["identities"]["AuditRole"]["available_actions"]


def test_role_choice_fixture_retains_recovery_actions_after_wrong_role() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "aws_role_choice_lab.json"
    fixture = Fixture.load(fixture_path)
    action = Action(
        action_type=ActionType.ASSUME_ROLE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:iam::123456789012:role/BucketReaderRole",
        parameters={},
    )
    observation = fixture.execute(action)
    assert observation.success is True

    analyst_actions = fixture.state_copy()["identities"]["arn:aws:iam::123456789012:user/analyst"][
        "available_actions"
    ]
    targets = [item.get("target") for item in analyst_actions]
    assert "arn:aws:iam::123456789012:role/AuditRole" in targets
    assert "arn:aws:iam::123456789012:role/BucketReaderRole" in targets


def test_write_sanitized_artifacts_redacts_real_aws_outputs(tmp_path: Path) -> None:
    report_json = {
        "steps": [
            {
                "observation": {
                    "success": True,
                    "details": {
                        "real_api_called": True,
                        "aws_identity": {
                            "account_id": "550192603632",
                            "arn": "arn:aws:iam::550192603632:user/brainctl-user",
                        },
                        "evidence": {
                            "bucket": "sensitive-finance-data",
                            "object_key": "payroll.csv",
                            "accessed_via": "arn:aws:iam::550192603632:role/AuditRole",
                        },
                        "candidate_roles": [
                            "arn:aws:iam::550192603632:role/AuditRole",
                            "arn:aws:iam::550192603632:role/BucketReaderRole",
                        ],
                        "response_summary": {
                            "preview": "employee_id,name,salary",
                        },
                    },
                }
            }
        ]
    }
    markdown = (
        "identity arn:aws:iam::550192603632:user/brainctl-user "
        "roles AuditRole BucketReaderRole "
        "bucket s3://sensitive-finance-data/payroll.csv"
    )
    audit_path = tmp_path / "audit.jsonl"
    audit_path.write_text(
        '{"payload":{"real_api_called":true,"identity":"arn:aws:iam::550192603632:user/brainctl-user",'
        '"selected":"arn:aws:iam::550192603632:role/AuditRole",'
        '"rejected":"arn:aws:iam::550192603632:role/BucketReaderRole",'
        '"bucket":"sensitive-finance-data","preview":"employee_id,name,salary"}}\n'
    )

    write_sanitized_artifacts(tmp_path, report_json, markdown, audit_path)

    sanitized_report = (tmp_path / "report.sanitized.json").read_text()
    sanitized_md = (tmp_path / "report.sanitized.md").read_text()
    sanitized_audit = (tmp_path / "audit.sanitized.jsonl").read_text()

    assert "550192603632" not in sanitized_report
    assert "brainctl-user" not in sanitized_report
    assert "sensitive-finance-data" not in sanitized_report
    assert "payroll.csv" not in sanitized_report
    assert "employee_id,name,salary" not in sanitized_report
    assert "<AWS_ACCOUNT_ID>" in sanitized_report
    assert "<REDACTED_BUCKET>" in sanitized_report
    assert "<REDACTED_OBJECT_KEY>" in sanitized_report
    assert "<REDACTED_USER>" in sanitized_md
    assert "brainctl-user" not in sanitized_md
    assert "AuditRole" not in sanitized_md
    assert "BucketReaderRole" not in sanitized_md
    assert "sensitive-finance-data" not in sanitized_md
    assert "payroll.csv" not in sanitized_md
    assert "<REDACTED_ROLE>" in sanitized_report
    assert "<REDACTED_ROLE>_2" in sanitized_report
    assert "<REDACTED_CONTENT_PREVIEW>" in sanitized_audit

def test_end_to_end_run(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "iam_lab.json"
    objective_path = repo_root / "examples" / "objective.json"
    scope_path = repo_root / "examples" / "scope.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=5,
        seed=1,
    )

    report_json = tmp_path / "report.json"
    report_md = tmp_path / "report.md"
    audit_log = tmp_path / "audit.jsonl"

    assert report_json.exists()
    assert report_md.exists()
    assert audit_log.exists()

    report = report_json.read_text()
    assert '"objective_met": true' in report
    assert '"mitre_techniques"' in report


def test_openai_parser_accepts_action_index() -> None:
    actions = [
        Action(
            action_type=ActionType.ENUMERATE,
            actor="analyst",
            target="account",
            parameters={},
        ),
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="analyst",
            target="AuditRole",
            parameters={},
        ),
    ]

    decision = parse_openai_response(
        '{"action_index": 1, "reason": "Use the role path."}',
        actions,
    )

    assert decision.action.action_type == ActionType.ASSUME_ROLE
    assert decision.action.target == "AuditRole"
    assert decision.reason == "Use the role path."


def test_mock_planner_emits_backend_metadata() -> None:
    planner = DeterministicPlanner(seed=1)
    actions = [
        Action(
            action_type=ActionType.ENUMERATE,
            actor="analyst",
            target="account",
            parameters={},
        )
    ]

    decision = planner.decide(snapshot=None, available_actions=actions)

    assert decision.planner_metadata["planner_backend"] == "mock"


def test_ollama_parser_falls_back_on_invalid_selection() -> None:
    planner = OllamaPlanner.__new__(OllamaPlanner)
    actions = [
        Action(
            action_type=ActionType.ENUMERATE,
            actor="analyst",
            target="account",
            parameters={},
        ),
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="analyst",
            target="AuditRole",
            parameters={},
        ),
    ]

    decision = planner._parse_response(
        '{"action_type": "assume_role", "actor": "analyst", "target": null, "reason": "bad target"}',
        actions,
    )

    assert decision.action.action_type == ActionType.ENUMERATE
    assert "Fallback para enumerate" in decision.reason


def test_state_tracks_tested_and_failed_assume_roles() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "aws_role_choice_lab.json"
    fixture = Fixture.load(fixture_path)
    objective = Objective(
        description="test objective",
        target="arn:aws:s3:::sensitive-finance-data/payroll.csv",
        success_criteria={"flag": "priv_esc"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=[
            ActionType.ENUMERATE,
            ActionType.ANALYZE,
            ActionType.ASSUME_ROLE,
            ActionType.ACCESS_RESOURCE,
        ],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:iam::123456789012:role/AuditRole",
            "arn:aws:iam::123456789012:role/BucketReaderRole",
            "arn:aws:s3:::sensitive-finance-data",
            "arn:aws:s3:::sensitive-finance-data/payroll.csv",
            "arn:aws:s3:::public-reports",
        ],
        max_steps=6,
        dry_run=True,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "sts", "s3"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
    )
    state = StateManager(objective=objective, scope=scope, fixture=fixture)

    wrong_assume = Action(
        action_type=ActionType.ASSUME_ROLE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:iam::123456789012:role/BucketReaderRole",
        parameters={},
    )
    wrong_observation = fixture.execute(wrong_assume)
    state.apply_observation(wrong_assume, wrong_observation, "picked wrong role")

    decoy_enum = Action(
        action_type=ActionType.ENUMERATE,
        actor="arn:aws:iam::123456789012:role/BucketReaderRole",
        target="arn:aws:s3:::public-reports",
        parameters={},
    )
    decoy_observation = fixture.execute(decoy_enum)
    state.apply_observation(decoy_enum, decoy_observation, "enumerated decoy bucket")

    snapshot = state.snapshot()
    assert "arn:aws:iam::123456789012:role/BucketReaderRole" in snapshot.tested_assume_roles
    assert "arn:aws:iam::123456789012:role/BucketReaderRole" in snapshot.failed_assume_roles


def test_state_tracks_active_assumed_roles_with_progress_actions() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "aws_role_choice_lab.json"
    fixture = Fixture.load(fixture_path)
    objective = Objective(
        description="test objective",
        target="arn:aws:s3:::sensitive-finance-data/payroll.csv",
        success_criteria={"flag": "priv_esc"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=[
            ActionType.ENUMERATE,
            ActionType.ANALYZE,
            ActionType.ASSUME_ROLE,
            ActionType.ACCESS_RESOURCE,
        ],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:iam::123456789012:role/AuditRole",
            "arn:aws:iam::123456789012:role/BucketReaderRole",
            "arn:aws:s3:::sensitive-finance-data",
            "arn:aws:s3:::sensitive-finance-data/payroll.csv",
            "arn:aws:s3:::public-reports",
        ],
        max_steps=6,
        dry_run=True,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "sts", "s3"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
    )
    state = StateManager(objective=objective, scope=scope, fixture=fixture)

    assume = Action(
        action_type=ActionType.ASSUME_ROLE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:iam::123456789012:role/AuditRole",
        parameters={},
    )
    observation = fixture.execute(assume)
    state.apply_observation(assume, observation, "picked right role")

    snapshot = state.snapshot()
    assert "arn:aws:iam::123456789012:role/AuditRole" in snapshot.active_assumed_roles
    assert snapshot.active_branch_action_count > 0


def test_state_exposes_candidate_paths_with_failed_status() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "aws_role_choice_lab.json"
    fixture = Fixture.load(fixture_path)
    objective = Objective(
        description="test objective",
        target="arn:aws:s3:::sensitive-finance-data/payroll.csv",
        success_criteria={"flag": "priv_esc"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=[
            ActionType.ENUMERATE,
            ActionType.ANALYZE,
            ActionType.ASSUME_ROLE,
            ActionType.ACCESS_RESOURCE,
        ],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:iam::123456789012:role/AuditRole",
            "arn:aws:iam::123456789012:role/BucketReaderRole",
            "arn:aws:s3:::sensitive-finance-data",
            "arn:aws:s3:::sensitive-finance-data/payroll.csv",
            "arn:aws:s3:::public-reports",
        ],
        max_steps=6,
        dry_run=True,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "sts", "s3"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
    )
    state = StateManager(objective=objective, scope=scope, fixture=fixture)

    wrong_assume = Action(
        action_type=ActionType.ASSUME_ROLE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:iam::123456789012:role/BucketReaderRole",
        parameters={},
    )
    wrong_observation = fixture.execute(wrong_assume)
    state.apply_observation(wrong_assume, wrong_observation, "picked wrong role")

    decoy_enum = Action(
        action_type=ActionType.ENUMERATE,
        actor="arn:aws:iam::123456789012:role/BucketReaderRole",
        target="arn:aws:s3:::public-reports",
        parameters={},
    )
    decoy_observation = fixture.execute(decoy_enum)
    state.apply_observation(decoy_enum, decoy_observation, "enumerated decoy bucket")

    snapshot = state.snapshot()
    candidate_paths = {path.target: path for path in snapshot.candidate_paths}

    assert candidate_paths["arn:aws:iam::123456789012:role/BucketReaderRole"].status == "failed"
    assert candidate_paths["arn:aws:iam::123456789012:role/BucketReaderRole"].times_tested == 1
    assert candidate_paths["arn:aws:iam::123456789012:role/AuditRole"].status == "untested"


def test_snapshot_exposes_guidance_for_commit_to_pivot() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "aws_role_choice_lab.json"
    fixture = Fixture.load(fixture_path)
    objective = Objective(
        description="test objective",
        target="arn:aws:s3:::sensitive-finance-data/payroll.csv",
        success_criteria={"flag": "priv_esc"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=[
            ActionType.ENUMERATE,
            ActionType.ANALYZE,
            ActionType.ASSUME_ROLE,
            ActionType.ACCESS_RESOURCE,
        ],
        allowed_resources=[
            "arn:aws:iam::123456789012:root",
            "arn:aws:iam::123456789012:role/AuditRole",
            "arn:aws:iam::123456789012:role/BucketReaderRole",
            "arn:aws:s3:::sensitive-finance-data",
            "arn:aws:s3:::sensitive-finance-data/payroll.csv",
            "arn:aws:s3:::public-reports",
        ],
        max_steps=6,
        dry_run=True,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "sts", "s3"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
    )
    state = StateManager(objective=objective, scope=scope, fixture=fixture)
    state._steps_taken = 1

    snapshot = state.snapshot()

    assert snapshot.enumeration_sufficient is True
    assert snapshot.should_commit_to_pivot is True
    assert "arn:aws:iam::123456789012:role/AuditRole" in snapshot.candidate_roles
    assert "arn:aws:iam::123456789012:role/BucketReaderRole" in snapshot.candidate_roles


def test_blind_runtime_omits_target_access_probe_for_role_chaining_profile() -> None:
    scope = Scope(
        target="aws",
        allowed_actions=["enumerate", "assume_role", "access_resource"],
        allowed_resources=["arn:aws:iam::123456789012:role/AppRole"],
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="tester",
        authorized_at="2026-04-04",
        authorization_document="doc",
    )
    runtime = BlindRealRuntime.build(
        plan={"resource_arn": "arn:aws:iam::123456789012:role/AppRole", "profile": "aws-iam-role-chaining"},
        discovery_snapshot={
            "caller_identity": {"Account": "123456789012"},
            "resources": [
                {"resource_type": "identity.role", "identifier": "arn:aws:iam::123456789012:role/AppRole"},
            ],
        },
        scope=scope,
        entry_identities=["arn:aws:iam::123456789012:user/analyst"],
    )

    actions = runtime.enumerate_actions(snapshot=None)

    assert any(action.tool == "iam_simulate_assume_role" for action in actions)
    assert all(action.tool != "iam_simulate_target_access" for action in actions)


def test_state_derives_candidate_roles_from_blind_runtime_discovered_roles() -> None:
    class RuntimeLikeFixture:
        def state_copy(self):
            return {
                "flags": [],
                "identities": {
                    "arn:aws:iam::123456789012:user/analyst": {"active": True},
                },
                "discovered_roles": [
                    "arn:aws:iam::123456789012:role/AppRole",
                    "arn:aws:iam::123456789012:role/AuditRole",
                ],
            }

        def has_flag(self, flag: str) -> bool:
            return False

        def canonicalize(self, value):
            return value

    objective = Objective(
        description="assume target role",
        target="arn:aws:iam::123456789012:role/AppRole",
        success_criteria={"mode": "assume_role_proved"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=["enumerate", "assume_role", "analyze"],
        allowed_resources=["arn:aws:iam::123456789012:role/AppRole"],
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="tester",
        authorized_at="2026-04-04",
        authorization_document="doc",
    )
    state = StateManager(objective=objective, scope=scope, fixture=RuntimeLikeFixture())
    state._steps_taken = 1
    state._activated_identities = ["arn:aws:iam::123456789012:user/analyst"]

    snapshot = state.snapshot()

    assert snapshot.enumeration_sufficient is True
    assert snapshot.should_commit_to_pivot is True
    assert "arn:aws:iam::123456789012:role/AppRole" in snapshot.candidate_roles
    assert "arn:aws:iam::123456789012:user/analyst" in snapshot.active_branch_identities


def test_ollama_prompt_includes_path_memory() -> None:
    planner = OllamaPlanner.__new__(OllamaPlanner)
    actions = [
        Action(
            action_type=ActionType.ENUMERATE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:root",
            parameters={},
        ),
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/AuditRole",
            parameters={},
        )
    ]
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "aws_role_choice_lab.json"
    fixture = Fixture.load(fixture_path)
    objective = Objective(
        description="test objective",
        target="arn:aws:s3:::sensitive-finance-data/payroll.csv",
        success_criteria={"flag": "priv_esc"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=[ActionType.ENUMERATE],
        allowed_resources=["arn:aws:iam::123456789012:root"],
        max_steps=5,
        dry_run=True,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
    )
    state = StateManager(objective=objective, scope=scope, fixture=fixture)
    state._tested_assume_roles = ["arn:aws:iam::123456789012:role/BucketReaderRole"]
    state._failed_assume_roles = ["arn:aws:iam::123456789012:role/BucketReaderRole"]
    state._steps_taken = 1
    state._tested_assume_roles.append("arn:aws:iam::123456789012:role/AuditRole")

    prompt = planner._build_prompt(state.snapshot(), actions)

    assert '"path_memory"' in prompt
    assert '"tested_assume_roles"' in prompt
    assert '"failed_assume_roles"' in prompt
    assert 'BucketReaderRole' in prompt
    assert '"planner_guidance"' in prompt
    assert '"enumeration_sufficient": true' in prompt
    assert '"should_commit_to_pivot": true' in prompt
    assert '"should_explore_current_branch"' in prompt


def test_shape_available_actions_prefers_active_branch_progress() -> None:
    actions = [
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/BucketReaderRole",
            parameters={},
        ),
        Action(
            action_type=ActionType.ENUMERATE,
            actor="arn:aws:iam::123456789012:role/AuditRole",
            target="arn:aws:s3:::sensitive-finance-data",
            parameters={},
        ),
        Action(
            action_type=ActionType.ACCESS_RESOURCE,
            actor="arn:aws:iam::123456789012:role/AuditRole",
            target="arn:aws:s3:::sensitive-finance-data/payroll.csv",
            parameters={},
        ),
    ]

    class Snapshot:
        active_assumed_roles = ["arn:aws:iam::123456789012:role/AuditRole"]

    shaped = shape_available_actions(Snapshot(), actions)

    assert [action.action_type for action in shaped] == [
        ActionType.ENUMERATE,
        ActionType.ACCESS_RESOURCE,
    ]
    assert all(
        action.actor == "arn:aws:iam::123456789012:role/AuditRole"
        for action in shaped
    )


def test_shape_available_actions_backtracks_to_untested_candidate_role() -> None:
    actions = [
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/BucketReaderRole",
            parameters={},
        ),
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/AuditRole",
            parameters={},
        ),
        Action(
            action_type=ActionType.ENUMERATE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:root",
            parameters={},
        ),
    ]

    class CandidatePath:
        def __init__(self, target: str, status: str) -> None:
            self.target = target
            self.status = status

    class Snapshot:
        active_assumed_roles = []
        candidate_paths = [
            CandidatePath("arn:aws:iam::123456789012:role/BucketReaderRole", "failed"),
            CandidatePath("arn:aws:iam::123456789012:role/AuditRole", "untested"),
        ]

    shaped = shape_available_actions(Snapshot(), actions)

    assert len(shaped) == 1
    assert shaped[0].action_type == ActionType.ASSUME_ROLE
    assert shaped[0].target == "arn:aws:iam::123456789012:role/AuditRole"


def test_mock_planner_avoids_failed_assume_role() -> None:
    planner = DeterministicPlanner(seed=1)
    actions = [
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/BucketReaderRole",
            parameters={},
        ),
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/AuditRole",
            parameters={},
        ),
    ]

    class Snapshot:
        observations = []
        failed_assume_roles = ["arn:aws:iam::123456789012:role/BucketReaderRole"]

    decision = planner.decide(Snapshot(), actions)

    assert decision.action.target == "arn:aws:iam::123456789012:role/AuditRole"


def test_mock_planner_prefers_untested_candidate_path() -> None:
    planner = DeterministicPlanner(seed=1)
    actions = [
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/BucketReaderRole",
            parameters={},
        ),
        Action(
            action_type=ActionType.ASSUME_ROLE,
            actor="arn:aws:iam::123456789012:user/analyst",
            target="arn:aws:iam::123456789012:role/AuditRole",
            parameters={},
        ),
    ]

    class CandidatePath:
        def __init__(self, target: str, status: str) -> None:
            self.target = target
            self.status = status

    class Snapshot:
        observations = []
        failed_assume_roles = []
        candidate_paths = [
            CandidatePath("arn:aws:iam::123456789012:role/BucketReaderRole", "tested"),
            CandidatePath("arn:aws:iam::123456789012:role/AuditRole", "untested"),
        ]

    decision = planner.decide(Snapshot(), actions)

    assert decision.action.target == "arn:aws:iam::123456789012:role/AuditRole"


def test_report_marks_fallback_steps(tmp_path: Path) -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "iam_lab.json"
    fixture = Fixture.load(fixture_path)
    objective = Objective(
        description="test objective",
        target="sensitive_bucket",
        success_criteria={"flag": "priv_esc"},
    )
    scope = Scope(
        allowed_actions=[
            ActionType.ENUMERATE,
            ActionType.ANALYZE,
            ActionType.ASSUME_ROLE,
            ActionType.ACCESS_RESOURCE,
        ],
        allowed_resources=["account", "AuditRole", "sensitive_bucket"],
        max_steps=5,
    )
    state = StateManager(objective=objective, scope=scope, fixture=fixture)
    action = Action(
        action_type=ActionType.ENUMERATE,
        actor="analyst",
        target="account",
        parameters={},
    )
    state.apply_observation(
        action,
        Observation(success=True, details={"details": "Roles enumerated."}),
        "LLM escolheu ação indisponível (assume_role/analyst/None). Fallback para enumerate.",
        {"planner_backend": "ollama", "raw_response": '{"action_index": 99}'},
    )

    report = ReportGenerator(tmp_path).generate(
        state.snapshot(),
        AttackGraph(),
        AuditLogger(tmp_path / "audit.jsonl"),
        state.initial_state(),
        objective_met=False,
    )

    assert report["json"]["steps"][0]["fallback_used"] is True
    assert report["json"]["steps"][0]["planner_backend"] == "ollama"




def test_aws_dry_run_lab_filters_disallowed_services() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "aws_dry_run_lab.json"
    fixture = Fixture.load(fixture_path)
    scope = Scope.model_validate_json((Path(__file__).resolve().parents[1] / "examples" / "scope_aws_dry_run.json").read_text())
    scope.allowed_services = ["iam"]
    lab = AwsDryRunLab.from_fixture(fixture, scope)

    actions = lab.enumerate_actions(snapshot=None)

    assert actions
    assert all(action.parameters.get("service") == "iam" for action in actions)
    denied = Action(
        action_type=ActionType.ACCESS_RESOURCE,
        actor="arn:aws:iam::123456789012:role/AuditRole",
        target="arn:aws:s3:::sensitive-finance-data/payroll.csv",
        parameters={"service": "s3"},
    )
    observation = lab.execute(denied)
    assert observation.success is False
    assert observation.details["reason"] == "service_not_allowed"


def test_report_includes_blind_real_execution_context(tmp_path: Path) -> None:
    objective = Objective(
        description="read target object",
        target="arn:aws:s3:::bucket-a/payroll.csv",
        success_criteria={"mode": "target_observed"},
    )
    scope = Scope(
        target="aws",
        allowed_actions=["enumerate", "assume_role", "access_resource"],
        allowed_resources=["arn:aws:s3:::bucket-a/payroll.csv"],
        dry_run=False,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam", "s3"],
        authorized_by="tester",
        authorized_at="2026-04-04",
        authorization_document="doc",
    )
    fixture = Fixture.load(Path(__file__).resolve().parents[1] / "fixtures" / "mixed_generalization_iam_s3_lab.json")
    state = StateManager(objective=objective, scope=scope, fixture=fixture)

    report = ReportGenerator(tmp_path).generate(
        state.snapshot(),
        AttackGraph(),
        AuditLogger(tmp_path / "audit.jsonl"),
        state.initial_state(),
        objective_met=False,
        execution_context={
            "runtime_mode": "blind_real",
            "synthetic_fixture_used": False,
        },
    )

    summary = report["json"]["executive_summary"]
    assert summary["runtime_mode"] == "blind_real"
    assert summary["synthetic_fixture_used"] is False


def test_aws_dry_run_lab_filters_disallowed_regions_and_accounts() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture = Fixture.load(repo_root / "fixtures" / "aws_dry_run_lab.json")
    scope = Scope.model_validate_json((repo_root / "examples" / "scope_aws_dry_run.json").read_text())

    region_scope = scope.model_copy(deep=True)
    region_scope.allowed_regions = ["eu-west-1"]
    region_lab = AwsDryRunLab.from_fixture(fixture, region_scope)
    assert region_lab.enumerate_actions(snapshot=None) == []
    denied_region = Action(
        action_type=ActionType.ENUMERATE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:iam::123456789012:root",
        parameters={"service": "iam", "region": "us-east-1"},
    )
    observation = region_lab.execute(denied_region)
    assert observation.success is False
    assert observation.details["reason"] == "region_not_allowed"

    account_scope = scope.model_copy(deep=True)
    account_scope.aws_account_ids = ["999999999999"]
    account_lab = AwsDryRunLab.from_fixture(fixture, account_scope)
    assert account_lab.enumerate_actions(snapshot=None) == []
    denied_account = Action(
        action_type=ActionType.ENUMERATE,
        actor="arn:aws:iam::123456789012:user/analyst",
        target="arn:aws:iam::123456789012:root",
        parameters={"service": "iam", "region": "us-east-1"},
    )
    observation = account_lab.execute(denied_account)
    assert observation.success is False
    assert observation.details["reason"] == "account_not_allowed"


def test_aws_dry_run_lab_filters_disallowed_resources() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture = Fixture.load(repo_root / "fixtures" / "aws_dry_run_lab.json")
    scope = Scope.model_validate_json((repo_root / "examples" / "scope_aws_dry_run.json").read_text())
    scope.allowed_resources = ["arn:aws:iam::123456789012:root"]
    lab = AwsDryRunLab.from_fixture(fixture, scope)

    actions = lab.enumerate_actions(snapshot=None)

    assert actions
    assert all(action.target == "arn:aws:iam::123456789012:root" for action in actions)

    denied = Action(
        action_type=ActionType.ACCESS_RESOURCE,
        actor="arn:aws:iam::123456789012:role/AuditRole",
        target="arn:aws:s3:::sensitive-finance-data/payroll.csv",
        parameters={"service": "s3", "region": "us-east-1"},
    )
    observation = lab.execute(denied)
    assert observation.success is False
    assert observation.details["reason"] == "resource_not_allowed"

def test_aws_scope_allows_dry_run_false_with_authorization() -> None:
    scope = Scope(
        target="aws",
        allowed_actions=[ActionType.ENUMERATE],
        allowed_resources=["arn:aws:iam::123456789012:root"],
        dry_run=False,
        max_steps=5,
        aws_account_ids=["123456789012"],
        allowed_regions=["us-east-1"],
        allowed_services=["iam"],
        authorized_by="Demo Operator",
        authorized_at="2026-03-28",
        authorization_document="docs/authorization-demo.md",
    )
    assert scope.dry_run is False

def test_aws_scope_requires_authorization_fields() -> None:
    with pytest.raises(ValueError):
        Scope(
            target="aws",
            allowed_actions=[ActionType.ENUMERATE],
            allowed_resources=["account"],
            dry_run=True,
            max_steps=5,
        )



def test_run_rejects_scope_fixture_mismatch(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "iam_lab.json"
    objective_path = repo_root / "examples" / "objective.json"
    scope_path = repo_root / "examples" / "scope_aws_dry_run.json"

    with pytest.raises(Exception, match="AWS scope is incompatible"):
        run(
            fixture_path=fixture_path,
            objective_path=objective_path,
            scope_path=scope_path,
            output_dir=tmp_path,
            max_steps=5,
            seed=1,
        )


def test_run_rejects_real_aws_when_capability_disabled(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "aws_dry_run_lab.json"
    objective_path = repo_root / "examples" / "objective_aws_dry_run.json"
    real_scope = tmp_path / "scope_real.json"
    real_scope.write_text(
        (
            repo_root / "examples" / "scope_aws_dry_run.json"
        ).read_text().replace('"dry_run": true', '"dry_run": false')
    )

    with pytest.raises(Exception, match="AWS real execution is disabled"):
        run(
            fixture_path=fixture_path,
            objective_path=objective_path,
            scope_path=real_scope,
            output_dir=tmp_path,
            max_steps=5,
            seed=1,
        )


def test_aws_dry_run_report_and_audit_include_execution_policy(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "aws_dry_run_lab.json"
    objective_path = repo_root / "examples" / "objective_aws_dry_run.json"
    scope_path = repo_root / "examples" / "scope_aws_dry_run.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=5,
        seed=1,
    )

    report = (tmp_path / "report.json").read_text()
    audit_log = (tmp_path / "audit.jsonl").read_text()

    assert '"execution_policy"' in report
    assert '"dry_run_applied": true' in report
    assert '"allowed_services": [' in report
    assert '"execution_policy"' in audit_log
    assert '"authorization_document": "docs/authorization-demo.md"' in audit_log

def test_aws_dry_run_end_to_end(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "aws_dry_run_lab.json"
    objective_path = repo_root / "examples" / "objective_aws_dry_run.json"
    scope_path = repo_root / "examples" / "scope_aws_dry_run.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=5,
        seed=1,
    )

    report = (tmp_path / "report.json").read_text()
    assert '"execution_mode": "dry_run"' in report
    assert '"real_api_called": false' in report
    assert 'arn:aws:s3:::sensitive-finance-data/payroll.csv' in report


def test_aws_s3_discovery_dry_run_end_to_end(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "aws_s3_discovery_lab.json"
    objective_path = repo_root / "examples" / "objective_aws_s3_discovery.json"
    scope_path = repo_root / "examples" / "scope_aws_s3_discovery.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=6,
        seed=1,
    )

    report = (tmp_path / "report.json").read_text()
    assert '"objective_met": true' in report
    assert '"tool": "s3_list_bucket"' in report
    assert '"discovered_objects"' in report
    assert '"mitre_id": "T1619"' in report
    assert '"evidence"' in report


def test_aws_role_choice_dry_run_end_to_end(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "aws_role_choice_lab.json"
    objective_path = repo_root / "examples" / "objective_aws_role_choice.json"
    scope_path = repo_root / "examples" / "scope_aws_role_choice.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=6,
        seed=1,
    )

    report = (tmp_path / "report.json").read_text()
    report_md = (tmp_path / "report.md").read_text()
    assert '"objective_met": true' in report
    assert '"target": "arn:aws:iam::123456789012:role/BucketReaderRole"' in report
    assert '"tool": "s3_list_bucket"' in report
    assert '"priv_esc"' in report
    assert '"arn:aws:s3:::sensitive-finance-data/payroll.csv"' in report
    assert '"rejected_roles": [' in report
    assert 'BucketReaderRole' in report_md
    assert (tmp_path / "attack_graph.html").exists()


def test_aws_backtracking_dry_run_end_to_end(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "aws_backtracking_lab.json"
    objective_path = repo_root / "examples" / "objective_aws_backtracking.json"
    scope_path = repo_root / "examples" / "scope_aws_backtracking.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=8,
        seed=1,
    )

    report = (tmp_path / "report.json").read_text()
    report_md = (tmp_path / "report.md").read_text()

    assert '"objective_met": true' in report
    assert '"arn:aws:iam::123456789012:role/A-FinanceAuditRole"' in report
    assert '"arn:aws:iam::123456789012:role/Z-DataOpsRole"' in report
    assert '"tool": "s3_read_sensitive"' in report
    assert 'A-FinanceAuditRole' in report_md
    assert 'Z-DataOpsRole' in report_md


def test_aws_backtracking_openai_scope_keeps_assume_role_actions_available() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture = Fixture.load(repo_root / "fixtures" / "aws_backtracking_lab.json")
    scope = Scope.model_validate_json(
        (repo_root / "examples" / "scope_aws_backtracking_openai.json").read_text()
    )
    lab = AwsDryRunLab.from_fixture(fixture, scope)

    actions = lab.enumerate_actions(snapshot=None)

    assert any(action.action_type == ActionType.ASSUME_ROLE for action in actions)
    assert any(
        action.target == "arn:aws:iam::123456789012:role/A-FinanceAuditRole"
        for action in actions
    )
    assert any(
        action.target == "arn:aws:iam::123456789012:role/Z-DataOpsRole"
        for action in actions
    )


def test_aws_multi_branch_backtracking_dry_run_end_to_end(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "aws_multi_branch_backtracking_lab.json"
    objective_path = repo_root / "examples" / "objective_aws_multi_branch_backtracking.json"
    scope_path = repo_root / "examples" / "scope_aws_multi_branch_backtracking.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=8,
        seed=1,
    )

    report = (tmp_path / "report.json").read_text()
    report_md = (tmp_path / "report.md").read_text()

    assert '"objective_met": true' in report
    assert '"arn:aws:iam::123456789012:role/RoleA"' in report
    assert '"arn:aws:iam::123456789012:role/RoleM"' in report
    assert '"arn:aws:iam::123456789012:role/RoleQ"' in report
    assert '"tool": "s3_read_sensitive"' in report
    assert 'RoleA' in report_md
    assert 'RoleM' in report_md
    assert 'RoleQ' in report_md


def test_action_shaping_orders_untested_candidate_paths_by_score_then_target() -> None:
    fixture = Fixture.load(
        Path(__file__).resolve().parents[1] / "fixtures" / "aws_permuted_branching_roleq_success_lab.json"
    )
    objective = Objective.model_validate_json(
        (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "objective_aws_permuted_branching.json"
        ).read_text()
    )
    scope = Scope.model_validate_json(
        (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "scope_aws_permuted_branching.json"
        ).read_text()
    )
    state = StateManager(objective=objective, scope=scope, fixture=AwsDryRunLab.from_fixture(fixture, scope))

    snapshot = state.snapshot()
    shaped = shape_available_actions(snapshot, AwsDryRunLab.from_fixture(fixture, scope).enumerate_actions(snapshot))

    assume_targets = [action.target for action in shaped if action.action_type == ActionType.ASSUME_ROLE]
    assert assume_targets == [
        "arn:aws:iam::123456789012:role/RoleQ",
        "arn:aws:iam::123456789012:role/RoleA",
        "arn:aws:iam::123456789012:role/RoleM",
    ]


def test_candidate_paths_expose_path_score() -> None:
    fixture = Fixture.load(
        Path(__file__).resolve().parents[1] / "fixtures" / "aws_multi_branch_backtracking_lab.json"
    )
    objective = Objective.model_validate_json(
        (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "objective_aws_multi_branch_backtracking.json"
        ).read_text()
    )
    scope = Scope.model_validate_json(
        (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "scope_aws_multi_branch_backtracking.json"
        ).read_text()
    )
    state = StateManager(objective=objective, scope=scope, fixture=AwsDryRunLab.from_fixture(fixture, scope))

    snapshot = state.snapshot()

    assert snapshot.candidate_paths
    assert all(hasattr(path, "path_score") for path in snapshot.candidate_paths)
    scores = {path.target: path.path_score for path in snapshot.candidate_paths}
    assert scores["arn:aws:iam::123456789012:role/RoleQ"] > scores[
        "arn:aws:iam::123456789012:role/RoleA"
    ]
    assert scores["arn:aws:iam::123456789012:role/RoleQ"] > scores[
        "arn:aws:iam::123456789012:role/RoleM"
    ]


def test_candidate_paths_gain_objective_relevance_score_from_observed_resources() -> None:
    fixture = Fixture.load(
        Path(__file__).resolve().parents[1] / "fixtures" / "aws_multi_branch_backtracking_lab.json"
    )
    objective = Objective.model_validate_json(
        (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "objective_aws_multi_branch_backtracking.json"
        ).read_text()
    )
    scope = Scope.model_validate_json(
        (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "scope_aws_multi_branch_backtracking.json"
        ).read_text()
    )
    lab = AwsDryRunLab.from_fixture(fixture, scope)
    state = StateManager(objective=objective, scope=scope, fixture=lab)

    enumerate_action = lab.enumerate_actions(state.snapshot())[0]
    enumerate_observation = lab.execute(enumerate_action)
    state.apply_observation(enumerate_action, enumerate_observation, "test")

    assume_role_q = next(
        action
        for action in lab.enumerate_actions(state.snapshot())
        if action.action_type == ActionType.ASSUME_ROLE
        and action.target == "arn:aws:iam::123456789012:role/RoleQ"
    )
    assume_observation = lab.execute(assume_role_q)
    state.apply_observation(assume_role_q, assume_observation, "test")

    list_action = next(
        action
        for action in lab.enumerate_actions(state.snapshot())
        if action.actor == "arn:aws:iam::123456789012:role/RoleQ"
        and action.action_type == ActionType.ENUMERATE
    )
    list_observation = lab.execute(list_action)
    state.apply_observation(list_action, list_observation, "test")

    snapshot = state.snapshot()
    role_q = next(path for path in snapshot.candidate_paths if path.target.endswith("/RoleQ"))
    role_a = next(path for path in snapshot.candidate_paths if path.target.endswith("/RoleA"))

    assert "payroll.csv" in role_q.observed_resources
    assert role_q.path_score > role_a.path_score


def test_candidate_paths_gain_lookahead_score_before_branch_is_tested() -> None:
    fixture = Fixture.load(
        Path(__file__).resolve().parents[1] / "fixtures" / "aws_permuted_branching_rolea_success_lab.json"
    )
    objective = Objective.model_validate_json(
        (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "objective_aws_permuted_branching.json"
        ).read_text()
    )
    scope = Scope.model_validate_json(
        (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "scope_aws_permuted_branching.json"
        ).read_text()
    )
    state = StateManager(objective=objective, scope=scope, fixture=AwsDryRunLab.from_fixture(fixture, scope))

    snapshot = state.snapshot()
    role_a = next(path for path in snapshot.candidate_paths if path.target.endswith("/RoleA"))
    role_m = next(path for path in snapshot.candidate_paths if path.target.endswith("/RoleM"))

    assert any("payroll.csv" in signal for signal in role_a.lookahead_signals)
    assert role_a.path_score > role_m.path_score


@pytest.mark.parametrize(
    ("fixture_name", "successful_role"),
    [
        ("aws_permuted_branching_rolea_success_lab.json", "RoleA"),
        ("aws_permuted_branching_rolem_success_lab.json", "RoleM"),
        ("aws_permuted_branching_roleq_success_lab.json", "RoleQ"),
    ],
)
def test_aws_permuted_branching_variants_dry_run_end_to_end(
    tmp_path: Path,
    fixture_name: str,
    successful_role: str,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / fixture_name
    objective_path = repo_root / "examples" / "objective_aws_permuted_branching.json"
    scope_path = repo_root / "examples" / "scope_aws_permuted_branching.json"
    output_dir = tmp_path / successful_role

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=output_dir,
        max_steps=8,
        seed=1,
    )

    report = (output_dir / "report.json").read_text()
    report_md = (output_dir / "report.md").read_text()

    assert '"objective_met": true' in report
    assert '"tool": "s3_read_sensitive"' in report
    assert f'"accessed_via": "arn:aws:iam::123456789012:role/{successful_role}"' in report
    assert successful_role in report_md


def test_aws_deeper_branching_dry_run_end_to_end(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "aws_deeper_branching_lab.json"
    objective_path = repo_root / "examples" / "objective_aws_deeper_branching.json"
    scope_path = repo_root / "examples" / "scope_aws_deeper_branching.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=10,
        seed=1,
    )

    report = (tmp_path / "report.json").read_text()
    report_md = (tmp_path / "report.md").read_text()

    assert '"objective_met": true' in report
    assert '"finance/payroll.csv"' in report
    assert '"tool": "s3_read_sensitive"' in report
    assert 'RoleQ' in report_md


def test_aws_secrets_branching_dry_run_end_to_end(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "aws_secrets_branching_lab.json"
    objective_path = repo_root / "examples" / "objective_aws_secrets_branching.json"
    scope_path = repo_root / "examples" / "scope_aws_secrets_branching.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=6,
        seed=1,
    )

    report = (tmp_path / "report.json").read_text()
    report_md = (tmp_path / "report.md").read_text()

    assert '"objective_met": true' in report
    assert 'prod/payroll-api-key' in report
    assert '"tool": "secretsmanager_read_secret"' in report
    assert 'RoleM' in report_md


def test_aws_secrets_branching_candidate_paths_favor_secret_relevant_role() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture = Fixture.load(repo_root / "fixtures" / "aws_secrets_branching_lab.json")
    objective = Objective.model_validate_json(
        (repo_root / "examples" / "objective_aws_secrets_branching.json").read_text()
    )
    scope = Scope.model_validate_json(
        (repo_root / "examples" / "scope_aws_secrets_branching.json").read_text()
    )

    snapshot = StateManager(
        objective=objective,
        scope=scope,
        fixture=AwsDryRunLab.from_fixture(fixture, scope),
        tool_registry=ToolRegistry.load(repo_root / "tools"),
    ).snapshot()

    scores = {path.target.rsplit("/", 1)[-1]: path.path_score for path in snapshot.candidate_paths}
    assert scores["RoleM"] > scores["RoleA"]
    assert scores["RoleM"] > scores["RoleQ"]


def test_aws_secrets_deeper_branching_dry_run_end_to_end(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "aws_secrets_deeper_branching_lab.json"
    objective_path = repo_root / "examples" / "objective_aws_secrets_deeper_branching.json"
    scope_path = repo_root / "examples" / "scope_aws_secrets_deeper_branching.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=8,
        seed=1,
    )

    report = (tmp_path / "report.json").read_text()
    report_md = (tmp_path / "report.md").read_text()

    assert '"objective_met": true' in report
    assert 'prod/payroll-api-key' in report
    assert '"tool": "secretsmanager_read_secret"' in report
    assert 'RoleQ' in report_md


def test_aws_secrets_backtracking_dry_run_end_to_end(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "aws_secrets_backtracking_lab.json"
    objective_path = repo_root / "examples" / "objective_aws_secrets_backtracking.json"
    scope_path = repo_root / "examples" / "scope_aws_secrets_backtracking.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=7,
        seed=1,
    )

    report = (tmp_path / "report.json").read_text()
    report_md = (tmp_path / "report.md").read_text()

    assert '"objective_met": true' in report
    assert 'prod/payroll-api-key' in report
    assert '"tool": "secretsmanager_read_secret"' in report
    assert 'RoleA' in report_md
    assert 'RoleM' in report_md


def test_external_entry_report_tracks_reachability_maturity(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / "compute_pivot_app_external_entry_lab.json"
    objective_path = repo_root / "examples" / "objective_compute_pivot_app_external_entry.json"
    scope_path = repo_root / "examples" / "scope_compute_pivot_app_external_entry.json"

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=tmp_path,
        max_steps=6,
        seed=1,
    )

    report = json.loads((tmp_path / "report.json").read_text())
    maturity = report["executive_summary"]["external_entry_maturity"]
    report_md = (tmp_path / "report.md").read_text()

    assert maturity["applicable"] is True
    assert maturity["classification"] == "public_exposure_structurally_linked_to_privileged_path"
    assert maturity["network_reachable_from_internet"]["status"] == "structural"
    assert maturity["backend_reachable"]["status"] == "structural"
    assert maturity["credential_acquisition_possible"]["status"] == "structural"
    assert maturity["data_path_exploitable"]["status"] == "not_observed"
    assert "## External Entry Maturity" in report_md
    assert "public_exposure_structurally_linked_to_privileged_path" in report_md


@pytest.mark.parametrize(
    ("fixture_name", "expected_statuses", "expected_classification", "expected_objective_met"),
    [
        (
            "compute_pivot_app_external_entry_surface_only_lab.json",
            {
                "network_reachable_from_internet": "structural",
                "backend_reachable": "not_observed",
                "credential_acquisition_possible": "not_observed",
                "data_path_exploitable": "not_observed",
            },
            "public_exposure_structurally_linked_to_privileged_path",
            False,
        ),
        (
            "compute_pivot_app_external_entry_backend_reachable_lab.json",
            {
                "network_reachable_from_internet": "proved",
                "backend_reachable": "proved",
                "credential_acquisition_possible": "not_observed",
                "data_path_exploitable": "not_observed",
            },
            "public_exposure_structurally_linked_to_privileged_path",
            False,
        ),
        (
            "compute_pivot_app_external_entry_credential_acquisition_lab.json",
            {
                "network_reachable_from_internet": "proved",
                "backend_reachable": "proved",
                "credential_acquisition_possible": "proved",
                "data_path_exploitable": "not_observed",
            },
            "public_exposure_structurally_linked_to_privileged_path",
            False,
        ),
        (
            "compute_pivot_app_external_entry_end_to_end_lab.json",
            {
                "network_reachable_from_internet": "proved",
                "backend_reachable": "proved",
                "credential_acquisition_possible": "proved",
                "data_path_exploitable": "proved",
            },
            "public_exploit_path_proved_end_to_end",
            True,
        ),
    ],
)
def test_external_entry_reachability_maturity_benchmark_states(
    tmp_path: Path,
    fixture_name: str,
    expected_statuses: dict[str, str],
    expected_classification: str,
    expected_objective_met: bool,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "fixtures" / fixture_name
    objective_path = repo_root / "examples" / "objective_external_entry_reachability_benchmark.json"
    scope_path = repo_root / "examples" / "scope_compute_pivot_app_external_entry.json"
    output_dir = tmp_path / fixture_name.replace(".json", "")

    run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=output_dir,
        max_steps=6,
        seed=1,
    )

    report = json.loads((output_dir / "report.json").read_text())
    maturity = report["executive_summary"]["external_entry_maturity"]

    assert report["objective_met"] is expected_objective_met
    assert maturity["classification"] == expected_classification
    for key, expected in expected_statuses.items():
        assert maturity[key]["status"] == expected


def test_mock_planner_prefers_higher_scored_assume_role() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture = Fixture.load(repo_root / "fixtures" / "aws_secrets_branching_lab.json")
    objective = Objective.model_validate_json(
        (repo_root / "examples" / "objective_aws_secrets_branching.json").read_text()
    )
    scope = Scope.model_validate_json(
        (repo_root / "examples" / "scope_aws_secrets_branching.json").read_text()
    )
    registry = ToolRegistry.load(repo_root / "tools")
    environment = AwsDryRunLab.from_fixture(fixture, scope)
    state = StateManager(
        objective=objective,
        scope=scope,
        fixture=environment,
        tool_registry=registry,
    )

    enumerate_action = registry.filter_actions(
        environment.enumerate_actions(state.snapshot()),
        state.snapshot().fixture_state.get("flags", []),
    )[0]
    observation = environment.execute(enumerate_action)
    state.apply_observation(enumerate_action, observation, "seed enumeration")

    snapshot = state.snapshot()
    available_actions = registry.filter_actions(
        environment.enumerate_actions(snapshot),
        snapshot.fixture_state.get("flags", []),
    )
    shaped_actions = shape_available_actions(snapshot, available_actions)
    decision = DeterministicPlanner(seed=1).decide(snapshot, shaped_actions)

    assert decision.action.target == "arn:aws:iam::123456789012:role/RoleM"


def test_aws_backtracking_real_local_artifacts_are_consistent() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture = Fixture.load(
        repo_root / "terraform_local_lab" / "rastro_local" / "aws_backtracking_lab.local.json"
    )
    scope = Scope.model_validate_json(
        (
            repo_root
            / "terraform_local_lab"
            / "rastro_local"
            / "scope_aws_backtracking_openai.local.json"
        ).read_text()
    )
    objective = Objective.model_validate_json(
        (
            repo_root
            / "terraform_local_lab"
            / "rastro_local"
            / "objective_aws_backtracking.local.json"
        ).read_text()
    )
    lab = AwsDryRunLab.from_fixture(fixture, scope)

    actions = lab.enumerate_actions(snapshot=None)

    assert objective.target == "arn:aws:s3:::sensitive-finance-data/payroll.csv"
    assert any(
        action.target == "arn:aws:iam::550192603632:role/A-FinanceAuditRole"
        for action in actions
    )
    assert any(
        action.target == "arn:aws:iam::550192603632:role/Z-DataOpsRole"
        for action in actions
    )


def test_aws_backtracking_real_local_exposes_progress_after_assume_role() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixture = Fixture.load(
        repo_root / "terraform_local_lab" / "rastro_local" / "aws_backtracking_lab.local.json"
    )
    scope = Scope.model_validate_json(
        (
            repo_root
            / "terraform_local_lab"
            / "rastro_local"
            / "scope_aws_backtracking_openai.local.json"
        ).read_text()
    )
    objective = Objective.model_validate_json(
        (
            repo_root
            / "terraform_local_lab"
            / "rastro_local"
            / "objective_aws_backtracking.local.json"
        ).read_text()
    )
    state = StateManager(objective=objective, scope=scope, fixture=fixture)
    tool_registry = ToolRegistry.load(repo_root / "tools")

    initial_actions = fixture.enumerate_actions(None)
    enum_action = next(action for action in initial_actions if action.tool == "iam_list_roles")
    enum_obs = fixture.execute(enum_action)
    state.apply_observation(enum_action, enum_obs, "enum", {})

    assume_action = next(
        action
        for action in tool_registry.filter_actions(
            fixture.enumerate_actions(state.snapshot()),
            state.snapshot().fixture_state.get("flags", []),
        )
        if action.target == "arn:aws:iam::550192603632:role/Z-DataOpsRole"
    )
    assume_obs = fixture.execute(assume_action)
    state.apply_observation(assume_action, assume_obs, "assume", {})

    available = tool_registry.filter_actions(
        fixture.enumerate_actions(state.snapshot()),
        state.snapshot().fixture_state.get("flags", []),
    )
    shaped = shape_available_actions(state.snapshot(), available)

    assert any(action.tool == "s3_read_sensitive" for action in available)
    assert len(shaped) == 1
    assert shaped[0].tool == "s3_read_sensitive"
