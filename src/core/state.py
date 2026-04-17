from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import PurePosixPath
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
    observed_resources: List[str] = field(default_factory=list)
    lookahead_signals: List[str] = field(default_factory=list)


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
    objective_met: bool
    tested_assume_roles: List[str]
    failed_assume_roles: List[str]
    active_assumed_roles: List[str]
    active_branch_identities: List[str] = field(default_factory=list)
    uncredentialed_identities: List[str] = field(default_factory=list)
    active_branch_action_count: int = 0
    enumeration_sufficient: bool = False
    should_commit_to_pivot: bool = False
    should_explore_current_branch: bool = False
    candidate_roles: List[str] = field(default_factory=list)
    candidate_paths: List[CandidatePath] = field(default_factory=list)
    attempted_access_targets: List[Dict[str, str]] = field(default_factory=list)
    attempted_enumerations: List[Dict[str, str]] = field(default_factory=list)


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
        self._activated_identities: List[str] = []
        self._uncredentialed_identities: List[str] = []
        self._attempted_access_targets: set[tuple[str, str]] = set()
        self._attempted_enumerations: set[tuple[str, str]] = set()

    def snapshot(self) -> StateSnapshot:
        fixture_state = self._fixture.state_copy()
        fixture_state["flags"] = self._active_flags(fixture_state.get("flags", []))
        return StateSnapshot(
            objective=self._objective,
            scope=self._scope,
            fixture_state=fixture_state,
            tool_registry=self._tool_registry,
            steps_taken=self._steps_taken,
            actions_taken=list(self._actions_taken),
            action_reasons=list(self._action_reasons),
            action_metadata=list(self._action_metadata),
            blocked_actions=list(self._blocked_actions),
            observations=list(self._observations),
            objective_met=self.is_objective_met(),
            tested_assume_roles=list(self._tested_assume_roles),
            failed_assume_roles=list(self._failed_assume_roles),
            active_assumed_roles=self._active_assumed_roles(),
            active_branch_identities=self._active_branch_identities(),
            uncredentialed_identities=list(self._uncredentialed_identities),
            active_branch_action_count=self._active_branch_action_count(),
            enumeration_sufficient=self._enumeration_sufficient(),
            should_commit_to_pivot=self._should_commit_to_pivot(),
            should_explore_current_branch=self._should_explore_current_branch(),
            candidate_roles=self._candidate_roles(),
            candidate_paths=self._candidate_paths(),
            attempted_access_targets=[
                {"actor": actor, "target": target}
                for actor, target in sorted(self._attempted_access_targets)
            ],
            attempted_enumerations=[
                {"actor": actor, "target": target}
                for actor, target in sorted(self._attempted_enumerations)
            ],
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
        if action.action_type.value == "access_resource":
            actor = action.actor
            target = action.target
            if actor and target:
                self._attempted_access_targets.add((actor, target))
        if action.action_type.value == "enumerate":
            actor = action.actor
            target = action.target
            if actor:
                self._attempted_enumerations.add((actor, target or "*"))
        self._update_path_memory(action, observation)

    def record_blocked(self, action: Action, reason: str) -> None:
        self._blocked_actions.append((action, reason))

    def is_objective_met(self) -> bool:
        criteria = self._objective.success_criteria
        required_flag = criteria.get("flag")
        if required_flag:
            active_flags = self._active_flags(self._fixture.state_copy().get("flags", []))
            if required_flag in active_flags:
                return True
        mode = criteria.get("mode")
        target = self._objective.target
        if mode == "access_proved" and target:
            canonical_target = self._fixture.canonicalize(target)
            for action, observation in zip(self._actions_taken, self._observations):
                if not observation.success:
                    continue
                if action.action_type.value != "access_resource":
                    continue
                if self._fixture.canonicalize(action.target) != canonical_target:
                    continue
                evidence = observation.details.get("evidence") or {}
                if not evidence:
                    continue
                if evidence.get("simulated"):
                    continue
                return True
            return False
        if mode == "assume_role_proved" and target:
            canonical_target = self._fixture.canonicalize(target)
            for action, observation in zip(self._actions_taken, self._observations):
                if not observation.success:
                    continue
                if action.action_type.value != "assume_role":
                    continue
                granted_role = observation.details.get("granted_role") or action.target
                if self._fixture.canonicalize(granted_role) != canonical_target:
                    continue
                if action.tool == "iam_simulate_assume_role":
                    continue
                return True
            return False
        if mode == "policy_probe_proved" and target:
            canonical_target = self._fixture.canonicalize(target)
            required_tool = criteria.get("required_tool")
            for action, observation in zip(self._actions_taken, self._observations):
                if not observation.success:
                    continue
                if action.action_type.value != "access_resource":
                    continue
                if self._fixture.canonicalize(action.target) != canonical_target:
                    continue
                if required_tool and action.tool != required_tool:
                    continue
                request_summary = observation.details.get("request_summary") or {}
                if "iam:SimulatePrincipalPolicy" not in request_summary.get("api_calls", []):
                    continue
                return True
            return False
        if mode == "policy_mutation_proved" and target:
            # Proves a real IAM mutation was executed against the target role.
            canonical_target = self._fixture.canonicalize(target)
            required_tool = criteria.get("required_tool")
            for action, observation in zip(self._actions_taken, self._observations):
                if not observation.success:
                    continue
                if action.action_type.value != "access_resource":
                    continue
                canonical_action_target = self._fixture.canonicalize(action.target or "")
                if canonical_action_target != canonical_target and canonical_target not in (action.parameters.get("role_arn", "") or ""):
                    continue
                if required_tool and action.tool != required_tool:
                    continue
                if not observation.details.get("mutation_executed"):
                    continue
                return True
            return False
        if target:
            canonical_target = self._fixture.canonicalize(target)
            for action, observation in zip(self._actions_taken, self._observations):
                if not observation.success:
                    continue
                if self._fixture.canonicalize(action.target) == canonical_target:
                    return True
                if self._observation_contains_target(observation.details, canonical_target):
                    return True
        return False

    def _observation_contains_target(self, value, canonical_target: str | None) -> bool:
        if canonical_target is None:
            return False
        canonical_value = self._fixture.canonicalize(value)
        if isinstance(canonical_value, str):
            return canonical_value == canonical_target
        if isinstance(canonical_value, list):
            return any(self._observation_contains_target(item, canonical_target) for item in canonical_value)
        if isinstance(canonical_value, dict):
            return any(self._observation_contains_target(item, canonical_target) for item in canonical_value.values())
        return False

    def _update_path_memory(self, action: Action, observation: Observation) -> None:
        if action.action_type.value == "assume_role" and observation.success:
            granted_role = observation.details.get("granted_role") or action.target
            if granted_role and granted_role not in self._tested_assume_roles:
                self._tested_assume_roles.append(granted_role)
            if granted_role and granted_role not in self._activated_identities:
                self._activated_identities.append(granted_role)

        reached_role = observation.details.get("reached_role")
        if not reached_role:
            reached_role = (observation.details.get("evidence") or {}).get("reached_role")
        if observation.success and reached_role and reached_role not in self._activated_identities:
            self._activated_identities.append(reached_role)

        if observation.details.get("reason") == "missing_actor_credentials":
            actor = observation.details.get("actor") or action.actor
            if actor and actor not in self._uncredentialed_identities:
                self._uncredentialed_identities.append(actor)

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
            # If only repeated access_resource actions remain, mark as exhausted.
            remaining = []
            for action in available:
                action_type = action.get("action_type")
                if action_type != "access_resource":
                    remaining.append(action)
                    continue
                target = action.get("target")
                if target and self._access_attempted(role_identity, target):
                    continue
                remaining.append(action)
            if remaining:
                return
            if role_identity not in self._failed_assume_roles:
                self._failed_assume_roles.append(role_identity)
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
            progress_actions = []
            for action in available_actions:
                action_type = action.get("action_type")
                if action_type not in {"enumerate", "access_resource", "analyze", "assume_role"}:
                    continue
                if action_type == "access_resource":
                    target = action.get("target")
                    if target and self._access_attempted(role, target):
                        continue
                progress_actions.append(action)
            if progress_actions:
                active_roles.append(role)
                continue
            if identities.get(role, {}).get("active"):
                active_roles.append(role)
        return active_roles

    def _active_branch_identities(self) -> List[str]:
        fixture_state = self._fixture.state_copy()
        identities = fixture_state.get("identities", {})
        active_identities: List[str] = []
        for identity in self._activated_identities:
            if identity in self._failed_assume_roles:
                continue
            if identity in self._uncredentialed_identities:
                continue
            available_actions = identities.get(identity, {}).get("available_actions", [])
            progress_actions = []
            for action in available_actions:
                action_type = action.get("action_type")
                if action_type not in {"enumerate", "access_resource", "analyze", "assume_role"}:
                    continue
                if action_type == "access_resource":
                    target = action.get("target")
                    if target and self._access_attempted(identity, target):
                        continue
                progress_actions.append(action)
            if progress_actions:
                active_identities.append(identity)
                continue
            if identities.get(identity, {}).get("active"):
                active_identities.append(identity)
        return active_identities

    def _active_branch_action_count(self) -> int:
        fixture_state = self._fixture.state_copy()
        identities = fixture_state.get("identities", {})
        total = 0
        for identity in self._active_branch_identities():
            available_actions = identities.get(identity, {}).get("available_actions", [])
            if available_actions:
                total += len(
                    [
                        action
                        for action in available_actions
                        if action.get("action_type") in {"enumerate", "access_resource", "analyze", "assume_role"}
                    ]
                )
                continue
            if identities.get(identity, {}).get("active"):
                total += 1
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
        if candidate_roles:
            return candidate_roles
        for role in fixture_state.get("discovered_roles", []):
            if role and role not in candidate_roles:
                candidate_roles.append(role)
        return candidate_roles

    def _enumeration_sufficient(self) -> bool:
        return bool(self._steps_taken > 0 and self._candidate_roles())

    def _should_commit_to_pivot(self) -> bool:
        return self._enumeration_sufficient()

    def _should_explore_current_branch(self) -> bool:
        return self._active_branch_action_count() > 0

    def _active_flags(self, base_flags: List[str]) -> List[str]:
        active_flags = set(base_flags)
        if self._tool_registry is None:
            return sorted(active_flags)
        for action, observation in zip(self._actions_taken, self._observations):
            if not observation.success or not action.tool:
                continue
            tool = self._tool_registry.get(action.tool)
            if tool is None:
                continue
            active_flags.update(tool.postconditions)
        return sorted(active_flags)

    def _candidate_paths(self) -> List[CandidatePath]:
        active_roles = set(self._active_assumed_roles())
        failed_roles = set(self._failed_assume_roles)
        tested_roles = set(self._tested_assume_roles)
        fixture_state = self._fixture.state_copy()
        identities = fixture_state.get("identities", {})
        candidate_paths: List[CandidatePath] = []

        for role in self._candidate_roles():
            available_actions = identities.get(role, {}).get("available_actions", [])
            has_progress_actions = False
            for action in available_actions:
                action_type = action.get("action_type")
                if action_type not in {"enumerate", "access_resource", "analyze", "assume_role"}:
                    continue
                if action_type == "access_resource":
                    target = action.get("target")
                    if target and self._access_attempted(role, target):
                        continue
                has_progress_actions = True
                break
            if not has_progress_actions and role in fixture_state.get("discovered_roles", []):
                has_progress_actions = True
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
                    observed_resources=self._observed_resources_for_role(role),
                    lookahead_signals=self._lookahead_signals_for_role(role),
                    path_score=self._path_score(
                        role=role,
                        status=status,
                        times_tested=times_tested,
                        has_progress_actions=has_progress_actions,
                    ),
                )
            )

        return candidate_paths

    def _path_score(
        self,
        role: str,
        status: str,
        times_tested: int,
        has_progress_actions: bool,
    ) -> int:
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
        score -= self._attempted_access_count(role) * 15
        score += self._objective_relevance_score(role)
        score += self._lookahead_relevance_score(role)
        score += self._bucket_mismatch_penalty(role)
        score += self._analyze_unlock_bonus(role)
        return score

    def _access_attempted(self, role: str, target: str) -> bool:
        return (role, target) in self._attempted_access_targets

    def _attempted_access_count(self, role: str) -> int:
        return sum(1 for actor, _ in self._attempted_access_targets if actor == role)

    def _observed_resources_for_role(self, role: str) -> List[str]:
        observed: List[str] = []
        for action, observation in zip(self._actions_taken, self._observations):
            actor = action.actor
            if ":assumed-role/" in actor:
                role_name = actor.split(":assumed-role/", 1)[1].split("/", 1)[0]
                account = actor.split("::", 1)[1].split(":", 1)[0]
                actor = f"arn:aws:iam::{account}:role/{role_name}"
            if actor != role:
                continue
            observed.extend(observation.details.get("discovered_objects", []))
            evidence = observation.details.get("evidence", {})
            bucket = evidence.get("bucket")
            if bucket:
                observed.append(f"arn:aws:s3:::{bucket}")
            object_key = evidence.get("object_key")
            if object_key:
                observed.append(object_key)
        return list(dict.fromkeys(observed))

    def _objective_relevance_score(self, role: str) -> int:
        observed = self._observed_resources_for_role(role)
        if not observed:
            return 0

        target_tokens, target_bucket, target_key = self._extract_tokens(self._objective.target)
        score = 0
        for resource in observed:
            resource_tokens, bucket, key = self._extract_tokens(resource)
            if key and target_key and key == target_key:
                score += 100
            if bucket and target_bucket and bucket == target_bucket:
                score += 80
            score += 10 * len(target_tokens & resource_tokens)
        return score

    def _lookahead_signals_for_role(self, role: str) -> List[str]:
        identities = self._fixture.state_copy().get("identities", {})
        available_actions = identities.get(role, {}).get("available_actions", [])
        signals: List[str] = []
        for action in available_actions:
            parameters = action.get("parameters", {})
            target = action.get("target")
            if action.get("action_type") == "access_resource" and target:
                signals.append(target)
            bucket = parameters.get("bucket")
            if bucket:
                signals.append(f"arn:aws:s3:::{bucket}")
            prefix = parameters.get("prefix")
            if prefix:
                signals.append(prefix)
            object_key = parameters.get("object_key")
            if object_key:
                signals.append(object_key)
        if signals:
            return list(dict.fromkeys(signals))

        fixture_transitions = self._fixture_transitions()
        for transition in fixture_transitions:
            if transition.get("action_type") != "assume_role":
                continue
            if transition.get("target") != role:
                continue
            future_identity = transition.get("update_identities", {}).get(role, {})
            for action in future_identity.get("available_actions", []):
                parameters = action.get("parameters", {})
                target = action.get("target")
                if action.get("action_type") == "access_resource" and target:
                    signals.append(target)
                bucket = parameters.get("bucket")
                if bucket:
                    signals.append(f"arn:aws:s3:::{bucket}")
                prefix = parameters.get("prefix")
                if prefix:
                    signals.append(prefix)
                object_key = parameters.get("object_key")
                if object_key:
                    signals.append(object_key)
                for nested_transition in fixture_transitions:
                    if nested_transition.get("actor") != role:
                        continue
                    if nested_transition.get("action_type") != action.get("action_type"):
                        continue
                    if nested_transition.get("target") != target:
                        continue
                    observation = nested_transition.get("observation", {})
                    signals.extend(observation.get("discovered_objects", []))
                    nested_identity = nested_transition.get("update_identities", {}).get(role, {})
                    for nested_action in nested_identity.get("available_actions", []):
                        nested_target = nested_action.get("target")
                        nested_params = nested_action.get("parameters", {})
                        if nested_action.get("action_type") == "access_resource" and nested_target:
                            signals.append(nested_target)
                        if nested_action.get("action_type") == "analyze" and nested_target:
                            for analyze_transition in fixture_transitions:
                                if analyze_transition.get("actor") != role:
                                    continue
                                if analyze_transition.get("action_type") != "analyze":
                                    continue
                                if analyze_transition.get("target") != nested_target:
                                    continue
                                analyze_identity = analyze_transition.get("update_identities", {}).get(
                                    role, {}
                                )
                                for analyze_action in analyze_identity.get("available_actions", []):
                                    analyze_target = analyze_action.get("target")
                                    analyze_params = analyze_action.get("parameters", {})
                                    if (
                                        analyze_action.get("action_type") == "access_resource"
                                        and analyze_target
                                    ):
                                        signals.append(analyze_target)
                                    analyze_bucket = analyze_params.get("bucket")
                                    if analyze_bucket:
                                        signals.append(f"arn:aws:s3:::{analyze_bucket}")
                                    analyze_object_key = analyze_params.get("object_key")
                                    if analyze_object_key:
                                        signals.append(analyze_object_key)
                        nested_object_key = nested_params.get("object_key")
                        if nested_object_key:
                            signals.append(nested_object_key)
        return list(dict.fromkeys(signals))

    def _fixture_transitions(self) -> List[Dict]:
        if hasattr(self._fixture, "fixture") and hasattr(self._fixture.fixture, "data"):
            return self._fixture.fixture.data.get("transitions", [])
        if hasattr(self._fixture, "data"):
            return self._fixture.data.get("transitions", [])
        return []

    def _lookahead_relevance_score(self, role: str) -> int:
        signals = self._lookahead_signals_for_role(role)
        if not signals:
            return 0

        target_tokens, target_bucket, target_key = self._extract_tokens(self._objective.target)
        score = 0
        for signal in signals:
            signal_tokens, bucket, key = self._extract_tokens(signal)
            if key and target_key and key == target_key:
                score += 120
            if bucket and target_bucket and bucket == target_bucket:
                score += 90
            score += 12 * len(target_tokens & signal_tokens)
        return score

    def _bucket_mismatch_penalty(self, role: str) -> int:
        objective_bucket = self._parse_s3_arn(self._objective.target)[0]
        if not objective_bucket:
            return 0

        identities = self._fixture.state_copy().get("identities", {})
        actions: List[Dict] = []
        actions.extend(identities.get(role, {}).get("available_actions", []))

        for transition in self._fixture_transitions():
            if transition.get("actor") != role and transition.get("target") != role:
                continue
            actions.extend(transition.get("update_identities", {}).get(role, {}).get("available_actions", []))

        mismatches = set()
        for action in actions:
            if action.get("action_type") != "access_resource":
                continue
            params = action.get("parameters", {})
            bucket = params.get("bucket")
            if not bucket:
                continue
            target_bucket = None
            target = action.get("target")
            if isinstance(target, str):
                target_bucket = self._parse_s3_arn(target)[0]
            if target_bucket and target_bucket != bucket:
                mismatches.add(("target", bucket, target_bucket))
            if objective_bucket != bucket:
                mismatches.add(("objective", bucket, objective_bucket))

        penalty = 0
        for kind, bucket, reference in mismatches:
            if kind == "target":
                penalty -= 120
            else:
                penalty -= 200
        return penalty

    def _analyze_unlock_bonus(self, role: str) -> int:
        objective_bucket = self._parse_s3_arn(self._objective.target)[0]
        if not objective_bucket:
            return 0
        bonus = 0
        for transition in self._fixture_transitions():
            if transition.get("action_type") != "analyze":
                continue
            if transition.get("actor") != role:
                continue
            target_bucket = self._parse_s3_arn(transition.get("target") or "")[0]
            if target_bucket and target_bucket == objective_bucket:
                bonus += 80
                analyze_identity = transition.get("update_identities", {}).get(role, {})
                for action in analyze_identity.get("available_actions", []):
                    if action.get("action_type") != "access_resource":
                        continue
                    params = action.get("parameters", {})
                    bucket = params.get("bucket")
                    if bucket == objective_bucket:
                        bonus += 120
                        return bonus
        return bonus

    def _extract_tokens(self, value: str) -> tuple[set[str], str | None, str | None]:
        bucket, key = self._parse_s3_arn(value)
        tokens: set[str] = set()
        if bucket:
            tokens.update(token for token in bucket.replace(".", "-").split("-") if token)
        if key:
            name = PurePosixPath(key).name.lower()
            tokens.update(token for token in name.replace(".", "-").split("-") if token)
        if not tokens:
            name = PurePosixPath(value).name.lower()
            tokens.update(token for token in name.replace(".", "-").split("-") if token)
        return tokens, bucket, PurePosixPath(key).name.lower() if key else None

    def _parse_s3_arn(self, value: str) -> tuple[str | None, str | None]:
        if not value.startswith("arn:aws:s3:::"):
            return None, None
        remainder = value.split("arn:aws:s3:::", 1)[1]
        if not remainder:
            return None, None
        if "/" in remainder:
            bucket, key = remainder.split("/", 1)
            return bucket, key
        return remainder, None
