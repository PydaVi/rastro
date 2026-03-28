from pathlib import Path

import pytest

from app.main import run
from core.attack_graph import AttackGraph
from core.audit import AuditLogger
from core.domain import Action, ActionType, Decision, Objective, Observation, Scope
from core.aws_dry_run_lab import AwsDryRunLab
from core.state import StateManager
from reporting.report import ReportGenerator
from execution.scope_enforcer import ScopeEnforcer
from core.fixture import Fixture
from planner.ollama_planner import OllamaPlanner
from planner.openai_planner import _parse_response as parse_openai_response
from planner.mock_planner import DeterministicPlanner


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

def test_aws_scope_rejects_dry_run_false() -> None:
    with pytest.raises(ValueError, match="dry_run=true"):
        Scope(
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

    with pytest.raises(Exception, match="AWS dry-run scope is incompatible"):
        run(
            fixture_path=fixture_path,
            objective_path=objective_path,
            scope_path=scope_path,
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
