"""Bloco 16.2/16.1 — Gerador combinatório de ambiente sintético (Camada C).

Produz um discovery snapshot VÁLIDO e anotado (mesmas anotações do Bloco 7,
computadas pelo `_compute_capability_graph` real — não faked à mão), pra
exercitar discovery + geração de hipóteses em escala que nenhum lab curado
alcança (todos os fixtures de hoje têm 10–46 recursos).

Determinístico por `seed` — held-out reproduzível. Não toca AWS.

Parametrização por `scale`: número de principals/recursos de cada classe cresce
junto, misturando permissões combinatoriamente pra que readable_by / assumable_by
/ createkey_by / mutable_by tenham densidade real, não um punhado de arestas.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from operations.discovery import _compute_capability_graph  # noqa: E402

ACCOUNT = "123456789012"
REGION = "us-east-1"


def _arn(kind: str, name: str) -> str:
    if kind == "user":
        return f"arn:aws:iam::{ACCOUNT}:user/{name}"
    if kind == "role":
        return f"arn:aws:iam::{ACCOUNT}:role/{name}"
    if kind == "secret":
        return f"arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:{name}"
    if kind == "ssm":
        return f"arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/{name}"
    if kind == "s3obj":
        return f"arn:aws:s3:::{name}"
    raise ValueError(kind)


def generate_environment(scale: int, seed: int = 1337) -> dict:
    """Gera um snapshot com ~ scale principals de cada classe e recursos de dados.

    - n_users = n_roles = n_secrets = scale
    - n_ssm = n_s3 = scale // 2
    Cada user recebe policy_permissions concretas (AssumeRole em k roles,
    GetSecretValue em k secrets, e uma fração recebe CreateAccessKey/AttachRolePolicy).
    Cada role recebe trust_principals reais pra assumable_by resolver de verdade.
    """
    rng = random.Random(seed)
    n_users = scale
    n_roles = scale
    n_secrets = scale
    n_ssm = max(1, scale // 2)
    n_s3 = max(1, scale // 2)

    users = [f"svc-user-{i:04d}" for i in range(n_users)]
    roles = [f"svc-role-{i:04d}" for i in range(n_roles)]
    secrets = [f"prod/app-{i:04d}/creds" for i in range(n_secrets)]
    ssm_params = [f"prod/app-{i:04d}/token" for i in range(n_ssm)]
    s3_objs = [f"data-bucket-{i:04d}/exports/dump.json" for i in range(n_s3)]

    user_arns = [_arn("user", u) for u in users]
    role_arns = [_arn("role", r) for r in roles]
    secret_arns = [_arn("secret", s) for s in secrets]
    ssm_arns = [_arn("ssm", s) for s in ssm_params]
    s3_arns = [_arn("s3obj", s) for s in s3_objs]

    k_assume = 3
    k_read = 3
    resources: list[dict] = []

    # trust_principals por role, preenchido conforme os users ganham AssumeRole
    trust_by_role: dict[str, list[str]] = {r: [] for r in role_arns}

    for uarn in user_arns:
        assume_targets = rng.sample(role_arns, min(k_assume, len(role_arns)))
        for r in assume_targets:
            trust_by_role[r].append(uarn)
        read_secrets = rng.sample(secret_arns, min(k_read, len(secret_arns)))
        read_ssm = rng.sample(ssm_arns, min(k_read, len(ssm_arns))) if ssm_arns else []

        statements = [
            {"Effect": "Allow", "Action": ["sts:AssumeRole"], "Resource": assume_targets},
            {"Effect": "Allow", "Action": ["secretsmanager:GetSecretValue"], "Resource": read_secrets},
        ]
        if read_ssm:
            statements.append({"Effect": "Allow", "Action": ["ssm:GetParameter"], "Resource": read_ssm})
        # 1 em 8 users pode criar access key em outro user (fonte de pivot IAM)
        if rng.random() < 0.125 and len(user_arns) > 1:
            victim = rng.choice([a for a in user_arns if a != uarn])
            statements.append({"Effect": "Allow", "Action": ["iam:CreateAccessKey"], "Resource": [victim]})
        # 1 em 8 pode mutar uma role (privesc IAM direto)
        if rng.random() < 0.125:
            victim_role = rng.choice(role_arns)
            statements.append({"Effect": "Allow", "Action": ["iam:AttachRolePolicy"], "Resource": [victim_role]})

        resources.append({
            "service": "iam",
            "resource_type": "identity.user",
            "identifier": uarn,
            "region": REGION,
            "metadata": {
                "user_name": uarn.split("/")[-1],
                "policy_permissions": [{"source": f"inline:{uarn.split('/')[-1]}-inline", "statements": statements}],
            },
            "source": "synthetic",
        })

    for rarn in role_arns:
        trusted = trust_by_role[rarn]
        # role pode ler alguns secrets também (elo intermediário de chain)
        read_secrets = rng.sample(secret_arns, min(k_read, len(secret_arns)))
        resources.append({
            "service": "iam",
            "resource_type": "identity.role",
            "identifier": rarn,
            "region": REGION,
            "metadata": {
                "role_name": rarn.split("/")[-1],
                "trust_principals": trusted,
                "policy_permissions": [{
                    "source": f"inline:{rarn.split('/')[-1]}-inline",
                    "statements": [
                        {"Effect": "Allow", "Action": ["secretsmanager:GetSecretValue"], "Resource": read_secrets},
                    ],
                }],
            },
            "source": "synthetic",
        })

    for sarn in secret_arns:
        resources.append({
            "service": "secretsmanager", "resource_type": "secret.secrets_manager",
            "identifier": sarn, "region": REGION,
            "metadata": {"name": sarn.split(":secret:")[-1]}, "source": "synthetic",
        })
    for sarn in ssm_arns:
        resources.append({
            "service": "ssm", "resource_type": "secret.ssm_parameter",
            "identifier": sarn, "region": REGION,
            "metadata": {"name": sarn.split(":parameter/")[-1]}, "source": "synthetic",
        })
    for oarn in s3_arns:
        bucket, _, key = oarn.partition("/")
        resources.append({
            "service": "s3", "resource_type": "data_store.s3_object",
            "identifier": oarn, "region": REGION,
            "metadata": {"bucket": bucket, "object_key": key}, "source": "synthetic",
        })

    # Anota com o MESMO código de produção (readable_by / assumable_by / etc)
    _compute_capability_graph(resources)

    return {
        "target": f"synthetic-camada-c-scale-{scale}",
        "bundle": "aws-iam-heavy",
        "caller_identity": {"Account": ACCOUNT, "Arn": user_arns[0]},
        "services_scanned": ["iam", "secretsmanager", "ssm", "s3"],
        "regions_scanned": [REGION],
        "resources": resources,
        "summary": {"resource_count": len(resources)},
    }


def generate_ec2_environment(scale: int, seed: int = 4242) -> dict:
    """Camada C — ambiente com pivot de EC2 instance profile (Bloco 16.3).

    n_instances instâncias, cada uma com um instance profile que concede uma role;
    uma fração dos users tem `ssm:SendCommand` sobre instâncias → compute_pivot.
    Anota via `_compute_capability_graph` real.
    """
    rng = random.Random(seed)
    n_users = scale
    n_instances = scale
    resources: list[dict] = []

    user_arns = [_arn("user", f"ec2-user-{i:04d}") for i in range(n_users)]
    role_arns = [_arn("role", f"ec2-app-role-{i:04d}") for i in range(n_instances)]
    profile_arns = [
        f"arn:aws:iam::{ACCOUNT}:instance-profile/ec2-profile-{i:04d}" for i in range(n_instances)
    ]
    instance_arns = [
        f"arn:aws:ec2:{REGION}:{ACCOUNT}:instance/i-{i:016x}" for i in range(n_instances)
    ]

    # cada user pode rodar comando em k instâncias
    k_cmd = 2
    for uarn in user_arns:
        cmd_targets = rng.sample(instance_arns, min(k_cmd, len(instance_arns)))
        resources.append({
            "service": "iam", "resource_type": "identity.user", "identifier": uarn,
            "region": REGION,
            "metadata": {"user_name": uarn.split("/")[-1], "policy_permissions": [{
                "source": "inline",
                "statements": [{"Effect": "Allow", "Action": ["ssm:SendCommand"], "Resource": cmd_targets}],
            }]},
            "source": "synthetic",
        })

    for i, (rarn, parn, iarn) in enumerate(zip(role_arns, profile_arns, instance_arns)):
        # roles de instância de alto valor em 1 a cada 5 (pra exercitar priorização)
        hv = (i % 5 == 0)
        resources.append({
            "service": "iam", "resource_type": "identity.role", "identifier": rarn,
            "region": REGION,
            "metadata": {"role_name": rarn.split("/")[-1],
                         "is_high_value_target": hv, "privilege_score": 8000 if hv else 100},
            "source": "synthetic",
        })
        resources.append({
            "service": "iam", "resource_type": "compute.instance_profile", "identifier": parn,
            "region": REGION, "metadata": {"role": rarn, "name": parn.split("/")[-1]},
            "source": "synthetic",
        })
        resources.append({
            "service": "ec2", "resource_type": "compute.ec2_instance", "identifier": iarn,
            "region": REGION,
            "metadata": {"instance_id": iarn.split("/")[-1], "instance_profile": parn,
                         "state": "running"},
            "source": "synthetic",
        })

    _compute_capability_graph(resources)
    return {
        "target": f"synthetic-ec2-scale-{scale}",
        "bundle": "aws-advanced",
        "caller_identity": {"Account": ACCOUNT, "Arn": user_arns[0]},
        "services_scanned": ["iam", "ec2", "ssm"],
        "regions_scanned": [REGION],
        "resources": resources,
        "summary": {"resource_count": len(resources)},
    }


def generate_secure_baseline(scale: int, seed: int = 7) -> dict:
    """Camada B — baseline seguro: recursos existem, mas NENHUM caminho de ataque.

    Users só têm permissões inócuas (List/Describe/GetCallerIdentity); roles não
    têm trust pra esses users; secrets não são legíveis por eles. O engine deve
    gerar ZERO hipóteses — mede falso positivo. Anota via código de produção.
    """
    rng = random.Random(seed)
    resources: list[dict] = []
    user_arns = [_arn("user", f"safe-user-{i:04d}") for i in range(scale)]
    role_arns = [_arn("role", f"safe-role-{i:04d}") for i in range(scale)]
    secret_arns = [_arn("secret", f"prod/safe-{i:04d}") for i in range(scale)]

    for uarn in user_arns:
        resources.append({
            "service": "iam", "resource_type": "identity.user", "identifier": uarn,
            "region": REGION,
            "metadata": {"user_name": uarn.split("/")[-1], "policy_permissions": [{
                "source": "inline",
                "statements": [{
                    "Effect": "Allow",
                    "Action": ["s3:ListBucket", "ec2:DescribeInstances", "sts:GetCallerIdentity"],
                    "Resource": "*",
                }],
            }]},
            "source": "synthetic",
        })
    for rarn in role_arns:
        resources.append({
            "service": "iam", "resource_type": "identity.role", "identifier": rarn,
            "region": REGION,
            # trust só pra um serviço AWS, nenhum dos safe-users — não assumível
            "metadata": {"role_name": rarn.split("/")[-1], "trust_principals": [],
                         "policy_permissions": []},
            "source": "synthetic",
        })
    for sarn in secret_arns:
        resources.append({
            "service": "secretsmanager", "resource_type": "secret.secrets_manager",
            "identifier": sarn, "region": REGION,
            "metadata": {"name": sarn.split(":secret:")[-1]}, "source": "synthetic",
        })

    _compute_capability_graph(resources)
    return {
        "target": f"synthetic-secure-baseline-scale-{scale}",
        "bundle": "aws-iam-heavy",
        "caller_identity": {"Account": ACCOUNT, "Arn": user_arns[0]},
        "services_scanned": ["iam", "secretsmanager", "s3", "ec2"],
        "regions_scanned": [REGION],
        "resources": resources,
        "summary": {"resource_count": len(resources)},
    }


if __name__ == "__main__":
    import json
    mode = sys.argv[1] if len(sys.argv) > 1 else "iam"
    scale = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    fn = {"iam": generate_environment, "ec2": generate_ec2_environment,
          "baseline": generate_secure_baseline}[mode]
    print(json.dumps(fn(scale), indent=2))
