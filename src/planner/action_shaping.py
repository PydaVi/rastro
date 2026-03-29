from __future__ import annotations

from typing import List

from core.domain import Action, ActionType


def _ranked_candidate_paths(snapshot) -> list:
    candidate_paths = list(getattr(snapshot, "candidate_paths", []))
    return sorted(
        candidate_paths,
        key=lambda path: (-getattr(path, "path_score", 0), path.target),
    )


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
        if ranked_assume_actions:
            return ranked_assume_actions

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
