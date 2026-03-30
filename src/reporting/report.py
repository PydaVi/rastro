from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Dict

from core.attack_graph import AttackGraph
from core.audit import AuditLogger


@dataclass
class ReportGenerator:
    output_dir: Path

    def generate(
        self,
        snapshot,
        graph: AttackGraph,
        audit: AuditLogger,
        initial_state: Dict,
        objective_met: bool,
    ) -> Dict:
        objective = snapshot.objective
        steps_taken = snapshot.steps_taken
        allowed_actions = [a.model_dump() for a in snapshot.actions_taken]
        steps = []
        for idx, action in enumerate(snapshot.actions_taken):
            observation = None
            if idx < len(snapshot.observations):
                observation = snapshot.observations[idx].model_dump()
            reason = None
            if idx < len(snapshot.action_reasons):
                reason = snapshot.action_reasons[idx]
            planner_metadata = {}
            if idx < len(snapshot.action_metadata):
                planner_metadata = snapshot.action_metadata[idx]
            raw_response = planner_metadata.get("raw_response")
            fallback_used = bool(reason and "Fallback para" in reason)
            steps.append(
                {
                    "step": idx + 1,
                    "action": action.model_dump(),
                    "reason": reason,
                    "fallback_used": fallback_used,
                    "planner_metadata": planner_metadata,
                    "planner_backend": planner_metadata.get("planner_backend"),
                    "planner_model": planner_metadata.get("planner_model"),
                    "raw_response": raw_response,
                    "observation": observation,
                }
            )
        tool_chain = []
        for action in snapshot.actions_taken:
            if action.tool:
                tool_chain.append(action.tool)
        mitre_techniques = []
        seen = set()
        for action in snapshot.actions_taken:
            if action.technique:
                key = (
                    action.technique.mitre_id,
                    action.technique.mitre_name,
                    action.technique.tactic,
                    action.technique.platform,
                )
                if key not in seen:
                    seen.add(key)
                    mitre_techniques.append(action.technique.model_dump())
        blocked_actions = [
            {"action": action.model_dump(), "reason": reason}
            for action, reason in snapshot.blocked_actions
        ]
        observations = [o.model_dump() for o in snapshot.observations]
        graph_summary = graph.summary()
        choice_summary = _build_choice_summary(initial_state, steps)
        mermaid = _build_enriched_mermaid(graph, choice_summary)
        attack_graph_dot = graph.to_dot()
        decision_chain_dot = _build_decision_chain_dot(steps)
        executive_summary = _build_executive_summary(steps, objective_met)
        execution_policy = _build_execution_policy(snapshot.scope)

        report_json = {
            "objective": objective.model_dump(),
            "starting_conditions": initial_state,
            "executive_summary": executive_summary,
            "execution_policy": execution_policy,
            "steps_taken": steps_taken,
            "steps": steps,
            "allowed_actions": allowed_actions,
            "blocked_actions": blocked_actions,
            "observations": observations,
            "graph_summary": graph_summary,
            "choice_summary": choice_summary,
            "attack_graph_mermaid": mermaid,
            "attack_graph_dot": attack_graph_dot,
            "decision_chain_dot": decision_chain_dot,
            "mitre_techniques": mitre_techniques,
            "tool_chain": tool_chain,
            "objective_met": objective_met,
        }

        step_lines = []
        for step in steps:
            status = step["observation"]["success"] if step["observation"] else "n/a"
            backend = step["planner_backend"] or "unknown"
            suffix = " | fallback=true" if step["fallback_used"] else ""
            step_lines.append(
                f"{step['step']}. {step['action']['action_type']} "
                f"{_short_resource(step['action']['actor'])} -> {_short_resource(step['action'].get('target') or '-')} "
                f"(tool={step['action'].get('tool') or '-'}) "
                f"| success={status} | backend={backend}{suffix} "
                f"| reason={step['reason'] or '-'}"
            )

        planner_lines = []
        for step in steps:
            line = (
                f"step={step['step']} backend={step['planner_backend'] or '-'} "
                f"model={step['planner_model'] or '-'} fallback={step['fallback_used']}"
            )
            if step["raw_response"]:
                line += f" raw={step['raw_response']}"
            planner_lines.append(line)

        markdown = [
            "# MVP Report",
            "",
            f"Objective: {objective.description}",
            "",
            "## Executive Summary",
            f"- Initial identity: {_short_resource(executive_summary['initial_identity'])}",
            f"- Assumed role: {_short_resource(executive_summary['assumed_role'])}",
            f"- Final resource: {_short_resource(executive_summary['final_resource'])}",
            f"- Execution mode: {executive_summary['execution_mode']}",
            f"- Real API called: {executive_summary['real_api_called']}",
            f"- Proof: {executive_summary['proof']}",
            f"- Objective met: {executive_summary['objective_met']}",
            "",
            "## Execution Policy",
            f"- Target: {execution_policy['target']}",
            f"- Dry-run required: {execution_policy['dry_run_required']}",
            f"- Dry-run applied: {execution_policy['dry_run_applied']}",
            f"- Real execution enabled: {execution_policy['real_execution_enabled']}",
            f"- Allowed services: {execution_policy['allowed_services']}",
            f"- Allowed regions: {execution_policy['allowed_regions']}",
            f"- AWS account IDs: {execution_policy['aws_account_ids']}",
            f"- Authorization document: {execution_policy['authorization_document']}",
            "",
            "## Starting Conditions",
            f"```\n{initial_state}\n```",
            "",
            "## Steps Taken",
            f"Total steps: {steps_taken}",
            "",
            "## Step-by-Step",
            "```\n" + "\n".join(step_lines) + "\n```",
            "",
            "## Planner Details",
            "```\n" + "\n".join(planner_lines) + "\n```",
            "",
            "## Allowed Actions",
            f"```\n{allowed_actions}\n```",
            "",
            "## Blocked Actions",
            f"```\n{blocked_actions}\n```",
            "",
            "## Observations",
            f"```\n{observations}\n```",
            "",
            "## Path Choice",
            f"- Candidate roles: {[ _short_resource(role) for role in choice_summary['candidate_roles'] ]}",
            f"- Selected role: {_short_resource(choice_summary['selected_role'])}",
            f"- Rejected roles: {[ _short_resource(role) for role in choice_summary['rejected_roles'] ]}",
            "",
            "## Graph Summary",
            f"- Nodes: {graph_summary['node_count']}",
            f"- Edges: {graph_summary['edge_count']}",
            "",
            "## MITRE ATT&CK Mapping",
            "```\n" + str(mitre_techniques) + "\n```",
            "",
            "## Tool Chain",
            "```\n" + str(tool_chain) + "\n```",
            "",
            "## Attack Graph (DOT)",
            "```dot",
            attack_graph_dot,
            "```",
            "",
            "## Decision Chain (DOT)",
            "```dot",
            decision_chain_dot,
            "```",
            "",
            "## Outcome",
            f"Objective met: {objective_met}",
            "",
        ]

        return {"json": report_json, "markdown": "\n".join(markdown)}


