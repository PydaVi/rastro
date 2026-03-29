from __future__ import annotations

from typing import List

from core.domain import Action, ActionType


def shape_available_actions(snapshot, available_actions: List[Action]) -> List[Action]:
    if not snapshot or not available_actions:
        return available_actions

    active_roles = set(getattr(snapshot, "active_assumed_roles", []))
    if not active_roles:
        return available_actions

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

    return available_actions
