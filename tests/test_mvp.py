import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.main import _build_execution_surface, app, execute_run, run
from core.attack_graph import AttackGraph
from core.audit import AuditLogger
from core.domain import Action, ActionType, Decision, Objective, Observation, Scope
from core.aws_dry_run_lab import AwsDryRunLab
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
    write_assessment_summary,
)
from operations.models import AssessmentResult, CampaignResult
from operations.discovery import run_foundation_discovery
from operations.campaign_synthesis import synthesize_foundation_campaigns
from operations.synthetic_catalog import get_synthetic_profile
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

    def list_roles(self, region: str, credentials=None):
        return ["arn:aws:iam::123456789012:role/AuditRole"]

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
        if path == "/prod":
            return ["/prod/payroll/api_key"]
        if path == "/finance":
            return ["/finance/quarterly/reporting_key"]
        return []

    def get_secret_value(self, region: str, secret_id: str, credentials=None):
        return {
            "ARN": f"arn:aws:secretsmanager:{region}:123456789012:secret:{secret_id}",
            "Name": secret_id,
            "VersionId": "example-version",
            "SecretString": "payroll-api-key-preview",
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
    assert all(":role/aws-service-role/" not in resource["identifier"] for resource in snapshot["resources"])
    assert any(
        resource["identifier"] == "arn:aws:ssm:us-east-1:550192603632:parameter/prod/payroll/api_key"
        for resource in snapshot["resources"]
        if resource["resource_type"] == "secret.ssm_parameter"
    )


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
            scope.write_text("{}")
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
