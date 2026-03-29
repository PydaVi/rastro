from __future__ import annotations

from typing import List

from core.domain import Action, ActionType


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
            return progress_actions

    candidate_paths = getattr(snapshot, "candidate_paths", [])
    if candidate_paths:
        untested_roles = {
            path.target
            for path in candidate_paths
            if getattr(path, "status", "untested") == "untested"
        }
        if untested_roles:
            untested_assume_actions = [
                action
                for action in available_actions
                if action.action_type == ActionType.ASSUME_ROLE
                and action.target in untested_roles
            ]
            if untested_assume_actions:
                return untested_assume_actions

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
        if non_failed_assume_actions:
            return non_failed_assume_actions

    return available_actions
