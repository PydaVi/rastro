from __future__ import annotations

from dataclasses import dataclass

from core.domain import Action, Observation, Scope


@dataclass
class AwsRealExecutorStub:
    scope: Scope

    def execute(self, action: Action) -> Observation:
        return Observation(
            success=False,
            details={
                "reason": "aws_real_execution_not_implemented",
                "target": "aws",
                "execution_mode": "stub",
                "real_api_called": False,
                "service": action.parameters.get("service"),
            },
        )
