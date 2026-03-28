from __future__ import annotations

from typing import Protocol

from core.domain import Action, Observation


class ExecutionSurface(Protocol):
    def execute(self, action: Action) -> Observation:
        ...


class Executor:
    def __init__(self, surface: ExecutionSurface) -> None:
        self._surface = surface

    def execute(self, action: Action) -> Observation:
        # Only executes simulated transitions inside the configured surface.
        return self._surface.execute(action)
