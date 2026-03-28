from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from core.domain import Observation
from core.fixture import Fixture


@dataclass
class AwsDryRunLab:
    fixture: Fixture

    @classmethod
    def from_fixture(cls, fixture: Fixture) -> "AwsDryRunLab":
        return cls(fixture=fixture)

    def metadata(self) -> Dict:
        base = self.fixture.metadata()
        return {
            **base,
            "target": "aws",
            "mode": "dry_run",
        }

    def state_copy(self) -> Dict:
        return self.fixture.state_copy()

    def enumerate_actions(self, snapshot):
        return self.fixture.enumerate_actions(snapshot)

    def execute(self, action) -> Observation:
        observation = self.fixture.execute(action)
        details = {
            **observation.details,
            "execution_mode": "dry_run",
            "real_api_called": False,
        }
        return Observation(success=observation.success, details=details)

    def has_flag(self, flag: str) -> bool:
        return self.fixture.has_flag(flag)
