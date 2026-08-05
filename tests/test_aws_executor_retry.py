"""Retry de sts:AssumeRole pra InvalidClientTokenId — achado validando o
Bloco 10 contra AWS real (2026-08-05): access key recem-criado por
iam:CreateAccessKey pode nao estar propagado ainda, e o AssumeRole seguinte
falha por alguns segundos mesmo sendo uma credencial valida. Arquivo próprio,
mesma disciplina de test_policy_evaluator.py / test_graph_diff.py.
"""
from __future__ import annotations

import pytest

from core.domain import Action, ActionType, Scope
from execution.aws_executor import AwsRealExecutor, _assume_role_with_retry


class _ClientErrorLike(Exception):
    """Imita botocore.exceptions.ClientError o suficiente pro código de
    retry: um atributo .response no formato {"Error": {"Code": ...}}."""

    def __init__(self, code: str):
        super().__init__(f"An error occurred ({code})")
        self.response = {"Error": {"Code": code}}


class _FakeStsClient:
    """assume_role falha N vezes com InvalidClientTokenId, depois sucede."""

    def __init__(self, fail_times: int, error_code: str = "InvalidClientTokenId"):
        self.fail_times = fail_times
        self.error_code = error_code
        self.calls = 0

    def assume_role(self, *, region, role_arn, session_name, credentials=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise _ClientErrorLike(self.error_code)
        return {
            "Credentials": {
                "AccessKeyId": "AKIAFAKE",
                "SecretAccessKey": "fake-secret",
                "SessionToken": "fake-token",
            }
        }

    def get_caller_identity(self, *, region, credentials=None):
        return {"Account": "123456789012", "Arn": f"arn:aws:sts::123456789012:assumed-role/x/y"}


def _scope() -> Scope:
    return Scope.model_validate({
        "target": "aws",
        "allowed_services": ["iam", "sts"],
        "allowed_actions": ["assume_role"],
        "allowed_resources": ["*"],
        "aws_account_ids": ["123456789012"],
        "allowed_regions": ["us-east-1"],
        "authorized_by": "test",
        "authorized_at": "2026-01-01",
        "authorization_document": "docs/auth.pdf",
        "dry_run": False,
    })


# ---------------------------------------------------------------------------
# _assume_role_with_retry (unidade)
# ---------------------------------------------------------------------------

def test_assume_role_retry_succeeds_after_transient_failures(monkeypatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _s: None)
    client = _FakeStsClient(fail_times=2)
    result = _assume_role_with_retry(
        client, region="us-east-1", role_arn="arn:aws:iam::123:role/r",
        session_name="s", credentials=None,
    )
    assert result["Credentials"]["AccessKeyId"] == "AKIAFAKE"
    assert client.calls == 3


def test_assume_role_retry_gives_up_after_max_attempts(monkeypatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _s: None)
    client = _FakeStsClient(fail_times=10)  # sempre falha
    with pytest.raises(_ClientErrorLike):
        _assume_role_with_retry(
            client, region="us-east-1", role_arn="arn:aws:iam::123:role/r",
            session_name="s", credentials=None, max_attempts=3,
        )
    assert client.calls == 3


def test_assume_role_retry_does_not_retry_non_transient_errors(monkeypatch) -> None:
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))
    client = _FakeStsClient(fail_times=10, error_code="AccessDenied")
    with pytest.raises(_ClientErrorLike):
        _assume_role_with_retry(
            client, region="us-east-1", role_arn="arn:aws:iam::123:role/r",
            session_name="s", credentials=None,
        )
    assert client.calls == 1  # sem retry — falha real, nao transitoria
    assert sleep_calls == []


def test_assume_role_retry_succeeds_first_try_without_sleeping(monkeypatch) -> None:
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))
    client = _FakeStsClient(fail_times=0)
    _assume_role_with_retry(
        client, region="us-east-1", role_arn="arn:aws:iam::123:role/r",
        session_name="s", credentials=None,
    )
    assert client.calls == 1
    assert sleep_calls == []


# ---------------------------------------------------------------------------
# integração via AwsRealExecutor._execute_iam_passrole
# ---------------------------------------------------------------------------

def test_execute_iam_passrole_retries_through_full_executor(monkeypatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _s: None)
    client = _FakeStsClient(fail_times=2)
    executor = AwsRealExecutor(fixture=None, scope=_scope(), client=client)
    executor._base_actor_arn = "arn:aws:iam::123:user/entry"  # simula o que execute() faria no step 0
    action = Action(
        action_type=ActionType.ASSUME_ROLE,
        actor="arn:aws:iam::123:user/entry",
        target="arn:aws:iam::123:role/target-role",
        parameters={"service": "iam", "region": "us-east-1", "role_arn": "arn:aws:iam::123:role/target-role"},
        tool="iam_passrole",
    )
    details = executor._execute_iam_passrole(client, action)
    assert details["granted_role"] == "arn:aws:iam::123:role/target-role"
    assert client.calls == 3
