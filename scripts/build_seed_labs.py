"""Fase de labs — builder reprodutível dos labs semente.

Constrói os recursos crus, roda a anotação REAL de discovery
(`_compute_capability_graph`) e grava, por lab: `env.discovery.json` (o que a
discovery produziria) + `lab.yaml` (metadata) + `ground_truth.json` (verdade
INDEPENDENTE, escrita da intenção do ambiente — nunca da saída do engine).

O suite semente inclui de propósito um lab de DESAFIO que o engine ERRA hoje
(chain multi-hop: o BFS é single-level, não re-atravessa role assumida), pra o
scorer provar que reporta o miss em vez de mascarar.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from operations.discovery import _compute_capability_graph  # noqa: E402

ACCT = "123456789012"
REGION = "us-east-1"
LABS = Path(__file__).resolve().parents[1] / "labs"


def _u(n):
    return f"arn:aws:iam::{ACCT}:user/{n}"


def _r(n):
    return f"arn:aws:iam::{ACCT}:role/{n}"


def _allow(actions, res):
    return {"Effect": "Allow", "Action": actions, "Resource": res}


def _snapshot(name, resources, governance=None):
    _compute_capability_graph(resources)
    snap = {
        "target": name, "bundle": "aws-iam-heavy",
        "caller_identity": {"Account": ACCT, "Arn": resources[0]["identifier"]},
        "services_scanned": ["iam", "secretsmanager", "ec2", "lambda"],
        "regions_scanned": [REGION], "resources": resources,
        "summary": {"resource_count": len(resources)},
    }
    if governance is not None:
        snap["governance"] = governance
    return snap


def _write(name, meta, snapshot, true_paths):
    d = LABS / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "lab.yaml").write_text(
        "\n".join(f"{k}: {json.dumps(v) if isinstance(v, (bool, list)) else v}"
                  for k, v in meta.items()) + "\n")
    (d / "env.discovery.json").write_text(json.dumps(snapshot, indent=2))
    (d / "ground_truth.json").write_text(json.dumps({"lab": name, "true_paths": true_paths}, indent=2))
    print(f"  escrito labs/{name}/ ({len(snapshot['resources'])} recursos, {len(true_paths)} caminhos verdadeiros)")


def build_neg_secure_baseline():
    # Camada B — controle negativo: recursos existem, nenhum caminho de ataque.
    resources = []
    for i in range(4):
        resources.append({"resource_type": "identity.user", "identifier": _u(f"safe-{i}"),
                          "metadata": {"policy_permissions": [{"source": "i", "statements": [
                              _allow(["s3:ListBucket", "ec2:DescribeInstances"], "*")]}]}})
    for i in range(3):
        resources.append({"resource_type": "identity.role", "identifier": _r(f"svc-{i}"),
                          "metadata": {"trust_principals": [], "policy_permissions": []}})
    _write("neg_secure_baseline",
           {"name": "neg_secure_baseline", "layer": "B", "held_out": False, "challenge": False,
            "description": "Baseline seguro — resposta certa e zero achado (mede falso positivo)."},
           _snapshot("neg_secure_baseline", resources), [])


def build_pos_ec2_ssm_pivot():
    user, role = _u("ops"), _r("app-role")
    prof = f"arn:aws:iam::{ACCT}:instance-profile/app-profile"
    inst = f"arn:aws:ec2:{REGION}:{ACCT}:instance/i-0abc"
    resources = [
        {"resource_type": "identity.user", "identifier": user, "metadata": {"policy_permissions": [
            {"source": "i", "statements": [_allow(["ssm:SendCommand"], [inst])]}]}},
        {"resource_type": "identity.role", "identifier": role, "metadata": {}},
        {"resource_type": "compute.instance_profile", "identifier": prof, "metadata": {"role": role}},
        {"resource_type": "compute.ec2_instance", "identifier": inst, "metadata": {"instance_profile": prof}},
    ]
    _write("pos_ec2_ssm_pivot",
           {"name": "pos_ec2_ssm_pivot", "layer": "C", "held_out": False, "challenge": False,
            "description": "EC2 compute pivot em-cobertura — o engine DEVE achar."},
           _snapshot("pos_ec2_ssm_pivot", resources),
           [{"id": "ec2_pivot", "entry": user, "target": role, "class": "compute_pivot",
             "in_coverage": True, "note": "ssm:SendCommand → role do instance profile"}])


def build_pos_lambda_env_pivot():
    user, role = _u("dev"), _r("exec-role")
    fn = f"arn:aws:lambda:{REGION}:{ACCT}:function:worker"
    resources = [
        {"resource_type": "identity.user", "identifier": user, "metadata": {"policy_permissions": [
            {"source": "i", "statements": [_allow(["lambda:GetFunctionConfiguration"], [fn])]}]}},
        {"resource_type": "identity.role", "identifier": role, "metadata": {}},
        {"resource_type": "compute.lambda_function", "identifier": fn,
         "metadata": {"name": "worker", "execution_role": role}},
    ]
    _write("pos_lambda_env_pivot",
           {"name": "pos_lambda_env_pivot", "layer": "C", "held_out": False, "challenge": False,
            "description": "Lambda env-var pivot em-cobertura — o engine DEVE achar."},
           _snapshot("pos_lambda_env_pivot", resources),
           [{"id": "lambda_pivot", "entry": user, "target": role, "class": "lambda_pivot",
             "in_coverage": True}])


def build_challenge_multihop_chain():
    # DESAFIO: user → R1 (assumível), R1 → R2 (assumível). user NÃO assume R2 direto.
    # O BFS do engine é single-level (nunca re-atravessa role assumida) → acha
    # user→R1, ERRA user→R2. Miss ESPERADO e registrado (in_coverage: false).
    user, r1, r2 = _u("chain-entry"), _r("hop1-role"), _r("hop2-admin")
    resources = [
        {"resource_type": "identity.user", "identifier": user, "metadata": {"policy_permissions": [
            {"source": "i", "statements": [_allow(["sts:AssumeRole"], [r1])]}]}},
        {"resource_type": "identity.role", "identifier": r1, "metadata": {
            "trust_principals": [user],
            "policy_permissions": [{"source": "i", "statements": [_allow(["sts:AssumeRole"], [r2])]}]}},
        {"resource_type": "identity.role", "identifier": r2, "metadata": {
            "trust_principals": [r1], "policy_permissions": []}},
    ]
    _write("challenge_multihop_chain",
           {"name": "challenge_multihop_chain", "layer": "C", "held_out": False, "challenge": True,
            "description": "Chain de 2 hops de role. Desafia o BFS single-level do engine."},
           _snapshot("challenge_multihop_chain", resources),
           [{"id": "hop1", "entry": user, "target": r1, "class": "role_chain",
             "in_coverage": True, "note": "assume direto"},
            {"id": "hop2", "entry": user, "target": r2, "class": "role_chain_multihop",
             "in_coverage": True,
             "note": "coberto desde o fix multi-level do BFS (fase de labs, 2026-08-06)"}])


def build_challenge_role_then_read():
    # DESAFIO: user → R1 (assumível); R1 pode ler secret S; user NÃO pode ler S.
    # BFS single-level erra: R1 nunca é atravessada, então o acesso a S via R1 some.
    user, r1 = _u("rtr-entry"), _r("rtr-role")
    secret = f"arn:aws:secretsmanager:{REGION}:{ACCT}:secret:prod/db-creds"
    resources = [
        {"resource_type": "identity.user", "identifier": user, "metadata": {"policy_permissions": [
            {"source": "i", "statements": [_allow(["sts:AssumeRole"], [r1])]}]}},
        {"resource_type": "identity.role", "identifier": r1, "metadata": {
            "trust_principals": [user],
            "policy_permissions": [{"source": "i", "statements": [
                _allow(["secretsmanager:GetSecretValue"], [secret])]}]}},
        {"resource_type": "secret.secrets_manager", "identifier": secret, "metadata": {"name": "prod/db-creds"}},
    ]
    _write("challenge_role_then_read",
           {"name": "challenge_role_then_read", "layer": "C", "held_out": False, "challenge": True,
            "description": "Assume role e depois ler secret com ela. Desafia o BFS single-level."},
           _snapshot("challenge_role_then_read", resources),
           [{"id": "assume", "entry": user, "target": r1, "class": "role_chain", "in_coverage": True},
            {"id": "read_via_role", "entry": user, "target": secret, "class": "credential_access_via_role",
             "in_coverage": True,
             "note": "coberto desde o fix multi-level do BFS (fase de labs, 2026-08-06)"}])


def build_challenge_cross_account():
    # DESAFIO GENUINAMENTE FORA DE COBERTURA (não some com multi-level): role em
    # OUTRA conta confia o user. Discovery é single-account → a role da conta B nem
    # aparece no snapshot, então nenhuma aresta é gerada. Fica como plant permanente.
    user = _u("xacct-user")
    role_b = "arn:aws:iam::999888777666:role/partner-admin"
    resources = [
        {"resource_type": "identity.user", "identifier": user, "metadata": {"policy_permissions": [
            {"source": "i", "statements": [_allow(["sts:AssumeRole"], [role_b])]}]}},
        # a role_b NÃO está no snapshot (outra conta, discovery não enumerou)
    ]
    _write("challenge_cross_account",
           {"name": "challenge_cross_account", "layer": "C", "held_out": False, "challenge": True,
            "description": "Assume role cross-account. Discovery single-account não vê a role alvo."},
           _snapshot("challenge_cross_account", resources),
           [{"id": "xacct", "entry": user, "target": role_b, "class": "cross_account_role_chain",
             "in_coverage": False,
             "limitation": "discovery single-account: a role da conta B não está no snapshot, sem aresta"}])


def build_challenge_scp_denied():
    # DESAFIO (eixo FALSO POSITIVO, não miss): user→role permitido por
    # permission+trust, MAS uma SCP nega sts:AssumeRole na conta. O caminho real
    # NÃO existe (a AWS bloquearia). O engine é SCP-cego no grafo → gera o
    # role_chain assim mesmo = FP. Declarado em false_paths (FP esperado/conhecido).
    user, role = _u("scp-user"), _r("scp-blocked-admin")
    resources = [
        {"resource_type": "identity.user", "identifier": user, "metadata": {"policy_permissions": [
            {"source": "i", "statements": [_allow(["sts:AssumeRole"], [role])]}]}},
        {"resource_type": "identity.role", "identifier": role, "metadata": {
            "trust_principals": [user], "policy_permissions": []}},
    ]
    governance = {"scp_visibility": "directly_attached_only",
                  "scp_policies": [{"statements": [
                      {"Effect": "Deny", "Action": ["sts:AssumeRole"], "Resource": "*"}]}]}
    d = LABS / "challenge_scp_denied"
    d.mkdir(parents=True, exist_ok=True)
    snap = _snapshot("challenge_scp_denied", resources, governance=governance)
    _write("challenge_scp_denied",
           {"name": "challenge_scp_denied", "layer": "C", "held_out": False, "challenge": True,
            "description": "SCP nega o assume; o engine (SCP-cego no grafo) reporta o caminho = FP conhecido."},
           snap, [])
    # o caminho verdadeiro é vazio; o que o engine gera é um FP ESPERADO, declarado:
    gt = {"lab": "challenge_scp_denied", "true_paths": [],
          "false_paths": [{"entry": user, "target": role, "class": "role_chain",
                           "limitation": "engine SCP-cego no grafo: assumable_by não cruza com SCP Deny, então reporta um caminho que a AWS bloquearia"}]}
    (d / "ground_truth.json").write_text(json.dumps(gt, indent=2))


def build_heldout_ec2_variant():
    # HELD-OUT: nunca usar pra ajustar o engine; medido só na estatística final.
    user, role = _u("ho-ops"), _r("ho-role")
    prof = f"arn:aws:iam::{ACCT}:instance-profile/ho-profile"
    inst = f"arn:aws:ec2:{REGION}:{ACCT}:instance/i-9zzz"
    resources = [
        {"resource_type": "identity.user", "identifier": user, "metadata": {"policy_permissions": [
            {"source": "i", "statements": [_allow(["ssm:StartSession"], [inst])]}]}},
        {"resource_type": "identity.role", "identifier": role, "metadata": {}},
        {"resource_type": "compute.instance_profile", "identifier": prof, "metadata": {"role": role}},
        {"resource_type": "compute.ec2_instance", "identifier": inst, "metadata": {"instance_profile": prof}},
    ]
    _write("heldout_ec2_startsession",
           {"name": "heldout_ec2_startsession", "layer": "C", "held_out": True, "challenge": False,
            "description": "HELD-OUT — variante EC2 via StartSession; não tocar durante o dev."},
           _snapshot("heldout_ec2_startsession", resources),
           [{"id": "ec2_pivot_ss", "entry": user, "target": role, "class": "compute_pivot",
             "in_coverage": True}])


def build_heldout_multihop_4():
    # HELD-OUT: chain de 4 hops (user→R1→R2→R3→R4). Valida que o fix multi-level
    # GENERALIZA (h1-h3, cobertos) E carrega o plant fora-de-cobertura do novo
    # limite: R4 está em depth 4 > max_depth=3, então é perdido de propósito.
    # Nunca tocar pra ajustar o engine.
    user = _u("ho-chain")
    r1, r2, r3, r4 = _r("ho-h1"), _r("ho-h2"), _r("ho-h3"), _r("ho-h4-admin")
    def role(arn, trust, assumes):
        return {"resource_type": "identity.role", "identifier": arn, "metadata": {
            "trust_principals": [trust],
            "policy_permissions": ([{"source": "i", "statements": [_allow(["sts:AssumeRole"], [assumes])]}]
                                   if assumes else [])}}
    resources = [
        {"resource_type": "identity.user", "identifier": user, "metadata": {"policy_permissions": [
            {"source": "i", "statements": [_allow(["sts:AssumeRole"], [r1])]}]}},
        role(r1, user, r2), role(r2, r1, r3), role(r3, r2, r4), role(r4, r3, None),
    ]
    _write("heldout_multihop_4",
           {"name": "heldout_multihop_4", "layer": "C", "held_out": True, "challenge": True,
            "description": "HELD-OUT — chain de 4 hops; valida generalização (h1-h3) + limite max_depth (h4)."},
           _snapshot("heldout_multihop_4", resources),
           [{"id": "h1", "entry": user, "target": r1, "class": "role_chain", "in_coverage": True},
            {"id": "h2", "entry": user, "target": r2, "class": "role_chain", "in_coverage": True},
            {"id": "h3", "entry": user, "target": r3, "class": "role_chain", "in_coverage": True},
            {"id": "h4", "entry": user, "target": r4, "class": "role_chain_4hop", "in_coverage": False,
             "limitation": "max_depth=3: R4 está em depth 4, além do teto de travessia"}])


if __name__ == "__main__":
    LABS.mkdir(exist_ok=True)
    print("construindo labs semente...")
    build_neg_secure_baseline()
    build_pos_ec2_ssm_pivot()
    build_pos_lambda_env_pivot()
    build_challenge_multihop_chain()
    build_challenge_role_then_read()
    build_challenge_cross_account()
    build_challenge_scp_denied()
    build_heldout_ec2_variant()
    build_heldout_multihop_4()
    print("pronto.")
