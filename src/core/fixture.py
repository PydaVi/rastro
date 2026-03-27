from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from core.domain import Action, ActionType, Observation


@dataclass
class Fixture:
    data: Dict

    @classmethod
    def load(cls, path: Path) -> "Fixture":
        return cls(json.loads(path.read_text()))

    def metadata(self) -> Dict:
        return {
            "name": self.data.get("name"),
            "description": self.data.get("description"),
            "version": self.data.get("version"),
        }

    def state_copy(self) -> Dict:
        return json.loads(json.dumps(self.data.get("state", {})))

    def has_flag(self, flag: str) -> bool:
        return flag in self.data.get("state", {}).get("flags", [])

    def enumerate_actions(self, snapshot) -> List[Action]:
        actions: List[Action] = []
        state = self.data.get("state", {})
        identities = state.get("identities", {})
        for identity, details in identities.items():
            for action_def in details.get("available_actions", []):
                actions.append(
                    Action(
                        action_type=ActionType(action_def["action_type"]),
                        actor=identity,
                        target=action_def.get("target"),
                        parameters=action_def.get("parameters", {}),
                    )
                )
        return actions

    def execute(self, action: Action) -> Observation:
        transitions = self.data.get("transitions", [])
        for transition in transitions:
            if (
                transition["action_type"] == action.action_type.value
                and transition["actor"] == action.actor
                and transition.get("target") == action.target
            ):
                self._apply_transition(transition)
                return Observation(success=True, details=transition.get("observation", {}))
        return Observation(success=False, details={"reason": "no_transition"})

    def _apply_transition(self, transition: Dict) -> None:
        state = self.data.setdefault("state", {})
        for flag in transition.get("add_flags", []):
            state.setdefault("flags", [])
            if flag not in state["flags"]:
                state["flags"].append(flag)
        for identity, updates in transition.get("update_identities", {}).items():
            identity_state = state.setdefault("identities", {}).setdefault(identity, {})
            for key, value in updates.items():
                identity_state[key] = value