def _build_executive_summary(steps: list[Dict], objective_met: bool) -> Dict:
    summary = {
        "initial_identity": None,
        "assumed_role": None,
        "final_resource": None,
        "execution_mode": None,
        "real_api_called": None,
        "proof": None,
        "objective_met": objective_met,
    }

    for step in steps:
        observation = step.get("observation") or {}
        details = observation.get("details") or {}
        action = step.get("action") or {}

        if summary["initial_identity"] is None:
            aws_identity = details.get("aws_identity")
            if aws_identity:
                summary["initial_identity"] = aws_identity.get("arn")
            else:
                summary["initial_identity"] = action.get("actor")

        if summary["assumed_role"] is None and details.get("granted_role"):
            summary["assumed_role"] = details.get("granted_role")

        if summary["final_resource"] is None and action.get("target"):
            summary["final_resource"] = action.get("target")

        if details.get("execution_mode") is not None:
            summary["execution_mode"] = details.get("execution_mode")

        if details.get("real_api_called") is not None:
            summary["real_api_called"] = details.get("real_api_called")

        if details.get("evidence"):
            summary["proof"] = details.get("evidence")
        elif summary["proof"] is None and details.get("simulated_policy_result"):
            summary["proof"] = details.get("simulated_policy_result")

    if steps:
        summary["final_resource"] = steps[-1].get("action", {}).get("target")

    return summary


