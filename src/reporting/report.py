from __future__ import annotations

from dataclasses import dataclass
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
        mermaid = graph.to_mermaid()

        report_json = {
            "objective": objective.model_dump(),
            "starting_conditions": initial_state,
            "steps_taken": steps_taken,
            "steps": steps,
            "allowed_actions": allowed_actions,
            "blocked_actions": blocked_actions,
            "observations": observations,
            "graph_summary": graph_summary,
            "attack_graph_mermaid": mermaid,
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
                f"{step['action']['actor']} -> {step['action'].get('target') or '-'} "
                f"(tool={step['action'].get('tool') or '-'}) "
                f"| success={status} | backend={backend}{suffix} "
                f"| reason={step['reason'] or '-'}"
            )

        planner_details = []
        for step in steps:
            planner_details.append(
                {
                    "step": step["step"],
                    "planner_backend": step["planner_backend"],
                    "planner_model": step["planner_model"],
                    "fallback_used": step["fallback_used"],
                    "raw_response": step["raw_response"],
                }
            )

        markdown = [
            "# MVP Report",
            "",
            f"Objective: {objective.description}",
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
            f"```\n{planner_details}\n```",
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
            "## Attack Graph (Mermaid)",
            "```mermaid",
            mermaid,
            "```",
            "",
            "## Outcome",
            f"Objective met: {objective_met}",
            "",
        ]

        return {"json": report_json, "markdown": "\n".join(markdown)}
