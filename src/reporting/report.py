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
            "allowed_actions": allowed_actions,
            "blocked_actions": blocked_actions,
            "observations": observations,
            "graph_summary": graph_summary,
            "attack_graph_mermaid": mermaid,
            "objective_met": objective_met,
        }

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
