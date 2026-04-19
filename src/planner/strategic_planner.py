from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field

from core.domain import Scope


class AttackHypothesis(BaseModel):
    entry_identity: str
    target: str
    attack_class: Literal[
        "iam_privesc",
        "role_chain",
        "credential_access",
        "credential_access_direct",  # entry identity reads secret/SSM without role chain
        "credential_pivot",          # entry reads secret → extracted identity assumes role
        "data_exfil",
        "compute_pivot",
    ]
    attack_steps: list[str] = Field(min_length=1)
    confidence: Literal["high", "medium", "low"]
    reasoning: str
    intermediate_resource: str | None = None  # Bloco 6c: secret/param ARN used as pivot


class StrategicPlanner(ABC):
    @abstractmethod
    def plan_attacks(
        self,
        discovery_snapshot: dict,
        entry_identities: list[str],
        scope: Scope,
    ) -> list[AttackHypothesis]:
        """
        Raciocina sobre o discovery e retorna hipóteses de ataque.

        Contrato:
        - Nunca lança exceção por conteúdo inválido — retorna [] se nada pode ser inferido.
        - Output é sempre list[AttackHypothesis] validada pelo Pydantic.
        - entry_identities restringe os ARNs usados como entry_identity.
        """
