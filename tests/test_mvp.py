from pathlib import Path

import pytest

from app.main import _build_execution_surface, run
from core.attack_graph import AttackGraph
from core.audit import AuditLogger
from core.domain import Action, ActionType, Decision, Objective, Observation, Scope
from core.aws_dry_run_lab import AwsDryRunLab
from execution.aws_executor import AwsRealExecutor, AwsRealExecutorStub
from core.state import StateManager
from reporting.report import ReportGenerator
from execution.scope_enforcer import ScopeEnforcer
from core.fixture import Fixture
from core.sanitizer import write_sanitized_artifacts
from core.tool_registry import ToolRegistry
from planner.action_shaping import shape_available_actions
from planner.ollama_planner import OllamaPlanner
from planner.openai_planner import _parse_response as parse_openai_response
from planner.mock_planner import DeterministicPlanner


class FakeAwsClient:
    def get_caller_identity(self, region: str, credentials=None):
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
        return {
            "ContentLength": 24,
            "ETag": '"etag"',
            "Preview": "payroll-preview",
        }

    def list_objects(self, region: str, bucket: str, prefix=None, credentials=None):
        return ["payroll.csv", "notes.txt"]



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
    assert 'candidate assume_role' in report_md


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
