from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from core.domain import Action, ActionType, Observation, Technique


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

    def canonicalize(self, value):
        return self._canonicalize_value(value)

    def enumerate_actions(self, snapshot) -> List[Action]:
        actions: List[Action] = []
        state = self.data.get("state", {})
        identities = state.get("identities", {})
        for identity, details in identities.items():
            for action_def in details.get("available_actions", []):
                for expanded_action_def in self._expand_action_def(action_def):
                    actions.append(
                        Action(
                            action_type=ActionType(expanded_action_def["action_type"]),
                            actor=identity,
                            target=expanded_action_def.get("target"),
                            parameters=expanded_action_def.get("parameters", {}),
                            technique=(
                                Technique.model_validate(expanded_action_def["technique"])
                                if expanded_action_def.get("technique")
                                else None
                            ),
                            tool=expanded_action_def.get("tool"),
                        )
                    )
        return actions

    def execute(self, action: Action) -> Observation:
        transitions = self.data.get("transitions", [])
        for transition in transitions:
            if (
                transition["action_type"] == action.action_type.value
                and transition["actor"] == action.actor
                and self._strings_match(transition.get("target"), action.target)
                and self._parameters_match(
                    transition.get("parameters"),
                    action.parameters,
                )
            ):
                self._apply_transition(transition)
                return Observation(success=True, details=transition.get("observation", {}))
        return Observation(success=False, details={"reason": "no_transition"})

    def _parameters_match(self, expected: Dict | None, actual: Dict) -> bool:
        if not expected:
            return True
        return self._canonicalize_value(expected) == self._canonicalize_value(actual)

    def _expand_action_def(self, action_def: Dict) -> List[Dict]:
        expanded = [deepcopy(action_def)]
        target = action_def.get("target")
        for alias in self._aliases_for(target):
            replacements = [(target, alias), *self._derived_replacements(target, alias)]
            aliased = deepcopy(action_def)
            for canonical, replacement in replacements:
                aliased = self._replace_alias_in_mapping(aliased, canonical, replacement)
            aliased["target"] = alias
            expanded.append(aliased)
        return expanded

    def _replace_alias_in_mapping(self, value, canonical: str, alias: str):
        if isinstance(value, str):
            return alias if value == canonical else value
        if isinstance(value, list):
            return [self._replace_alias_in_mapping(item, canonical, alias) for item in value]
        if isinstance(value, dict):
            return {key: self._replace_alias_in_mapping(item, canonical, alias) for key, item in value.items()}
        return value

    def _strings_match(self, expected: str | None, actual: str | None) -> bool:
        return self._canonicalize_string(expected) == self._canonicalize_string(actual)

    def _canonicalize_value(self, value):
        if isinstance(value, str):
            return self._canonicalize_string(value)
        if isinstance(value, list):
            return [self._canonicalize_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._canonicalize_value(item) for key, item in value.items()}
        return value

    def _canonicalize_string(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._reverse_alias_map().get(value, value)

    def _aliases_for(self, canonical: str | None) -> List[str]:
        if canonical is None:
            return []
        return self.data.get("aliases", {}).get(canonical, [])

    def _derived_replacements(self, canonical: str | None, alias: str | None) -> List[tuple[str, str]]:
        if not canonical or not alias:
            return []
        derived: List[tuple[str, str]] = []
        if ":secret:" in canonical and ":secret:" in alias:
            derived.append((canonical.split(":secret:", 1)[1], alias.split(":secret:", 1)[1]))
        if ":parameter/" in canonical and ":parameter/" in alias:
            derived.append((canonical.split(":parameter/", 1)[1], alias.split(":parameter/", 1)[1]))
            derived.append((f"/{canonical.split(':parameter/', 1)[1]}", f"/{alias.split(':parameter/', 1)[1]}"))
        if canonical.startswith("arn:aws:s3:::") and alias.startswith("arn:aws:s3:::"):
            canonical_path = canonical.replace("arn:aws:s3:::", "", 1)
            alias_path = alias.replace("arn:aws:s3:::", "", 1)
            if "/" in canonical_path and "/" in alias_path:
                canonical_bucket, canonical_key = canonical_path.split("/", 1)
                alias_bucket, alias_key = alias_path.split("/", 1)
                derived.append((canonical_bucket, alias_bucket))
                derived.append((canonical_key, alias_key))
        return derived

    def _reverse_alias_map(self) -> Dict[str, str]:
        reverse: Dict[str, str] = {}
        for canonical, aliases in self.data.get("aliases", {}).items():
            for alias in aliases:
                reverse[alias] = canonical
                for derived_canonical, derived_alias in self._derived_replacements(canonical, alias):
                    reverse[derived_alias] = derived_canonical
        return reverse

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