def _build_decision_chain_dot(steps: list[Dict]) -> str:
    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("\"", "\\\"")

    def short(value: str | None) -> str:
        if not value:
            return "-"
        return _short_resource(value)

    lines = [
        "digraph DecisionChain {",
        "  rankdir=TB;",
        "  node [shape=box, style=rounded, fontname=\"Helvetica\"];",
    ]

    for step in steps:
        step_idx = step.get("step")
        action = step.get("action", {})
        action_type = action.get("action_type", "-")
        actor = short(action.get("actor"))
        target = short(action.get("target"))
        reason = step.get("reason") or ""
        if len(reason) > 120:
            reason = reason[:117] + "..."
        label = (
            f"step {step_idx}\\n{action_type}\\n{actor} -> {target}\\nreason: {reason}"
        )
        lines.append(f"  step_{step_idx} [label=\"{escape(label)}\"];")

    for idx in range(1, len(steps)):
        lines.append(f"  step_{idx} -> step_{idx + 1};")

    lines.append("}")
    return "\n".join(lines)


def _short_resource(value: str | None) -> str:
    if not value:
        return "-"
    if value.startswith("arn:aws:iam::"):
        if ":user/" in value:
            return value.split(":user/", 1)[1]
        if ":role/" in value:
            return value.split(":role/", 1)[1]
        return value.rsplit(":", 1)[-1]
    if value.startswith("arn:aws:s3:::"):
        return value.replace("arn:aws:s3:::", "s3://", 1)
    return value


def _build_execution_policy(scope) -> Dict:
    return {
        "target": scope.target.value,
        "dry_run_required": scope.target.value == "aws" and not _aws_real_execution_enabled(),
        "dry_run_applied": scope.dry_run,
        "real_execution_enabled": _aws_real_execution_enabled(),
        "allowed_services": list(scope.allowed_services),
        "allowed_regions": list(scope.allowed_regions),
        "aws_account_ids": list(scope.aws_account_ids),
        "authorization_document": scope.authorization_document,
    }


def _aws_real_execution_enabled() -> bool:
    return os.getenv("RASTRO_ENABLE_AWS_REAL", "0") == "1"


def _build_choice_summary(initial_state: Dict, steps: list[Dict]) -> Dict:
    candidate_roles = []
    identities = initial_state.get("identities", {})
    for details in identities.values():
        for action in details.get("available_actions", []):
            if action.get("action_type") == "assume_role" and action.get("target"):
                candidate_roles.append(action["target"])
    candidate_roles = list(dict.fromkeys(candidate_roles))

    selected_role = None
    for step in steps:
        details = (step.get("observation") or {}).get("details") or {}
        if details.get("granted_role"):
            selected_role = details.get("granted_role")
            break

    rejected_roles = [role for role in candidate_roles if role != selected_role]
    return {
        "candidate_roles": candidate_roles,
        "selected_role": selected_role,
        "rejected_roles": rejected_roles,
    }


def _build_enriched_mermaid(graph: AttackGraph, choice_summary: Dict) -> str:
    base = graph.to_mermaid().splitlines()
    candidate_roles = choice_summary.get("candidate_roles") or []
    selected_role = choice_summary.get("selected_role")
    rejected_roles = choice_summary.get("rejected_roles") or []
    if not candidate_roles or not selected_role or not rejected_roles:
        return "\n".join(base)

    def node_id(raw: str) -> str:
        return "".join(ch if ch.isalnum() else "_" for ch in raw)

    analyst_node = None
    for node in graph.nodes.values():
        if node.node_type == "identity" and node.metadata.get("name") != selected_role:
            analyst_node = node
            break
    if analyst_node is None:
        return "\n".join(base)

    extra_lines = []
    next_link_index = len(graph.edges)
    analyst_safe = node_id(analyst_node.node_id)
    for rejected_role in rejected_roles:
        resource_id = f"resource:{rejected_role}"
        identity_id = f"identity:{rejected_role}"
        safe_resource = node_id(resource_id)
        safe_identity = node_id(identity_id)
        extra_lines.append(f'  {safe_resource}["resource:{rejected_role}"]')
        extra_lines.append(f'  {safe_identity}["identity:{rejected_role}"]')
        extra_lines.append(f'  {analyst_safe} -.->|"candidate assume_role"| {safe_resource}')
        extra_lines.append(
            f"  linkStyle {next_link_index} stroke:#6b7280,stroke-width:1.5px,stroke-dasharray:4 3;"
        )
        next_link_index += 1
        extra_lines.append(f'  {analyst_safe} -.->|"candidate assume_role"| {safe_identity}')
        extra_lines.append(
            f"  linkStyle {next_link_index} stroke:#6b7280,stroke-width:1.5px,stroke-dasharray:4 3;"
        )
        next_link_index += 1

    return "\n".join(base + extra_lines)
