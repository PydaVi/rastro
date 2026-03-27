from __future__ import annotations

from core.domain import Action, Scope


class ScopeEnforcer:
    def __init__(self, scope: Scope) -> None:
        self._scope = scope

    def validate(self, action: Action) -> bool:
        if action.action_type not in self._scope.allowed_actions:
            return False
        if action.target and action.target not in self._scope.allowed_resources:
            return False
        return True
