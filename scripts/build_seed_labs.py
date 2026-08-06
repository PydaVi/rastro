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


def _snapshot(name, resources):
    _compute_capability_graph(resources)
    return {
        "target": name, "bundle": "aws-iam-heavy",
        "caller_identity": {"Account": ACCT, "Arn": resources[0]["identifier"]},
        "services_scanned": ["iam", "secretsmanager", "ec2", "lambda"],
        "regions_scanned": [REGION], "resources": resources,
        "summary": {"resource_count": len(resources)},
    }


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
             "in_coverage": True, "note": "assume direto — engine acha"},
            {"id": "hop2", "entry": user, "target": r2, "class": "role_chain_multihop",
             "in_coverage": False,
             "limitation": "BFS single-level: role assumida (R1) não é re-atravessada, então user→R2 via R1 não é gerado"}])


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


if __name__ == "__main__":
    LABS.mkdir(exist_ok=True)
    print("construindo labs semente...")
    build_neg_secure_baseline()
    build_pos_ec2_ssm_pivot()
    build_pos_lambda_env_pivot()
    build_challenge_multihop_chain()
    build_heldout_ec2_variant()
    print("pronto.")
