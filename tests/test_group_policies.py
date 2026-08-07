"""Fase de labs — permissões herdadas de grupos IAM (falso negativo estrutural).

Antes o discovery coletava só as policies anexadas/inline DO USUÁRIO, nunca as dos
grupos IAM a que ele pertence. Em contas reais, permissão via grupo é prática
padrão — sem isso, um user com acesso só via grupo tinha policy_permissions
incompleto e o engine perdia todas as arestas dele. Este teste trava o fix.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from operations.discovery import _compute_capability_graph, _fetch_group_policy_permissions


class _FakeIam:
    def __init__(self, groups):
        self._groups = groups  # {user: [group,...]}, {group: {"attached":[...], "inline":{name:doc}}}

    def list_groups_for_user(self, region, user_name):
        return self._groups.get("membership", {}).get(user_name, [])

    def list_attached_group_policies(self, region, group_name):
        return self._groups.get(group_name, {}).get("attached", [])

    def list_group_inline_policies(self, region, group_name):
        return list(self._groups.get(group_name, {}).get("inline", {}).keys())

    def get_group_inline_policy(self, region, group_name, policy_name):
        return self._groups.get(group_name, {}).get("inline", {}).get(policy_name)

    def get_policy_default_version(self, region, policy_arn):
        return self._groups.get("managed", {}).get(policy_arn)


def _client():
    return _FakeIam({
        "membership": {"alice": ["developers"]},
        "developers": {
            "attached": [{"PolicyArn": "arn:aws:iam::123:policy/SecretsRead", "PolicyName": "SecretsRead"}],
            "inline": {"assume-inline": {"Statement": [
                {"Effect": "Allow", "Action": ["sts:AssumeRole"], "Resource": "*"}]}},
        },
        "managed": {"arn:aws:iam::123:policy/SecretsRead": {"Statement": [
            {"Effect": "Allow", "Action": ["secretsmanager:GetSecretValue"], "Resource": "*"}]}},
    })


def test_group_attached_and_inline_merged_with_prefixed_source():
    perms = _fetch_group_policy_permissions(aws_client=_client(), region="us-east-1",
                                            user_name="alice", max_policies=5)
    sources = {p["source"] for p in perms}
    assert "group:developers:SecretsRead" in sources
    assert "group:developers:inline:assume-inline" in sources


def test_user_without_group_gets_nothing():
    assert _fetch_group_policy_permissions(aws_client=_client(), region="us-east-1",
                                           user_name="bob", max_policies=5) == []


def test_client_without_group_methods_degrades_to_empty():
    # best-effort: cliente sem os métodos de grupo não quebra
    assert _fetch_group_policy_permissions(aws_client=object(), region="us-east-1",
                                           user_name="alice", max_policies=5) == []


def test_group_inherited_permission_produces_graph_edge():
    # Efeito ponta a ponta: um user cujo ÚNICO acesso vem do grupo (aqui já
    # mesclado no policy_permissions, como o discovery pós-fix produz) gera a
    # aresta readable_by — antes seria um falso negativo total.
    user = "arn:aws:iam::123:user/alice"
    secret = "arn:aws:secretsmanager:us-east-1:123:secret:prod/s"
    group_perm = _fetch_group_policy_permissions(aws_client=_client(), region="us-east-1",
                                                 user_name="alice", max_policies=5)
    resources = [
        {"resource_type": "identity.user", "identifier": user,
         "metadata": {"policy_permissions": group_perm}},  # só o que veio do grupo
        {"resource_type": "secret.secrets_manager", "identifier": secret, "metadata": {}},
    ]
    _compute_capability_graph(resources)
    readable = next(r["metadata"] for r in resources if r["resource_type"] == "secret.secrets_manager").get("readable_by")
    assert readable == [user]
