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
            "allowed_regions": self.scope.allowed_regions,
            "aws_account_ids": self.scope.aws_account_ids,
        }

    def state_copy(self) -> Dict:
        return self.fixture.state_copy()

    def enumerate_actions(self, snapshot):
        actions = self.fixture.enumerate_actions(snapshot)
        return [action for action in actions if self._is_action_allowed(action)]

    def execute(self, action) -> Observation:
        denial = self._build_denied_observation(action)
        if denial is not None:
            return denial

        observation = self.fixture.execute(action)
        details = {
            **observation.details,
            "execution_mode": "dry_run",
            "real_api_called": False,
        }
        return Observation(success=observation.success, details=details)

    def has_flag(self, flag: str) -> bool:
        return self.fixture.has_flag(flag)

    def _is_action_allowed(self, action) -> bool:
        return self._build_denied_observation(action) is None

    def _build_denied_observation(self, action) -> Observation | None:
        service = action.parameters.get("service")
        if service is not None and service not in self.scope.allowed_services:
            return Observation(
                success=False,
                details={
                    "reason": "service_not_allowed",
                    "service": service,
                    "execution_mode": "dry_run",
                    "real_api_called": False,
                },
            )

        region = action.parameters.get("region")
        if region is not None and region not in self.scope.allowed_regions:
            return Observation(
                success=False,
                details={
                    "reason": "region_not_allowed",
                    "region": region,
                    "execution_mode": "dry_run",
                    "real_api_called": False,
                },
            )

        account_id = _extract_account_id(action.actor) or _extract_account_id(action.target)
        if account_id is not None and account_id not in self.scope.aws_account_ids:
            return Observation(
                success=False,
                details={
                    "reason": "account_not_allowed",
                    "account_id": account_id,
                    "execution_mode": "dry_run",
                    "real_api_called": False,
                },
            )

        return None


def _extract_account_id(value: str | None) -> str | None:
    if not value or not value.startswith("arn:aws:"):
        return None
    parts = value.split(":")
    if len(parts) < 5:
        return None
    account_id = parts[4]
    return account_id or None
