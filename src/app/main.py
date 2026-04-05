from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer

from core.domain import ActionType, Objective, Scope, TargetType
from core.aws_dry_run_lab import AwsDryRunLab
from core.state import StateManager
from core.fixture import Fixture
from core.tool_registry import ToolRegistry
from planner import get_planner
from planner.action_shaping import shape_available_actions
from planner.interface import Planner
from execution.scope_enforcer import ScopeEnforcer
from execution.executor import Executor
from execution.aws_executor import AwsRealExecutor
from execution.preflight import run_preflight
from operations.campaign_synthesis import synthesize_foundation_campaigns
from operations.discovery import run_foundation_discovery
from operations.target_selection import select_foundation_targets
from core.attack_graph import AttackGraph
from core.audit import AuditLogger
from core.sanitizer import write_sanitized_artifacts
from operations.service import (
    list_available_bundles,
    list_available_profiles,
    load_authorization,
    load_target,
    run_assessment,
    run_campaign,
    run_discovery_driven_assessment,
    validate_target,
    write_assessment_summary,
)
from reporting.report import ReportGenerator


app = typer.Typer(add_completion=False)
profile_app = typer.Typer(add_completion=False)
target_app = typer.Typer(add_completion=False)
preflight_app = typer.Typer(add_completion=False)
discovery_app = typer.Typer(add_completion=False)
target_selection_app = typer.Typer(add_completion=False)
campaign_synthesis_app = typer.Typer(add_completion=False)
campaign_app = typer.Typer(add_completion=False)
assessment_app = typer.Typer(add_completion=False)

app.add_typer(profile_app, name="profile")
app.add_typer(target_app, name="target")
app.add_typer(preflight_app, name="preflight")
app.add_typer(discovery_app, name="discovery")
app.add_typer(target_selection_app, name="target-selection")
app.add_typer(campaign_synthesis_app, name="campaign-synthesis")
app.add_typer(campaign_app, name="campaign")
app.add_typer(assessment_app, name="assessment")


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
    result = execute_run(
        fixture_path=fixture_path,
        objective_path=objective_path,
        scope_path=scope_path,
        output_dir=output_dir,
        max_steps=max_steps,
        seed=seed,
    )

    typer.echo(f"Report JSON: {result['report_json']}")
    typer.echo(f"Report MD: {result['report_md']}")
    typer.echo(f"Attack Graph: {result['attack_graph']}")


def execute_run(
    *,
    fixture_path: Path | None,
    objective_path: Path,
    scope_path: Path,
    output_dir: Path,
    max_steps: int = 5,
    seed: Optional[int] = None,
    runtime_fixture=None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    objective = Objective.model_validate_json(objective_path.read_text())
    scope = Scope.model_validate_json(scope_path.read_text())
    fixture = runtime_fixture or (Fixture.load(fixture_path) if fixture_path else None)
    if fixture is None:
        raise typer.BadParameter("execute_run requires fixture_path or runtime_fixture")
    _validate_run_inputs(fixture, objective, scope)
    environment = _build_environment(fixture, scope)
    preflight = run_preflight(scope)
    if not preflight.ok:
        raise typer.BadParameter(
            f"AWS preflight failed: {json.dumps(preflight.details, ensure_ascii=True)}"
        )

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
            "preflight": {"ok": preflight.ok, "details": preflight.details},
            "execution_policy": execution_policy,
            "max_steps": effective_max_steps,
        },
    )

    for step in range(effective_max_steps):
        snapshot = state.snapshot()
        available_actions = environment.enumerate_actions(snapshot)
        if tool_registry is not None:
            filtered_actions = tool_registry.filter_actions(
                available_actions, snapshot.fixture_state.get("flags", [])
            )
            available_actions = _restore_objective_target_access_actions(
                snapshot,
                available_actions,
                filtered_actions,
                scope,
            )
        available_actions = shape_available_actions(snapshot, available_actions)
        decision = planner.decide(snapshot, available_actions)

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
        preflight={"ok": preflight.ok, "details": preflight.details},
        execution_context={
            "runtime_mode": "blind_real" if runtime_fixture is not None else "fixture",
            "synthetic_fixture_used": runtime_fixture is None,
            "fixture_metadata": environment.metadata(),
        },
    )
    report_json_path = output_dir / "report.json"
    report_md_path = output_dir / "report.md"
    graph_path = output_dir / "attack_graph.mmd"
    report_json_path.write_text(json.dumps(report["json"], indent=2))
    report_md_path.write_text(report["markdown"])
    graph_path.write_text(report["json"]["attack_graph_mermaid"])
    write_sanitized_artifacts(output_dir, report["json"], report["markdown"], audit.path)

    audit.log_event(
        "run_complete",
        {
            "objective_met": state.is_objective_met(),
            "preflight": {"ok": preflight.ok, "details": preflight.details},
            "report_json": str(report_json_path),
            "report_md": str(report_md_path),
            "attack_graph_mermaid": str(graph_path),
            "execution_policy": execution_policy,
        },
    )

    return {
        "objective_met": state.is_objective_met(),
        "preflight": {"ok": preflight.ok, "details": preflight.details},
        "report_json": report_json_path,
        "report_md": report_md_path,
        "attack_graph": graph_path,
    }


