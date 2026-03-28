from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from core.domain import Observation, Scope
from core.fixture import Fixture


@dataclass
class AwsDryRunLab:
    fixture: Fixture
    scope: Scope

    @classmethod
    def from_fixture(cls, fixture: Fixture, scope: Scope) -> "AwsDryRunLab":
        return cls(fixture=fixture, scope=scope)

    def metadata(self) -> Dict:
        base = self.fixture.metadata()
        return {
            **base,
            "target": "aws",
            "mode": "dry_run",
            "allowed_services": self.scope.allowed_services,
        }

    def state_copy(self) -> Dict:
        return self.fixture.state_copy()

    def enumerate_actions(self, snapshot):
        actions = self.fixture.enumerate_actions(snapshot)
        return [action for action in actions if self._is_service_allowed(action)]

    def execute(self, action) -> Observation:
        if not self._is_service_allowed(action):
            return Observation(
                success=False,
                details={
                    "reason": "service_not_allowed",
                    "service": action.parameters.get("service"),
                    "execution_mode": "dry_run",
                    "real_api_called": False,
                },
            )

        observation = self.fixture.execute(action)
        details = {
            **observation.details,
            "execution_mode": "dry_run",
            "real_api_called": False,
        }
        return Observation(success=observation.success, details=details)

    def has_flag(self, flag: str) -> bool:
        return self.fixture.has_flag(flag)

    def _is_service_allowed(self, action) -> bool:
        service = action.parameters.get("service")
        if service is None:
            return True
        return service in self.scope.allowed_services
