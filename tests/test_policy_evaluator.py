"""Bloco 12 — testes do PolicyEvaluator.

Arquivo próprio (não tests/test_mvp.py) por decisão deliberada: começar a
quebrar o monólito de testes por domínio em vez de agravar a dívida já
registrada no PLAN.md (Bloco 17). Testes puros, sem AWS, sem discovery —
só a semântica de avaliação de política.
"""
from __future__ import annotations

from core.policy_evaluator import (
    evaluate_scope,
    evaluate_effective_access,
)


def _perm(source: str, statements: list[dict]) -> dict:
    return {"source": source, "statements": statements}


# ---------------------------------------------------------------------------
# Wildcard matching — Action e Resource
# ---------------------------------------------------------------------------

def test_action_exact_match():
    r = evaluate_scope(
        [_perm("p", [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}])],
        "s3:GetObject", "arn:aws:s3:::bucket/key",
    )
    assert r.decision == "Allow"


def test_action_case_insensitive():
    r = evaluate_scope(
        [_perm("p", [{"Effect": "Allow", "Action": "S3:GETOBJECT", "Resource": "*"}])],
        "s3:GetObject", "arn:aws:s3:::bucket/key",
    )
    assert r.decision == "Allow"


def test_action_wildcard_prefix_suffix():
    r = evaluate_scope(
        [_perm("p", [{"Effect": "Allow", "Action": "s3:Get*", "Resource": "*"}])],
        "s3:GetObjectAcl", "arn:aws:s3:::bucket/key",
    )
    assert r.decision == "Allow"


def test_action_wildcard_middle():
    """s3:Get*Object casa com s3:GetBucketObject — glob completo, não só sufixo."""
    r = evaluate_scope(
        [_perm("p", [{"Effect": "Allow", "Action": "s3:Get*Object", "Resource": "*"}])],
        "s3:GetBucketObject", "arn:aws:s3:::bucket/key",
    )
    assert r.decision == "Allow"


def test_action_question_mark_single_char():
    r = evaluate_scope(
        [_perm("p", [{"Effect": "Allow", "Action": "iam:Get?ser", "Resource": "*"}])],
        "iam:GetUser", "arn:aws:iam::123:user/x",
    )
    assert r.decision == "Allow"


def test_action_no_match():
    r = evaluate_scope(
        [_perm("p", [{"Effect": "Allow", "Action": "s3:PutObject", "Resource": "*"}])],
        "s3:GetObject", "arn:aws:s3:::bucket/key",
    )
    assert r.decision == "NoMatch"


def test_not_action_excludes_listed_actions():
    r = evaluate_scope(
        [_perm("p", [{"Effect": "Allow", "NotAction": "iam:CreateAccessKey", "Resource": "*"}])],
        "iam:CreateAccessKey", "arn:aws:iam::123:user/bot",
    )
    assert r.decision == "NoMatch"


def test_not_action_matches_everything_else():
    r = evaluate_scope(
        [_perm("p", [{"Effect": "Allow", "NotAction": "iam:CreateAccessKey", "Resource": "*"}])],
        "s3:GetObject", "arn:aws:s3:::bucket/key",
    )
    assert r.decision == "Allow"