@profile_app.command("list")
def profile_list() -> None:
    for profile in list_available_profiles():
        typer.echo(f"{profile.name}\t{profile.bundle}\t{profile.description}")
    for bundle, profiles in list_available_bundles().items():
        typer.echo(f"bundle:{bundle}\t{','.join(profiles)}")


@target_app.command("validate")
def target_validate(
    target_path: Path = typer.Option(..., "--target"),
) -> None:
    target = load_target(target_path)
    issues = validate_target(target)
    if issues:
        raise typer.BadParameter("; ".join(issues))
    typer.echo(f"Target valid: {target.name}")


@preflight_app.command("validate")
def preflight_validate(
    scope_path: Path = typer.Option(..., "--scope"),
) -> None:
    scope = Scope.model_validate_json(scope_path.read_text())
    result = run_preflight(scope)
    typer.echo(json.dumps({"ok": result.ok, "details": result.details}, indent=2))
    if not result.ok:
        raise typer.Exit(code=1)


@discovery_app.command("run")
def discovery_run(
    bundle_name: str = typer.Option(..., "--bundle"),
    target_path: Path = typer.Option(..., "--target"),
    authorization_path: Path = typer.Option(..., "--authorization"),
    output_dir: Path = typer.Option(..., "--out"),
) -> None:
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)
    issues = validate_target(target)
    if issues:
        raise typer.BadParameter("; ".join(issues))
    discovery_json, discovery_md, snapshot = run_foundation_discovery(
        bundle_name=bundle_name,
        target=target,
        authorization=authorization,
        output_dir=output_dir,
    )
    typer.echo(f"Discovery JSON: {discovery_json}")
    typer.echo(f"Discovery MD: {discovery_md}")
    typer.echo(f"Discovery resources: {len(snapshot['resources'])}")


@target_selection_app.command("run")
def target_selection_run(
    discovery_path: Path = typer.Option(..., "--discovery"),
    output_dir: Path = typer.Option(..., "--out"),
    max_candidates_per_profile: int = typer.Option(5, "--max-candidates-per-profile"),
) -> None:
    discovery_snapshot = json.loads(discovery_path.read_text())
    candidates_json, candidates_md, payload = select_foundation_targets(
        discovery_snapshot=discovery_snapshot,
        output_dir=output_dir,
        max_candidates_per_profile=max_candidates_per_profile,
    )
    typer.echo(f"Target Candidates JSON: {candidates_json}")
    typer.echo(f"Target Candidates MD: {candidates_md}")
    typer.echo(f"Target Candidates total: {payload['summary']['candidates_total']}")


@campaign_synthesis_app.command("run")
def campaign_synthesis_run(
    candidates_path: Path = typer.Option(..., "--candidates"),
    target_path: Path = typer.Option(..., "--target"),
    authorization_path: Path = typer.Option(..., "--authorization"),
    output_dir: Path = typer.Option(..., "--out"),
    max_plans_per_profile: int = typer.Option(1, "--max-plans-per-profile"),
) -> None:
    candidates_payload = json.loads(candidates_path.read_text())
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)
    issues = validate_target(target)
    if issues:
        raise typer.BadParameter("; ".join(issues))
    campaign_plan_json, campaign_plan_md, payload = synthesize_foundation_campaigns(
        candidates_payload=candidates_payload,
        target=target,
        authorization=authorization,
        output_dir=output_dir,
        max_plans_per_profile=max_plans_per_profile,
    )
    typer.echo(f"Campaign Plan JSON: {campaign_plan_json}")
    typer.echo(f"Campaign Plan MD: {campaign_plan_md}")
    typer.echo(f"Campaign Plans total: {payload['summary']['plans_total']}")


@campaign_app.command("run")
def campaign_run(
    profile_name: str = typer.Option(..., "--profile"),
    target_path: Path = typer.Option(..., "--target"),
    authorization_path: Path = typer.Option(..., "--authorization"),
    output_dir: Path = typer.Option(..., "--out"),
    max_steps: Optional[int] = typer.Option(None, "--max-steps"),
    seed: Optional[int] = typer.Option(None, "--seed"),
) -> None:
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)
    issues = validate_target(target)
    if issues:
        raise typer.BadParameter("; ".join(issues))
    result = run_campaign(
        profile_name=profile_name,
        target=target,
        authorization=authorization,
        output_dir=output_dir,
        runner=execute_run,
        max_steps=max_steps,
        seed=seed,
    )
    typer.echo(f"Campaign profile: {result.profile}")
    typer.echo(f"Campaign status: {result.status}")
    typer.echo(f"Campaign objective_met: {result.objective_met}")
    if result.report_md:
        typer.echo(f"Campaign report: {result.report_md}")
    if result.error:
        typer.echo(f"Campaign error: {result.error}")
    if result.status in {"preflight_failed", "run_failed"}:
        raise typer.Exit(code=1)


