"""Bloco 12 — PolicyEvaluator: avaliação determinística de política IAM.

Avalia Action+Resource+Condition contra um conjunto de policy statements,
sem chamar iam:SimulatePrincipalPolicy e sem tocar a conta AWS. Implementa
a regra de precedência real da AWS: Deny explícito em qualquer camada vence
qualquer Allow; ausência de Allow numa camada que exige Allow (identity,
boundary) é negação implícita. SCP é tratado como camada especial — só
contribui Deny, nunca Allow (ver evaluate_effective_access), porque o
baseline real de uma conta é a policy AWS-managed FullAWSAccess (Allow *)
salvo substituição explícita, e este avaliador não resolve a hierarquia de
OUs/root necessária para saber se isso foi substituído.

Escopo desta primeira versão (ver PLAN.md Bloco 12 para o que fica de fora):
  - Action / NotAction, Resource / NotResource, com wildcard completo (* e ?)
  - Condition: StringEquals, StringNotEquals, StringLike, StringNotLike,
    ArnLike, ArnEquals, ArnNotLike, Bool, Null
  - Camadas: identity policy, permission boundary, SCP (deny-only)

Fora do escopo (não finge cobrir — ver `certain=False`/limitações no PLAN.md):
  - resource-based policy (bucket policy, key policy, secret resource policy)
  - hierarquia de OU/root para SCP (só o diretamente anexado à conta)
  - operadores de Condition fora da lista acima (Date*, IpAddress, Numeric*,
    ForAllValues/ForAnyValue, sufixos *IfExists) — um statement cujo Condition
    usa um operador não suportado nunca decide o resultado; a chamada inteira
    volta com certain=False em vez de adivinhar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable


# ---------------------------------------------------------------------------
# Wildcard matching (Action/Resource) — glob completo, não só prefixo/sufixo.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=4096)
def _wildcard_regex(pattern: str) -> re.Pattern:
    escaped = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
    return re.compile(f"^{escaped}$")


def _glob_match(value: str, pattern: str, *, case_insensitive: bool) -> bool:
    if pattern == "*":
        return True
    if case_insensitive:
        value, pattern = value.lower(), pattern.lower()
    return bool(_wildcard_regex(pattern).match(value))


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _statement_matches_action(stmt: dict, action: str) -> bool:
    not_action = stmt.get("NotAction")
    if not_action is not None:
        patterns = _as_list(not_action)
        return not any(_glob_match(action, p, case_insensitive=True) for p in patterns)
    action_field = stmt.get("Action")
    patterns = _as_list(action_field) if action_field is not None else []
    return any(_glob_match(action, p, case_insensitive=True) for p in patterns)


def _statement_matches_resource(stmt: dict, resource_arn: str) -> bool:
    not_resource = stmt.get("NotResource")
    if not_resource is not None:
        patterns = _as_list(not_resource)
        return not any(_glob_match(resource_arn, p, case_insensitive=False) for p in patterns)
    resource_field = stmt.get("Resource", "*")
    patterns = _as_list(resource_field)
    return any(_glob_match(resource_arn, p, case_insensitive=False) for p in patterns)


# ---------------------------------------------------------------------------
# Condition operators — conjunto deliberadamente pequeno (ver docstring).
# ---------------------------------------------------------------------------

def _op_string_equals(actual, expected: list[str]) -> bool:
    return actual is not None and str(actual) in expected


def _op_string_not_equals(actual, expected: list[str]) -> bool:
    return actual is None or str(actual) not in expected


def _op_string_like(actual, expected: list[str]) -> bool:
    return actual is not None and any(_glob_match(str(actual), p, case_insensitive=False) for p in expected)


def _op_string_not_like(actual, expected: list[str]) -> bool:
    return actual is None or not any(_glob_match(str(actual), p, case_insensitive=False) for p in expected)


def _op_arn_like(actual, expected: list[str]) -> bool:
    return actual is not None and any(_glob_match(str(actual), p, case_insensitive=False) for p in expected)


def _op_arn_not_like(actual, expected: list[str]) -> bool:
    return actual is None or not any(_glob_match(str(actual), p, case_insensitive=False) for p in expected)


def _op_bool(actual, expected: list[str]) -> bool:
    if actual is None:
        return False
    return str(actual).lower() in {v.lower() for v in expected}


def _op_null(actual, expected: list[str]) -> bool:
    is_null = actual is None
    expect_null = expected[0].lower() == "true" if expected else True
    return is_null == expect_null


_CONDITION_OPERATORS: dict[str, Callable[[object, list[str]], bool]] = {
    "StringEquals": _op_string_equals,
    "StringNotEquals": _op_string_not_equals,
    "StringLike": _op_string_like,
    "StringNotLike": _op_string_not_like,
    "ArnLike": _op_arn_like,
    "ArnEquals": _op_arn_like,
    "ArnNotLike": _op_arn_not_like,
    "Bool": _op_bool,
    "Null": _op_null,
}


def _condition_matches(condition_block: dict, context: dict) -> tuple[bool, bool]:
    """Retorna (supported, matches).

    supported=False assim que um operador não reconhecido aparece — o statement
    nunca decide o resultado nesse caso (ver evaluate_scope: certain vira False
    globalmente, não importa se o statement seria Allow ou Deny).
    """
    for operator, key_values in condition_block.items():
        handler = _CONDITION_OPERATORS.get(operator)
        if handler is None:
            return False, False
        for key, expected in key_values.items():
            actual = context.get(key)
            if not handler(actual, _as_list(expected)):
                return True, False
    return True, True


# ---------------------------------------------------------------------------
# Avaliação de uma camada (um conjunto de statements — identity, boundary, SCP)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StatementMatch:
    effect: str  # "Allow" | "Deny"
    statement: dict
    source: str


@dataclass(frozen=True)
class ScopeResult:
    decision: str  # "Allow" | "Deny" | "NoMatch"
    matched_statement: StatementMatch | None
    certain: bool


def evaluate_scope(
    statements_list: list[dict],
    action: str,
    resource_arn: str,
    context: dict | None = None,
) -> ScopeResult:
    """Avalia uma única camada (lista de {"source", "statements": [...]})."""
    ctx = context or {}
    deny_match: StatementMatch | None = None
    allow_match: StatementMatch | None = None
    certain = True

    for perm in statements_list:
        source = perm.get("source", "")
        for stmt in perm.get("statements", []):
            effect = stmt.get("Effect", "Allow")
            if effect not in ("Allow", "Deny"):
                continue
            if not _statement_matches_action(stmt, action):
                continue
            if not _statement_matches_resource(stmt, resource_arn):
                continue
            condition_block = stmt.get("Condition")
            if condition_block:
                supported, matches = _condition_matches(condition_block, ctx)
                if not supported:
                    certain = False
                    continue
                if not matches:
                    continue
            match = StatementMatch(effect=effect, statement=stmt, source=source)
            if effect == "Deny" and deny_match is None:
                deny_match = match
            elif effect == "Allow" and allow_match is None:
                allow_match = match

    if deny_match is not None:
        return ScopeResult("Deny", deny_match, certain=certain)
    if allow_match is not None:
        return ScopeResult("Allow", allow_match, certain=certain)
    return ScopeResult("NoMatch", None, certain=certain)


# ---------------------------------------------------------------------------
# Avaliação combinada (identity + boundary + SCP)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EffectiveAccessResult:
    allowed: bool
    certain: bool
    reason: str
    identity_result: ScopeResult
    boundary_result: ScopeResult | None
    scp_deny: StatementMatch | None


def evaluate_effective_access(
    *,
    identity_statements: list[dict],
    action: str,
    resource_arn: str,
    context: dict | None = None,
    boundary_statements: list[dict] | None = None,
    scp_statements: list[dict] | None = None,
) -> EffectiveAccessResult:
    """Combina identity policy + boundary (opcional) + SCP (opcional, deny-only).

    boundary_statements=None: boundary não resolvida (ver Bloco 11) ou
    inexistente — não restringe. scp_statements=None: SCP não resolvida
    (governance.scp_visibility != "directly_attached_only") — não restringe,
    nunca lido como "sem SCP".
    """
    ctx = context or {}
    identity_result = evaluate_scope(identity_statements, action, resource_arn, ctx)

    if identity_result.decision == "Deny":
        return EffectiveAccessResult(
            allowed=False,
            certain=identity_result.certain,
            reason=f"Deny explícito na identity policy ({identity_result.matched_statement.source})",
            identity_result=identity_result,
            boundary_result=None,
            scp_deny=None,
        )
    if identity_result.decision != "Allow":
        return EffectiveAccessResult(
            allowed=False,
            certain=identity_result.certain,
            reason="Nenhum Allow na identity policy cobre esta action+resource",
            identity_result=identity_result,
            boundary_result=None,
            scp_deny=None,
        )

    boundary_result: ScopeResult | None = None
    if boundary_statements is not None:
        boundary_result = evaluate_scope(boundary_statements, action, resource_arn, ctx)
        if boundary_result.decision == "Deny":
            return EffectiveAccessResult(
                allowed=False,
                certain=identity_result.certain and boundary_result.certain,
                reason=f"Deny explícito na permission boundary ({boundary_result.matched_statement.source})",
                identity_result=identity_result,
                boundary_result=boundary_result,
                scp_deny=None,
            )
        if boundary_result.decision != "Allow":
            return EffectiveAccessResult(
                allowed=False,
                certain=identity_result.certain and boundary_result.certain,
                reason="Permission boundary não cobre esta action+resource (teto atingido)",
                identity_result=identity_result,
                boundary_result=boundary_result,
                scp_deny=None,
            )

    scp_certain = True
    if scp_statements is not None:
        scp_result = evaluate_scope(scp_statements, action, resource_arn, ctx)
        scp_certain = scp_result.certain
        if scp_result.decision == "Deny":
            return EffectiveAccessResult(
                allowed=False,
                certain=identity_result.certain
                and (boundary_result.certain if boundary_result else True)
                and scp_certain,
                reason=f"Deny explícito em SCP ({scp_result.matched_statement.source})",
                identity_result=identity_result,
                boundary_result=boundary_result,
                scp_deny=scp_result.matched_statement,
            )
        # SCP só contribui Deny — ausência de Allow no SCP não bloqueia
        # (ver limitação de baseline no docstring do módulo).

    overall_certain = (
        identity_result.certain
        and (boundary_result.certain if boundary_result else True)
        and scp_certain
    )
    reason = "Allow em identity policy"
    if boundary_result is not None:
        reason += " + boundary"
    reason += ", sem Deny aplicável"
    return EffectiveAccessResult(
        allowed=True,
        certain=overall_certain,
        reason=reason,
        identity_result=identity_result,
        boundary_result=boundary_result,
        scp_deny=None,
    )