def test_resource_wildcard_prefix():
    r = evaluate_scope(
        [_perm("p", [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::bucket/*"}])],
        "s3:GetObject", "arn:aws:s3:::bucket/prefix/key.json",
    )
    assert r.decision == "Allow"


def test_resource_no_match():
    r = evaluate_scope(
        [_perm("p", [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::other-bucket/*"}])],
        "s3:GetObject", "arn:aws:s3:::bucket/key",
    )
    assert r.decision == "NoMatch"


def test_not_resource_excludes_listed_resource():
    r = evaluate_scope(
        [_perm("p", [{
            "Effect": "Allow", "Action": "s3:GetObject",
            "NotResource": "arn:aws:s3:::secret-bucket/*",
        }])],
        "s3:GetObject", "arn:aws:s3:::secret-bucket/key",
    )
    assert r.decision == "NoMatch"


def test_resource_case_sensitive():
    """Resource ARN, ao contrário de Action, é case-sensitive."""
    r = evaluate_scope(
        [_perm("p", [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::Bucket/Key"}])],
        "s3:GetObject", "arn:aws:s3:::bucket/key",
    )
    assert r.decision == "NoMatch"


# ---------------------------------------------------------------------------
# Deny explícito vence Allow (mesma camada)
# ---------------------------------------------------------------------------

def test_deny_beats_allow_same_scope():
    r = evaluate_scope(
        [_perm("p", [
            {"Effect": "Allow", "Action": "iam:*", "Resource": "*"},
            {"Effect": "Deny", "Action": "iam:CreateAccessKey", "Resource": "*"},
        ])],
        "iam:CreateAccessKey", "arn:aws:iam::123:user/bot",
    )
    assert r.decision == "Deny"


def test_deny_scoped_does_not_affect_other_resource():
    statements = [_perm("p", [
        {"Effect": "Allow", "Action": "iam:*", "Resource": "*"},
        {"Effect": "Deny", "Action": "iam:CreateAccessKey", "Resource": "arn:aws:iam::123:user/bot"},
    ])]
    assert evaluate_scope(statements, "iam:CreateAccessKey", "arn:aws:iam::123:user/bot").decision == "Deny"
    assert evaluate_scope(statements, "iam:CreateAccessKey", "arn:aws:iam::123:user/other").decision == "Allow"


# ---------------------------------------------------------------------------
# Condition operators
# ---------------------------------------------------------------------------

def test_condition_string_equals_satisfied():
    stmt = {
        "Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*",
        "Condition": {"StringEquals": {"aws:PrincipalOrgID": "o-123"}},
    }
    r = evaluate_scope([_perm("p", [stmt])], "sts:AssumeRole", "arn:x", context={"aws:PrincipalOrgID": "o-123"})
    assert r.decision == "Allow"
    assert r.certain


def test_condition_string_equals_not_satisfied():
    stmt = {
        "Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*",
        "Condition": {"StringEquals": {"aws:PrincipalOrgID": "o-123"}},
    }
    r = evaluate_scope([_perm("p", [stmt])], "sts:AssumeRole", "arn:x", context={"aws:PrincipalOrgID": "o-999"})
    assert r.decision == "NoMatch"
    assert r.certain


def test_condition_missing_context_key_fails_string_equals():
    stmt = {
        "Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*",
        "Condition": {"StringEquals": {"aws:PrincipalOrgID": "o-123"}},
    }
    r = evaluate_scope([_perm("p", [stmt])], "sts:AssumeRole", "arn:x", context={})
    assert r.decision == "NoMatch"
    assert r.certain


def test_condition_string_like():
    stmt = {
        "Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*",
        "Condition": {"StringLike": {"aws:userid": "AIDA*"}},
    }
    r = evaluate_scope([_perm("p", [stmt])], "sts:AssumeRole", "arn:x", context={"aws:userid": "AIDA123XYZ"})
    assert r.decision == "Allow"


def test_condition_arn_like():
    stmt = {
        "Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*",
        "Condition": {"ArnLike": {"aws:PrincipalArn": "arn:aws:iam::123:role/broker-*"}},
    }
    r = evaluate_scope(
        [_perm("p", [stmt])], "sts:AssumeRole", "arn:x",
        context={"aws:PrincipalArn": "arn:aws:iam::123:role/broker-prod"},
    )
    assert r.decision == "Allow"


def test_condition_bool():
    stmt = {
        "Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*",
        "Condition": {"Bool": {"aws:MultiFactorAuthPresent": "true"}},
    }
    assert evaluate_scope([_perm("p", [stmt])], "sts:AssumeRole", "arn:x", context={"aws:MultiFactorAuthPresent": "true"}).decision == "Allow"
    assert evaluate_scope([_perm("p", [stmt])], "sts:AssumeRole", "arn:x", context={"aws:MultiFactorAuthPresent": "false"}).decision == "NoMatch"


def test_condition_null_key_absent():
    stmt = {
        "Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*",
        "Condition": {"Null": {"aws:TokenIssueTime": "true"}},
    }
    r = evaluate_scope([_perm("p", [stmt])], "sts:AssumeRole", "arn:x", context={})
    assert r.decision == "Allow"


def test_condition_unsupported_operator_never_decides_and_marks_uncertain():
    """DateGreaterThan não é suportado — o statement nunca decide, e certain vira False."""
    stmt = {
        "Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*",
        "Condition": {"DateGreaterThan": {"aws:CurrentTime": "2026-01-01T00:00:00Z"}},
    }
    r = evaluate_scope([_perm("p", [stmt])], "sts:AssumeRole", "arn:x", context={})
    assert r.decision == "NoMatch"
    assert not r.certain


def test_condition_unsupported_operator_on_deny_marks_uncertain_not_silently_ignored():
    """Um Deny com condition não suportada nao decide Deny, mas tambem nao vira Allow confiante."""
    stmt_allow = {"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*"}
    stmt_deny_unsupported = {
        "Effect": "Deny", "Action": "sts:AssumeRole", "Resource": "*",
        "Condition": {"IpAddress": {"aws:SourceIp": "10.0.0.0/8"}},
    }
    r = evaluate_scope([_perm("p", [stmt_allow, stmt_deny_unsupported])], "sts:AssumeRole", "arn:x", context={})
    assert r.decision == "Allow"
    assert not r.certain  # nao deve ser tratado com a mesma confianca de um Allow limpo


# ---------------------------------------------------------------------------
# evaluate_effective_access — combinação de camadas
# ---------------------------------------------------------------------------

def test_effective_access_allowed_no_boundary_no_scp():
    result = evaluate_effective_access(
        identity_statements=[_perm("p", [{"Effect": "Allow", "Action": "iam:CreateAccessKey", "Resource": "*"}])],
        action="iam:CreateAccessKey", resource_arn="arn:aws:iam::123:user/bot",
    )
    assert result.allowed
    assert result.certain


def test_effective_access_denied_no_identity_allow():
    result = evaluate_effective_access(
        identity_statements=[],
        action="iam:CreateAccessKey", resource_arn="arn:aws:iam::123:user/bot",
    )
    assert not result.allowed


def test_effective_access_identity_deny_wins():
    result = evaluate_effective_access(
        identity_statements=[_perm("p", [
            {"Effect": "Allow", "Action": "iam:*", "Resource": "*"},
            {"Effect": "Deny", "Action": "iam:CreateAccessKey", "Resource": "*"},
        ])],
        action="iam:CreateAccessKey", resource_arn="arn:aws:iam::123:user/bot",
    )
    assert not result.allowed
    assert "identity policy" in result.reason


def test_effective_access_boundary_unresolved_none_does_not_restrict():
    result = evaluate_effective_access(
        identity_statements=[_perm("p", [{"Effect": "Allow", "Action": "iam:CreateAccessKey", "Resource": "*"}])],
        action="iam:CreateAccessKey", resource_arn="arn:aws:iam::123:user/bot",
        boundary_statements=None,
    )
    assert result.allowed


def test_effective_access_boundary_caps_permission():
    result = evaluate_effective_access(
        identity_statements=[_perm("p", [{"Effect": "Allow", "Action": "iam:CreateAccessKey", "Resource": "*"}])],
        action="iam:CreateAccessKey", resource_arn="arn:aws:iam::123:user/bot",
        boundary_statements=[_perm("b", [{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}])],
    )
    assert not result.allowed
    assert "boundary" in result.reason


def test_effective_access_boundary_explicit_deny_wins():
    result = evaluate_effective_access(
        identity_statements=[_perm("p", [{"Effect": "Allow", "Action": "iam:CreateAccessKey", "Resource": "*"}])],
        action="iam:CreateAccessKey", resource_arn="arn:aws:iam::123:user/bot",
        boundary_statements=[_perm("b", [
            {"Effect": "Allow", "Action": "iam:*", "Resource": "*"},
            {"Effect": "Deny", "Action": "iam:CreateAccessKey", "Resource": "*"},
        ])],
    )
    assert not result.allowed


def test_effective_access_scp_unresolved_none_does_not_restrict():
    result = evaluate_effective_access(
        identity_statements=[_perm("p", [{"Effect": "Allow", "Action": "iam:CreateAccessKey", "Resource": "*"}])],
        action="iam:CreateAccessKey", resource_arn="arn:aws:iam::123:user/bot",
        scp_statements=None,
    )
    assert result.allowed


def test_effective_access_scp_explicit_deny_wins():
    result = evaluate_effective_access(
        identity_statements=[_perm("p", [{"Effect": "Allow", "Action": "iam:CreateAccessKey", "Resource": "*"}])],
        action="iam:CreateAccessKey", resource_arn="arn:aws:iam::123:user/bot",
        scp_statements=[_perm("scp:guardrail", [{"Effect": "Deny", "Action": "iam:CreateAccessKey", "Resource": "*"}])],
    )
    assert not result.allowed
    assert result.scp_deny is not None


def test_effective_access_scp_without_allow_does_not_block():
    """SCP só com uma guardrail de Deny p/ outra action (sem Allow-all explícito) não bloqueia
    a action avaliada — SCP é deny-only neste avaliador (ver docstring do módulo)."""
    result = evaluate_effective_access(
        identity_statements=[_perm("p", [{"Effect": "Allow", "Action": "iam:CreateAccessKey", "Resource": "*"}])],
        action="iam:CreateAccessKey", resource_arn="arn:aws:iam::123:user/bot",
        scp_statements=[_perm("scp:guardrail", [
            {"Effect": "Deny", "Action": "organizations:LeaveOrganization", "Resource": "*"},
        ])],
    )
    assert result.allowed


def test_effective_access_all_layers_allow():
    result = evaluate_effective_access(
        identity_statements=[_perm("p", [{"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*"}])],
        action="sts:AssumeRole", resource_arn="arn:aws:iam::123:role/ops",
        boundary_statements=[_perm("b", [{"Effect": "Allow", "Action": "sts:*", "Resource": "*"}])],
        scp_statements=[_perm("scp:base", [{"Effect": "Allow", "Action": "*", "Resource": "*"}])],
    )
    assert result.allowed
    assert result.certain


def test_effective_access_certain_false_propagates_from_identity_layer():
    result = evaluate_effective_access(
        identity_statements=[_perm("p", [
            {"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*"},
            {
                "Effect": "Deny", "Action": "sts:AssumeRole", "Resource": "*",
                "Condition": {"IpAddress": {"aws:SourceIp": "10.0.0.0/8"}},
            },
        ])],
        action="sts:AssumeRole", resource_arn="arn:aws:iam::123:role/ops",
    )
    assert result.allowed
    assert not result.certain