@assessment_app.command("run")
def assessment_run(
    bundle_name: str = typer.Option(..., "--bundle"),
    target_path: Path = typer.Option(..., "--target"),
    authorization_path: Path = typer.Option(..., "--authorization"),
    output_dir: Path = typer.Option(..., "--out"),
    max_steps: Optional[int] = typer.Option(None, "--max-steps"),
    seed: Optional[int] = typer.Option(None, "--seed"),
    discovery_driven: bool = typer.Option(False, "--discovery-driven"),
) -> None:
    target = load_target(target_path)
    authorization = load_authorization(authorization_path)
    issues = validate_target(target)
    if issues:
        raise typer.BadParameter("; ".join(issues))
    if discovery_driven:
        result = run_discovery_driven_assessment(
            bundle_name=bundle_name,
            target=target,
            authorization=authorization,
            output_dir=output_dir,
            runner=execute_run,
            max_steps=max_steps,
            seed=seed,
        )
    else:
        result = run_assessment(
            bundle_name=bundle_name,
            target=target,
            authorization=authorization,
            output_dir=output_dir,
            runner=execute_run,
            max_steps=max_steps,
            seed=seed,
        )
    assessment_json, assessment_md = write_assessment_summary(result, output_dir)
    failed_campaigns = [campaign for campaign in result.campaigns if campaign.status in {"preflight_failed", "run_failed"}]
    typer.echo(f"Assessment JSON: {assessment_json}")
    typer.echo(f"Assessment MD: {assessment_md}")
    if result.artifacts.get("assessment_findings_json"):
        typer.echo(f"Findings JSON: {result.artifacts['assessment_findings_json']}")
    if result.artifacts.get("assessment_findings_md"):
        typer.echo(f"Findings MD: {result.artifacts['assessment_findings_md']}")
    if failed_campaigns:
        typer.echo(f"Assessment failed campaigns: {len(failed_campaigns)}")
    if failed_campaigns:
        raise typer.Exit(code=1)


def _build_environment(fixture: Fixture, scope: Scope):
    if scope.target == TargetType.AWS and scope.dry_run:
        return AwsDryRunLab.from_fixture(fixture, scope)
    return fixture


def _build_execution_surface(environment, scope: Scope):
    if scope.target == TargetType.AWS and not scope.dry_run:
        return AwsRealExecutor(environment, scope)
    return environment


def _build_execution_policy(scope: Scope) -> dict:
    return {
        "target": scope.target.value,
        "dry_run_required": scope.target == TargetType.AWS and not _aws_real_execution_enabled(),
        "dry_run_applied": scope.dry_run,
        "real_execution_enabled": _aws_real_execution_enabled(),
        "allowed_services": scope.allowed_services,
        "allowed_regions": scope.allowed_regions,
        "aws_account_ids": scope.aws_account_ids,
        "authorization_document": scope.authorization_document,
    }




def _validate_run_inputs(fixture, objective: Objective, scope: Scope) -> None:
    if scope.target == TargetType.AWS and not scope.dry_run and not _aws_real_execution_enabled():
        raise typer.BadParameter(
            "AWS real execution is disabled. Set RASTRO_ENABLE_AWS_REAL=1 to allow dry_run=false."
        )

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
            "AWS scope is incompatible with the provided fixture/objective. "
            "Use AWS-shaped identifiers (ARNs) consistently across fixture, objective and scope."
        )

    if scope.target == TargetType.FIXTURE and has_aws_identifier:
        raise typer.BadParameter(
            "Fixture target is incompatible with AWS-shaped fixture/objective data. "
            "Use target=aws with the AWS dry-run examples."
        )



def _is_aws_identifier(value: str | None) -> bool:
    return bool(value and value.startswith("arn:aws:"))


def _aws_real_execution_enabled() -> bool:
    return os.getenv("RASTRO_ENABLE_AWS_REAL", "0") == "1"


def _restore_objective_target_access_actions(snapshot, original_actions, filtered_actions, scope: Scope):
    if scope.target != TargetType.AWS or scope.dry_run:
        return filtered_actions
    objective_target = getattr(getattr(snapshot, "objective", None), "target", None)
    if not objective_target:
        return filtered_actions
    restored = list(filtered_actions)
    seen = {
        (
            action.action_type.value,
            action.actor,
            action.target,
            tuple(sorted(action.parameters.items())),
            action.tool,
        )
        for action in restored
    }
    for action in original_actions:
        key = (
            action.action_type.value,
            action.actor,
            action.target,
            tuple(sorted(action.parameters.items())),
            action.tool,
        )
        if action.action_type == ActionType.ACCESS_RESOURCE and action.target == objective_target and key not in seen:
            restored.append(action)
    return restored


if __name__ == "__main__":
    app()
