from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from core.domain import Action, Observation


@dataclass
class GraphNode:
    node_id: str
    node_type: str
    metadata: Dict


@dataclass
class GraphEdge:
    source: str
    target: str
    action_type: str
    metadata: Dict


@dataclass
class AttackGraph:
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)

    def update(self, action: Action, observation: Observation, snapshot) -> None:
        actor_id = f"identity:{action.actor}"
        self._add_node(actor_id, "identity", {"name": action.actor})

        if action.target:
            target_id = f"resource:{action.target}"
            self._add_node(target_id, "resource", {"name": action.target})
            self.edges.append(
                GraphEdge(
                    source=actor_id,
                    target=target_id,
                    action_type=action.action_type.value,
                    metadata={"success": observation.success},
                )
            )

        if observation.success and observation.details.get("granted_role"):
            role = observation.details["granted_role"]
            role_id = f"identity:{role}"
            self._add_node(role_id, "identity", {"name": role})
            self.edges.append(
                GraphEdge(
                    source=actor_id,
                    target=role_id,
                    action_type="assume_role",
                    metadata={"success": True},
                )
            )

    def _add_node(self, node_id: str, node_type: str, metadata: Dict) -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = GraphNode(
                node_id=node_id,
                node_type=node_type,
                metadata=metadata,
            )

    def summary(self) -> Dict:
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        for node in self.nodes.values():
            label = f"{node.node_type}:{node.metadata.get('name', node.node_id)}"
            lines.append(f'  "{node.node_id}"["{label}"]')
        for edge in self.edges:
            label = edge.action_type
            style = ":::success" if edge.metadata.get("success") else ":::blocked"
            lines.append(
                f'  "{edge.source}" -->|"{label}"| "{edge.target}" {style}'
            )
        lines.append("classDef success stroke:#1b7f3b,stroke-width:2px;")
        lines.append("classDef blocked stroke:#b3261e,stroke-width:2px;")
        return "\n".join(lines)
