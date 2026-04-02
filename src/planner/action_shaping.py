from __future__ import annotations

from typing import List

from core.domain import Action, ActionType


def _ranked_candidate_paths(snapshot) -> list:
    candidate_paths = list(getattr(snapshot, "candidate_paths", []))
    return sorted(
        candidate_paths,
        key=lambda path: (-getattr(path, "path_score", 0), path.target),
    )


def _filter_repeated_access(snapshot, actions: List[Action]) -> List[Action]:
    attempted = {
        (item.get("actor"), item.get("target"))
        for item in getattr(snapshot, "attempted_access_targets", [])
        if item.get("actor") and item.get("target")
    }
    if not attempted:
        return actions
    filtered: List[Action] = []
    for action in actions:
        if action.action_type == ActionType.ACCESS_RESOURCE:
            key = (action.actor, action.target)
            if key in attempted:
                continue
        filtered.append(action)
    return filtered


def _filter_repeated_enumerate(snapshot, actions: List[Action]) -> List[Action]:
    attempted = {
        (item.get("actor"), item.get("target"))
        for item in getattr(snapshot, "attempted_enumerations", [])
        if item.get("actor") and item.get("target")
    }
    if not attempted:
        return actions
    filtered: List[Action] = []
    for action in actions:
        if action.action_type == ActionType.ENUMERATE:
            key = (action.actor, action.target)
            if key in attempted:
                continue
        filtered.append(action)
    return filtered


def _objective_bucket(snapshot) -> str | None:
    target = getattr(getattr(snapshot, "objective", None), "target", None)
    if not target or not target.startswith("arn:aws:s3:::"):
        return None
    remainder = target.split("arn:aws:s3:::", 1)[1]
    if not remainder:
        return None
    return remainder.split("/", 1)[0]


def _filter_mismatched_bucket(snapshot, actions: List[Action]) -> List[Action]:
    objective_bucket = _objective_bucket(snapshot)
    if not objective_bucket:
        return actions
    filtered: List[Action] = []
    for action in actions:
        if action.action_type != ActionType.ACCESS_RESOURCE:
            filtered.append(action)
            continue
        bucket = getattr(action, "parameters", {}).get("bucket")
        if bucket and bucket != objective_bucket:
            continue
        filtered.append(action)
    return filtered


def _filter_repeated_assume(snapshot, actions: List[Action]) -> List[Action]:
    active_roles = set(getattr(snapshot, "active_assumed_roles", []))
    if not active_roles:
        return actions
    filtered: List[Action] = []
    for action in actions:
        if action.action_type == ActionType.ASSUME_ROLE and action.target in active_roles:
            continue
        filtered.append(action)
    return filtered


def _filter_failed_assume(snapshot, actions: List[Action]) -> List[Action]:
    failed_roles = set(getattr(snapshot, "failed_assume_roles", []))
    if not failed_roles:
        return actions
    return [
        action
        for action in actions
        if not (action.action_type == ActionType.ASSUME_ROLE and action.target in failed_roles)
    ]


def _prefer_analyze(snapshot, actions: List[Action]) -> List[Action]:
    if not snapshot or not actions:
        return actions
    # If objective not met and analyze is available in the active branch,
    # prefer analyze to unlock deeper paths before access_resource.
    if getattr(snapshot, "objective_met", False):
        return actions
    analyze_actions = [action for action in actions if action.action_type == ActionType.ANALYZE]
    if analyze_actions:
        return analyze_actions
    return actions


def _prefer_access_on_success(snapshot, actions: List[Action]) -> List[Action]:
    if not snapshot or not actions:
        return actions
    objective_target = getattr(getattr(snapshot, "objective", None), "target", None)
    if not objective_target:
        return actions
    success_actions = [
        action
        for action in actions
        if action.action_type == ActionType.ACCESS_RESOURCE and action.target == objective_target
    ]
    if success_actions:
        return success_actions
    return actions


def shape_available_actions(snapshot, available_actions: List[Action]) -> List[Action]:
    if not snapshot or not available_actions:
        return available_actions

    active_roles = set(getattr(snapshot, "active_assumed_roles", []))
    if active_roles:
        progress_types = {
            ActionType.ENUMERATE,
            ActionType.ACCESS_RESOURCE,
            ActionType.ANALYZE,
        }
        progress_actions = [
            action
            for action in available_actions
            if action.actor in active_roles and action.action_type in progress_types
        ]
        if progress_actions:
            filtered = _filter_repeated_access(snapshot, progress_actions)
            filtered = _filter_repeated_enumerate(snapshot, filtered)
            filtered = _filter_mismatched_bucket(snapshot, filtered)
            filtered = _filter_failed_assume(snapshot, filtered)
            if filtered:
                preferred = _prefer_analyze(snapshot, filtered)
                return _prefer_access_on_success(snapshot, preferred)

    candidate_paths = _ranked_candidate_paths(snapshot)
    if candidate_paths:
        scored_paths = [
            path for path in candidate_paths if getattr(path, "status", "untested") != "failed"
        ]
        ranked_assume_actions = []
        for path in scored_paths:
            ranked_assume_actions.extend(
                [
                    action
                    for action in available_actions
                    if action.action_type == ActionType.ASSUME_ROLE and action.target == path.target
                ]
            )
        ranked_assume_actions = _filter_repeated_assume(snapshot, ranked_assume_actions)
        if ranked_assume_actions:
            return _filter_failed_assume(snapshot, ranked_assume_actions)

        non_failed_assume_actions = [
            action
            for action in available_actions
            if action.action_type == ActionType.ASSUME_ROLE
            and action.target not in {
                path.target
                for path in candidate_paths
                if getattr(path, "status", "untested") == "failed"
            }
        ]
        non_failed_assume_actions = _filter_repeated_assume(snapshot, non_failed_assume_actions)
        if non_failed_assume_actions:
            return _filter_failed_assume(snapshot, non_failed_assume_actions)

    filtered = _filter_repeated_assume(snapshot, available_actions)
    filtered = _filter_repeated_enumerate(snapshot, filtered)
    return _filter_failed_assume(snapshot, filtered)
