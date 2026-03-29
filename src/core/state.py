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
class CandidatePath:
    target: str
    status: str = "untested"
    times_tested: int = 0
    has_progress_actions: bool = False
    path_score: int = 0


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
    active_assumed_roles: List[str]
    active_branch_action_count: int
    enumeration_sufficient: bool = False
    should_commit_to_pivot: bool = False
    should_explore_current_branch: bool = False
    candidate_roles: List[str] = field(default_factory=list)
    candidate_paths: List[CandidatePath] = field(default_factory=list)


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
            active_assumed_roles=self._active_assumed_roles(),
            active_branch_action_count=self._active_branch_action_count(),
            enumeration_sufficient=self._enumeration_sufficient(),
            should_commit_to_pivot=self._should_commit_to_pivot(),
            should_explore_current_branch=self._should_explore_current_branch(),
            candidate_roles=self._candidate_roles(),
            candidate_paths=self._candidate_paths(),
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

    def _active_assumed_roles(self) -> List[str]:
        fixture_state = self._fixture.state_copy()
        identities = fixture_state.get("identities", {})
        active_roles: List[str] = []
        for role in self._tested_assume_roles:
            if role in self._failed_assume_roles:
                continue
            available_actions = identities.get(role, {}).get("available_actions", [])
            progress_actions = [
                action
                for action in available_actions
                if action.get("action_type") in {"enumerate", "access_resource"}
            ]
            if progress_actions:
                active_roles.append(role)
        return active_roles

    def _active_branch_action_count(self) -> int:
        fixture_state = self._fixture.state_copy()
        identities = fixture_state.get("identities", {})
        total = 0
        for role in self._active_assumed_roles():
            available_actions = identities.get(role, {}).get("available_actions", [])
            total += len(
                [
                    action
                    for action in available_actions
                    if action.get("action_type") in {"enumerate", "access_resource"}
                ]
            )
        return total

    def _candidate_roles(self) -> List[str]:
        fixture_state = self._fixture.state_copy()
        identities = fixture_state.get("identities", {})
        candidate_roles: List[str] = []
        for details in identities.values():
            for action in details.get("available_actions", []):
                if action.get("action_type") != "assume_role":
                    continue
                target = action.get("target")
                if target and target not in candidate_roles:
                    candidate_roles.append(target)
        return candidate_roles

    def _enumeration_sufficient(self) -> bool:
        return bool(self._steps_taken > 0 and self._candidate_roles())

    def _should_commit_to_pivot(self) -> bool:
        return self._enumeration_sufficient()

    def _should_explore_current_branch(self) -> bool:
        return self._active_branch_action_count() > 0

    def _candidate_paths(self) -> List[CandidatePath]:
        active_roles = set(self._active_assumed_roles())
        failed_roles = set(self._failed_assume_roles)
        tested_roles = set(self._tested_assume_roles)
        identities = self._fixture.state_copy().get("identities", {})
        candidate_paths: List[CandidatePath] = []

        for role in self._candidate_roles():
            available_actions = identities.get(role, {}).get("available_actions", [])
            has_progress_actions = any(
                action.get("action_type") in {"enumerate", "access_resource"}
                for action in available_actions
            )
            if role in active_roles:
                status = "active"
            elif role in failed_roles:
                status = "failed"
            elif role in tested_roles:
                status = "tested"
            else:
                status = "untested"

            times_tested = sum(
                1
                for action in self._actions_taken
                if action.action_type.value == "assume_role" and action.target == role
            )
            candidate_paths.append(
                CandidatePath(
                    target=role,
                    status=status,
                    times_tested=times_tested,
                    has_progress_actions=has_progress_actions,
                    path_score=self._path_score(
                        status=status,
                        times_tested=times_tested,
                        has_progress_actions=has_progress_actions,
                    ),
                )
            )

        return candidate_paths

    def _path_score(self, status: str, times_tested: int, has_progress_actions: bool) -> int:
        score = 0
        if status == "active":
            score += 50
        elif status == "untested":
            score += 20
        elif status == "tested":
            score += 5
        elif status == "failed":
            score -= 100

        if has_progress_actions:
            score += 15

        score -= times_tested * 5
        return score
