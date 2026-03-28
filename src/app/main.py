from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from core.domain import Objective, Scope, TargetType
from core.aws_dry_run_lab import AwsDryRunLab
from core.state import StateManager
from core.fixture import Fixture
from core.tool_registry import ToolRegistry
from planner import get_planner
from planner.interface import Planner
from execution.scope_enforcer import ScopeEnforcer
from execution.executor import Executor
from execution.aws_executor import AwsRealExecutorStub
from core.attack_graph import AttackGraph
from core.audit import AuditLogger
from reporting.report import ReportGenerator


app = typer.Typer(add_completion=False)


@app.command()
def run(
    fixture_path: Path = typer.Option(..., "--fixture", "-f"),
    objective_path: Path = typer.Option(..., "--objective", "-o"),
    scope_path: Path = typer.Option(..., "--scope", "-s"),
    output_dir: Path = typer.Option(Path("outputs"), "--out", "-d"),
    max_steps: int = typer.Option(5, "--max-steps", "-m"),
    seed: Optional[int] = typer.Option(None, "--seed"),
) -> None:
    """
    Run the MVP agent against a synthetic fixture.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    objective = Objective.model_validate_json(objective_path.read_text())
    scope = Scope.model_validate_json(scope_path.read_text())
    fixture = Fixture.load(fixture_path)
    _validate_run_inputs(fixture, objective, scope)
    environment = _build_environment(fixture, scope)

    tool_registry = None
    tools_path = Path("tools")
    if tools_path.exists():
        tool_registry = ToolRegistry.load(tools_path)

    state = StateManager(
        objective=objective,
        scope=scope,
        fixture=environment,
        tool_registry=tool_registry,
    )
    planner_cfg = scope.planner
    backend = planner_cfg.backend if planner_cfg else "mock"
    planner_kwargs = {}
    if planner_cfg:
        if planner_cfg.model:
            planner_kwargs["model"] = planner_cfg.model
        if planner_cfg.base_url:
            planner_kwargs["base_url"] = planner_cfg.base_url
        if planner_cfg.api_key:
            planner_kwargs["api_key"] = planner_cfg.api_key
        if planner_cfg.timeout:
            planner_kwargs["timeout"] = planner_cfg.timeout
    if seed is not None:
        planner_kwargs["seed"] = seed

    planner: Planner = get_planner(backend=backend, **planner_kwargs)
    scope_enforcer = ScopeEnforcer(scope)
    execution_surface = _build_execution_surface(environment, scope)
    executor = Executor(execution_surface)
    graph = AttackGraph()
    audit = AuditLogger(output_dir / "audit.jsonl")
    reporter = ReportGenerator(output_dir)

    effective_max_steps = min(max_steps, scope.max_steps)

    execution_policy = _build_execution_policy(scope)

    audit.log_event(
        "run_start",
        {
            "objective": objective.model_dump(),
            "scope": scope.model_dump(),
            "fixture": environment.metadata(),
            "execution_policy": execution_policy,
            "max_steps": effective_max_steps,
        },
    )

    for step in range(effective_max_steps):
        snapshot = state.snapshot()
        available_actions = environment.enumerate_actions(snapshot)
        if tool_registry is not None:
            available_actions = tool_registry.filter_actions(
                available_actions, snapshot.fixture_state.get("flags", [])
            )
        decision = planner.decide(state.snapshot(), available_actions)

        allowed = scope_enforcer.validate(decision.action)
        if not allowed:
            state.record_blocked(decision.action, decision.reason)
            audit.log_event(
                "action_blocked",
                {
                    "step": step,
                    "action": decision.action.model_dump(),
                    "reason": decision.reason,
                    "planner_metadata": decision.planner_metadata,
                },
            )
            continue

        observation = executor.execute(decision.action)
        state.apply_observation(
            decision.action,
            observation,
            decision.reason,
            decision.planner_metadata,
        )
        graph.update(decision.action, observation, state.snapshot())
        audit.log_event(
            "action_executed",
            {
                "step": step,
                "action": decision.action.model_dump(),
                "reason": decision.reason,
                "planner_metadata": decision.planner_metadata,
                "observation": observation.model_dump(),
            },
        )

        if state.is_objective_met():
            audit.log_event("objective_met", {"step": step})
            break

    report = reporter.generate(
        state.snapshot(),
        graph,
        audit,
        state.initial_state(),
        state.is_objective_met(),
    )
    report_json_path = output_dir / "report.json"
    report_md_path = output_dir / "report.md"
    graph_path = output_dir / "attack_graph.mmd"
    report_json_path.write_text(json.dumps(report["json"], indent=2))
    report_md_path.write_text(report["markdown"])
    graph_path.write_text(report["json"]["attack_graph_mermaid"])

    audit.log_event(
        "run_complete",
        {
            "objective_met": state.is_objective_met(),
            "report_json": str(report_json_path),
            "report_md": str(report_md_path),
            "attack_graph_mermaid": str(graph_path),
            "execution_policy": execution_policy,
        },
    )

    typer.echo(f"Report JSON: {report_json_path}")
    typer.echo(f"Report MD: {report_md_path}")
    typer.echo(f"Attack Graph: {graph_path}")


def _build_environment(fixture: Fixture, scope: Scope):
    if scope.target == TargetType.AWS:
        return AwsDryRunLab.from_fixture(fixture, scope)
    return fixture


def _build_execution_surface(environment, scope: Scope):
    if scope.target == TargetType.AWS and not scope.dry_run:
        return AwsRealExecutorStub(scope)
    return environment


def _build_execution_policy(scope: Scope) -> dict:
    return {
        "target": scope.target.value,
        "dry_run_required": scope.target == TargetType.AWS,
        "dry_run_applied": scope.dry_run,
        "allowed_services": scope.allowed_services,
        "allowed_regions": scope.allowed_regions,
        "aws_account_ids": scope.aws_account_ids,
        "authorization_document": scope.authorization_document,
    }


def _validate_run_inputs(fixture: Fixture, objective: Objective, scope: Scope) -> None:
    observed_resources = set(scope.allowed_resources)
    observed_resources.add(objective.target)
    for action in fixture.enumerate_actions(None):
        observed_resources.add(action.actor)
        if action.target:
            observed_resources.add(action.target)

    has_aws_identifier = any(_is_aws_identifier(value) for value in observed_resources)
    has_non_aws_identifier = any(value and not _is_aws_identifier(value) for value in observed_resources)

    if scope.target == TargetType.AWS and has_non_aws_identifier:
        raise typer.BadParameter(
            "AWS dry-run scope is incompatible with the provided fixture/objective. "
            "Use AWS-shaped identifiers (ARNs) consistently across fixture, objective and scope."
        )

    if scope.target == TargetType.FIXTURE and has_aws_identifier:
        raise typer.BadParameter(
            "Fixture target is incompatible with AWS-shaped fixture/objective data. "
            "Use target=aws with the AWS dry-run examples."
        )



def _is_aws_identifier(value: str | None) -> bool:
    return bool(value and value.startswith("arn:aws:"))


if __name__ == "__main__":
    app()
