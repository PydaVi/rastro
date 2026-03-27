from __future__ import annotations

import random
from typing import List

from core.domain import Action, ActionType, Decision
from planner.interface import Planner


class DeterministicPlanner(Planner):
    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def decide(self, snapshot, available_actions: List[Action]) -> Decision:
        if not available_actions:
            return Decision(
                action=Action(
                    action_type=ActionType.ANALYZE,
                    actor="system",
                    target=None,
                    parameters={"note": "no_actions"},
                ),
                reason="No available actions; defaulting to analyze.",
            )

        available_actions = _filter_by_tool_preconditions(snapshot, available_actions)

        # Simple deterministic heuristic: prefer assume_role, then access_resource, then enumerate.
        priority = {
            ActionType.ASSUME_ROLE: 0,
            ActionType.ACCESS_RESOURCE: 1,
            ActionType.ENUMERATE: 2,
            ActionType.ANALYZE: 3,
        }
        sorted_actions = sorted(
            available_actions,
            key=lambda a: (priority.get(a.action_type, 9), a.actor, a.target or ""),
        )
        action = sorted_actions[0]
        return Decision(
            action=action,
            reason=f"Selected highest-priority action {action.action_type.value}.",
        )


def _filter_by_tool_preconditions(snapshot, actions: List[Action]) -> List[Action]:
    registry = getattr(snapshot, "tool_registry", None)
    if registry is None:
        return actions

    flags = set(snapshot.fixture_state.get("flags", []))
    eligible: List[Action] = []
    for action in actions:
        if not action.tool:
            eligible.append(action)
            continue
        tool = registry.get(action.tool)
        if tool is None:
            continue
        if all(pre in flags for pre in tool.preconditions):
            eligible.append(action)

    return eligible or actions
