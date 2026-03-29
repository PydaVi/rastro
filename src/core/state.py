from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Protocol, Tuple

from core.domain import Action, Observation, Objective, Scope
from core.tool_registry import ToolRegistry


class StateSurface(Protocol):
    def state_copy(self) -> Dict:
        ...

    def has_flag(self, flag: str) -> bool:
        ...


@dataclass
class StateSnapshot:
    objective: Objective
    scope: Scope
    fixture_state: Dict
    tool_registry: ToolRegistry | None
    steps_taken: int
    actions_taken: List[Action]
    action_reasons: List[str]
    action_metadata: List[Dict]
    blocked_actions: List[Tuple[Action, str]]
    observations: List[Observation]
    tested_assume_roles: List[str]
    failed_assume_roles: List[str]


class StateManager:
    def __init__(
        self,
        objective: Objective,
        scope: Scope,
        fixture: StateSurface,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self._objective = objective
        self._scope = scope
        self._fixture = fixture
        self._tool_registry = tool_registry
        self._initial_state = fixture.state_copy()
        self._steps_taken = 0
        self._actions_taken: List[Action] = []
        self._action_reasons: List[str] = []
        self._action_metadata: List[Dict] = []
        self._blocked_actions: List[Tuple[Action, str]] = []
        self._observations: List[Observation] = []
        self._tested_assume_roles: List[str] = []
        self._failed_assume_roles: List[str] = []

    def snapshot(self) -> StateSnapshot:
        return StateSnapshot(
            objective=self._objective,
            scope=self._scope,
            fixture_state=self._fixture.state_copy(),
            tool_registry=self._tool_registry,
            steps_taken=self._steps_taken,
            actions_taken=list(self._actions_taken),
            action_reasons=list(self._action_reasons),
            action_metadata=list(self._action_metadata),
            blocked_actions=list(self._blocked_actions),
            observations=list(self._observations),
            tested_assume_roles=list(self._tested_assume_roles),
            failed_assume_roles=list(self._failed_assume_roles),
        )

    def initial_state(self) -> Dict:
        return json.loads(json.dumps(self._initial_state))

    def apply_observation(
        self,
        action: Action,
        observation: Observation,
        reason: str,
        metadata: Dict | None = None,
    ) -> None:
        self._steps_taken += 1
        self._actions_taken.append(action)
        self._action_reasons.append(reason)
        self._action_metadata.append(metadata or {})
        self._observations.append(observation)
        self._update_path_memory(action, observation)

    def record_blocked(self, action: Action, reason: str) -> None:
        self._blocked_actions.append((action, reason))

    def is_objective_met(self) -> bool:
        criteria = self._objective.success_criteria
        required_flag = criteria.get("flag")
        if not required_flag:
            return False
        return self._fixture.has_flag(required_flag)

    def _update_path_memory(self, action: Action, observation: Observation) -> None:
        if action.action_type.value == "assume_role" and observation.success:
            granted_role = observation.details.get("granted_role") or action.target
            if granted_role and granted_role not in self._tested_assume_roles:
                self._tested_assume_roles.append(granted_role)

        if not action.actor.startswith("arn:aws:iam::") and not action.actor.startswith("arn:aws:sts::"):
            return
        if ":role/" not in action.actor and ":assumed-role/" not in action.actor:
            return
        if self.is_objective_met():
            return

        fixture_state = self._fixture.state_copy()
        role_identity = action.actor
        if ":assumed-role/" in role_identity:
            role_name = role_identity.split(":assumed-role/", 1)[1].split("/", 1)[0]
            account = role_identity.split("::", 1)[1].split(":", 1)[0]
            role_identity = f"arn:aws:iam::{account}:role/{role_name}"

        identities = fixture_state.get("identities", {})
        available = identities.get(role_identity, {}).get("available_actions", [])
        if available:
            return
        if role_identity not in self._failed_assume_roles:
            self._failed_assume_roles.append(role_identity)
