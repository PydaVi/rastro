from __future__ import annotations

from core.domain import Action, Observation
from core.fixture import Fixture


class Executor:
    def __init__(self, fixture: Fixture) -> None:
        self._fixture = fixture

    def execute(self, action: Action) -> Observation:
        # Only executes simulated transitions inside the fixture.
        return self._fixture.execute(action)
