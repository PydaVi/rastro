from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from core.domain import Action, Observation, Objective, Scope
from core.fixture import Fixture


@dataclass
class StateSnapshot:
    objective: Objective
    scope: Scope
    fixture_state: Dict
    steps_taken: int
    actions_taken: List[Action]
    blocked_actions: List[Tuple[Action, str]]
    observations: List[Observation]


class StateManager:
    def __init__(self, objective: Objective, scope: Scope, fixture: Fixture) -> None:
        self._objective = objective
        self._scope = scope
        self._fixture = fixture
        self._initial_state = fixture.state_copy()
        self._steps_taken = 0
        self._actions_taken: List[Action] = []
        self._blocked_actions: List[Tuple[Action, str]] = []
        self._observations: List[Observation] = []

    def snapshot(self) -> StateSnapshot:
        return StateSnapshot(
            objective=self._objective,
            scope=self._scope,
            fixture_state=self._fixture.state_copy(),
            steps_taken=self._steps_taken,
            actions_taken=list(self._actions_taken),
            blocked_actions=list(self._blocked_actions),
            observations=list(self._observations),
        )

    def initial_state(self) -> Dict:
        return json.loads(json.dumps(self._initial_state))

    def apply_observation(self, action: Action, observation: Observation) -> None:
        self._steps_taken += 1
        self._actions_taken.append(action)
        self._observations.append(observation)

    def record_blocked(self, action: Action, reason: str) -> None:
        self._blocked_actions.append((action, reason))

    def is_objective_met(self) -> bool:
        criteria = self._objective.success_criteria
        required_flag = criteria.get("flag")
        if not required_flag:
            return False
        return self._fixture.has_flag(required_flag)
