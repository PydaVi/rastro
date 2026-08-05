"""Bloco 14 — testes de verify_remediation. Arquivo próprio, mesma disciplina
do test_policy_evaluator.py / test_graph_diff.py."""
from __future__ import annotations

import pytest

from operations.remediation import verify_remediation


def _user(arn, policy_permissions=None, **meta):
    m = dict(meta)
    if policy_permissions is not None:
        m["policy_permissions"] = policy_permissions
    return {"resource_type": "identity.user", "identifier": arn, "metadata": m}


def _role(arn, **meta):
    return {"resource_type": "identity.role", "identifier": arn, "metadata": meta}


def test_remediation_closes_path_with_no_side_effects():
    """Remove sts:AssumeRole do entry -> a aresta fecha e nada mais abre."""
    entry = "arn:aws:iam::123:user/analyst"
    role_arn = "arn:aws:iam::123:role/AdminRole"
    snapshot = {
        "resources": [
            _user(entry, policy_permissions=[{"source": "p", "statements": [
                {"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": role_arn},
            ]}]),
            _role(role_arn),
        ],
    }
    result = verify_remediation(
        snapshot, target_principal=entry, proposed_policy_permissions=[],
    )
    assert result.closed_edges_from_principal == 1
    assert result.newly_opened_edges == 0
    assert result.remediation_effective
    assert (entry, role_arn) in result.diff.removed_can_assume


def test_remediation_reflects_removal_even_when_snapshot_has_stale_precomputed_edges():
    """Mesmo teste acima, mas o snapshot de ENTRADA já vem com assumable_by
    pré-computado (como um discovery.json real) — pega regressão se alguém
    remover o _strip_capability_annotations e o resultado ficar "grudado"."""
    entry = "arn:aws:iam::123:user/analyst"
    role_arn = "arn:aws:iam::123:role/AdminRole"
    snapshot = {
        "resources": [
            _user(entry, policy_permissions=[{"source": "p", "statements": [
                {"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": role_arn},
            ]}]),
            _role(role_arn, assumable_by=[entry], trust_principals=[entry]),
        ],
    }
    result = verify_remediation(
        snapshot, target_principal=entry, proposed_policy_permissions=[],
    )
    assert result.closed_edges_from_principal == 1
    assert result.remediation_effective


def test_remediation_detects_newly_opened_edge():
    """A correcao proposta fecha o alvo mas abre um caminho novo -> nao efetiva."""
    entry = "arn:aws:iam::123:user/analyst"
    role_a = "arn:aws:iam::123:role/A"
    role_b = "arn:aws:iam::123:role/B"
    snapshot = {
        "resources": [
            _user(entry, policy_permissions=[{"source": "p", "statements": [
                {"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": role_a},
            ]}]),
            _role(role_a),
            _role(role_b),
        ],
    }
    # "correcao" troca o Resource especifico por um wildcard mais amplo — fecha
    # role_a? nao, continua cobrindo. Vamos forcar o caso real: fecha role_a,
    # mas o autor errou e deixou um wildcard que agora tambem cobre role_b.
    proposed = [{"source": "p2", "statements": [
        {"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*"},
    ]}]
    result = verify_remediation(
        snapshot, target_principal=entry, proposed_policy_permissions=proposed,
    )
    assert result.newly_opened_edges >= 1
    assert (entry, role_b) in result.diff.added_can_assume
    assert not result.remediation_effective


def test_remediation_no_change_is_not_effective():
    entry = "arn:aws:iam::123:user/analyst"
    role_arn = "arn:aws:iam::123:role/AdminRole"
    statements = [{"source": "p", "statements": [
        {"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": role_arn},
    ]}]
    snapshot = {"resources": [_user(entry, policy_permissions=statements), _role(role_arn)]}
    result = verify_remediation(
        snapshot, target_principal=entry, proposed_policy_permissions=statements,
    )
    assert result.closed_edges_from_principal == 0
    assert result.newly_opened_edges == 0
    assert not result.remediation_effective
    assert not result.diff.has_changes


def test_remediation_unknown_principal_raises():
    snapshot = {"resources": [_role("arn:aws:iam::123:role/r")]}
    with pytest.raises(ValueError):
        verify_remediation(
            snapshot,
            target_principal="arn:aws:iam::123:user/nao-existe",
            proposed_policy_permissions=[],
        )


def test_remediation_real_lab_scenario_acme_style():
    """Cenario com forma real (achado validando o acme_showcase ao vivo hoje):
    cicd-agent tem AttachRolePolicy sobre ops-role. Proposta remove o Resource
    especifico e nao deixa nada no lugar — fecha sem abrir nada."""
    cicd_agent = "arn:aws:iam::550192603632:user/acme-cicd-agent"
    ops_role = "arn:aws:iam::550192603632:role/acme-ops-role"
    snapshot = {
        "resources": [
            _user(cicd_agent, policy_permissions=[{"source": "inline:acme-cicd-agent-privesc", "statements": [
                {"Effect": "Allow", "Action": ["iam:ListRoles", "sts:GetCallerIdentity"], "Resource": "*"},
                {"Effect": "Allow", "Action": ["iam:AttachRolePolicy", "iam:DetachRolePolicy"], "Resource": [ops_role]},
            ]}]),
            _role(ops_role, mutable_by={"iam:AttachRolePolicy": [cicd_agent]}),
        ],
    }
    proposed = [{"source": "inline:acme-cicd-agent-privesc", "statements": [
        {"Effect": "Allow", "Action": ["iam:ListRoles", "sts:GetCallerIdentity"], "Resource": "*"},
    ]}]
    result = verify_remediation(
        snapshot, target_principal=cicd_agent, proposed_policy_permissions=proposed,
    )
    assert (cicd_agent, ops_role, "iam:AttachRolePolicy") in result.diff.removed_can_mutate
    assert result.remediation_effective
