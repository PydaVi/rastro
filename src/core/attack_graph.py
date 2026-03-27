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
        def node_id(raw: str) -> str:
            return "".join(ch if ch.isalnum() else "_" for ch in raw)

        lines = ["graph TD"]
        id_map: Dict[str, str] = {}

        for node in self.nodes.values():
            safe_id = node_id(node.node_id)
            id_map[node.node_id] = safe_id
            label = f"{node.node_type}:{node.metadata.get('name', node.node_id)}"
            lines.append(f'  {safe_id}["{label}"]')

        for idx, edge in enumerate(self.edges):
            label = edge.action_type
            source = id_map.get(edge.source, node_id(edge.source))
            target = id_map.get(edge.target, node_id(edge.target))
            lines.append(f'  {source} -->|"{label}"| {target}')
            if edge.metadata.get("success"):
                lines.append(f"  linkStyle {idx} stroke:#1b7f3b,stroke-width:2px;")
            else:
                lines.append(f"  linkStyle {idx} stroke:#b3261e,stroke-width:2px;")

        return "\n".join(lines)
