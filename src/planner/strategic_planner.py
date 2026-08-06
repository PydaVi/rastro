from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field

from core.domain import Scope


class PathStep(BaseModel):
    """Bloco 10: um passo executável do path que o CapabilityGraph atravessou.

    step_type espelha os tipos de aresta do CapabilityGraph (assume/read/
    create_key/mutate); tool é o nome exato do YAML em tools/aws/ que executa
    esse passo — o mesmo nome que o executor e o ToolRegistry já conhecem.
    """
    step_type: Literal["assume", "read", "create_key", "mutate", "compute_pivot"]
    actor: str
    target: str
    tool: str


class AttackHypothesis(BaseModel):
    entry_identity: str
    target: str
    attack_class: Literal[
        "iam_privesc",
        "role_chain",
        "credential_access",
        "credential_access_direct",            # entry identity reads secret/SSM without role chain
        "credential_pivot",                    # entry reads secret → extracted identity assumes role
        "ssm_pivot",                           # entry reads SSM param → extracted identity assumes role
        "s3_pivot",                            # entry reads S3 object → extracted identity assumes role
        "iam_create_access_key_pivot",         # entry calls CreateAccessKey → extracted identity assumes role
        "iam_attach_role_policy_privesc",      # entry calls AttachRolePolicy on role
        "iam_put_role_policy_privesc",         # entry calls PutRolePolicy on role
        "iam_create_policy_version_privesc",   # entry calls CreatePolicyVersion on policy
        "iam_mutation_privesc",                # generic IAM mutation
        "data_exfil",
        "compute_pivot",
    ]
    attack_steps: list[str] = Field(min_length=1)
    confidence: Literal["high", "medium", "low"]
    reasoning: str
    intermediate_resource: str | None = None  # Bloco 6c: secret/param ARN used as pivot
    # Bloco 12: "structural" = achado por BFS sobre readable_by/assumable_by/etc
    # (classes de action, sem checar Condition/NotAction/boundary/SCP linha a linha).
    # "evaluated" = o primeiro passo do path foi confirmado pelo PolicyEvaluator,
    # com certain=True — Action+Resource+Condition avaliados de verdade contra
    # identity+boundary+SCP, não só a classe de action.
    evaluation_tier: Literal["structural", "evaluated"] = "structural"
    # Bloco 10: path executável (vazio quando não mapeável integralmente pra
    # tools existentes — nesse caso o executor cai no dispatch por profile).
    path: list[PathStep] = Field(default_factory=list)


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
