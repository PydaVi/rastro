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

        active_role_actors = set()
        failed_assume_roles = set()
        candidate_path_status = {}
        if snapshot is not None:
            for observation in snapshot.observations:
                granted_role = observation.details.get("granted_role")
                if granted_role:
                    active_role_actors.add(granted_role)
            failed_assume_roles = set(getattr(snapshot, "failed_assume_roles", []))
            candidate_path_status = {
                path.target: path.status
                for path in getattr(snapshot, "candidate_paths", [])
            }

        # Prefer progressing from an already-assumed role before pivoting again.
        def action_priority(action: Action) -> tuple[int, int, str, str]:
            if action.actor in active_role_actors:
                priority = {
                    ActionType.ACCESS_RESOURCE: 0,
                    ActionType.ENUMERATE: 1,
                    ActionType.ASSUME_ROLE: 2,
                    ActionType.ANALYZE: 3,
                }
                actor_rank = 0
            else:
                priority = {
                    ActionType.ASSUME_ROLE: 0,
                    ActionType.ACCESS_RESOURCE: 1,
                    ActionType.ENUMERATE: 2,
                    ActionType.ANALYZE: 3,
                }
                actor_rank = 1
            return (
                2
                if action.action_type == ActionType.ASSUME_ROLE and action.target in failed_assume_roles
                else 0,
                0
                if action.action_type == ActionType.ASSUME_ROLE
                and candidate_path_status.get(action.target) == "untested"
                else 1,
                actor_rank,
                priority.get(action.action_type, 9),
                action.actor,
                action.target or "",
            )

        sorted_actions = sorted(
            available_actions,
            key=action_priority,
        )
        action = sorted_actions[0]
        return Decision(
            action=action,
            reason=f"Selected highest-priority action {action.action_type.value}.",
            planner_metadata={"planner_backend": "mock"},
        )
