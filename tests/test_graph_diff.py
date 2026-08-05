"""Bloco 14 — testes de diff_capability_graphs. Arquivo próprio (não
tests/test_mvp.py), mesma disciplina do test_policy_evaluator.py."""
from __future__ import annotations

from core.capability_graph import CapabilityGraph
from core.graph_diff import diff_capability_graphs


def _snapshot(resources):
    return {"resources": resources}


def _user(arn, **meta):
    return {"resource_type": "identity.user", "identifier": arn, "metadata": meta}


def _role(arn, **meta):
    return {"resource_type": "identity.role", "identifier": arn, "metadata": meta}


def _secret(arn, **meta):
    return {"resource_type": "secret.secrets_manager", "identifier": arn, "metadata": meta}


def test_no_changes_yields_empty_diff():
    user_arn = "arn:aws:iam::123:user/u"
    role_arn = "arn:aws:iam::123:role/r"
    snapshot = _snapshot([_role(role_arn, assumable_by=[user_arn])])
    g1 = CapabilityGraph.build(snapshot)
    g2 = CapabilityGraph.build(snapshot)
    diff = diff_capability_graphs(g1, g2)
    assert not diff.has_changes
    assert diff.added_total == 0
    assert diff.removed_total == 0


def test_new_assume_edge_detected():
    user_arn = "arn:aws:iam::123:user/u"
    role_arn = "arn:aws:iam::123:role/r"
    old = CapabilityGraph.build(_snapshot([_role(role_arn)]))
    new = CapabilityGraph.build(_snapshot([_role(role_arn, assumable_by=[user_arn])]))
    diff = diff_capability_graphs(old, new)
    assert diff.added_can_assume == [(user_arn, role_arn)]
    assert diff.removed_can_assume == []
    assert diff.has_changes


def test_removed_read_edge_detected():
    user_arn = "arn:aws:iam::123:user/u"
    secret_arn = "arn:aws:secretsmanager:us-east-1:123:secret:s"
    old = CapabilityGraph.build(_snapshot([_secret(secret_arn, readable_by=[user_arn])]))
    new = CapabilityGraph.build(_snapshot([_secret(secret_arn, readable_by=[])]))
    diff = diff_capability_graphs(old, new)
    assert diff.removed_can_read == [(user_arn, secret_arn)]
    assert diff.added_can_read == []


def test_mutate_edge_added_and_removed_with_action():
    entry = "arn:aws:iam::123:user/e"
    other = "arn:aws:iam::123:user/o"
    role_arn = "arn:aws:iam::123:role/r"
    old = CapabilityGraph.build(_snapshot([
        _role(role_arn, mutable_by={"iam:AttachRolePolicy": [entry]}),
    ]))
    new = CapabilityGraph.build(_snapshot([
        _role(role_arn, mutable_by={"iam:AttachRolePolicy": [other]}),
    ]))
    diff = diff_capability_graphs(old, new)
    assert diff.removed_can_mutate == [(entry, role_arn, "iam:AttachRolePolicy")]
    assert diff.added_can_mutate == [(other, role_arn, "iam:AttachRolePolicy")]


def test_create_key_edge_diff():
    admin = "arn:aws:iam::123:user/admin"
    bot = "arn:aws:iam::123:user/bot"
    old = CapabilityGraph.build(_snapshot([_user(bot)]))
    new = CapabilityGraph.build(_snapshot([_user(bot, createkey_by=[admin])]))
    diff = diff_capability_graphs(old, new)
    assert diff.added_can_create_key == [(admin, bot)]


def test_mixed_changes_across_edge_types():
    user_arn = "arn:aws:iam::123:user/u"
    role_a = "arn:aws:iam::123:role/a"
    role_b = "arn:aws:iam::123:role/b"
    old = CapabilityGraph.build(_snapshot([
        _role(role_a, assumable_by=[user_arn]),
        _role(role_b),
    ]))
    new = CapabilityGraph.build(_snapshot([
        _role(role_a),
        _role(role_b, assumable_by=[user_arn]),
    ]))
    diff = diff_capability_graphs(old, new)
    assert diff.removed_can_assume == [(user_arn, role_a)]
    assert diff.added_can_assume == [(user_arn, role_b)]
    assert diff.added_total == 1
    assert diff.removed_total == 1
