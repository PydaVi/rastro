from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

from execution.aws_client import AwsClient, Boto3AwsClient
from operations.catalog import resolve_bundle
from operations.models import AuthorizationConfig, TargetConfig
from operations.service import validate_profile_access, validate_target


DEFAULT_SSM_DISCOVERY_PREFIXES = ["/prod", "/app", "/finance", "/shared"]


@dataclass
class DiscoveryLimits:
    max_roles: int = 100
    max_buckets: int = 50
    max_objects_per_bucket: int = 20
    max_secrets: int = 100
    max_parameters_per_prefix: int = 100
    max_policies_per_principal: int = 5


def _is_service_linked_role(role_arn: str) -> bool:
    return ":role/aws-service-role/" in role_arn


# IAM actions that target a ROLE ARN directly (Resource = role ARN)
_ROLE_TARGET_ACTIONS = frozenset({
    "iam:attachrolepolicy",
    "iam:detachrolepolicy",
    "iam:putrolepolicy",
    "iam:updateassumerolepolicy",
    "iam:deleterole",
    "iam:passrole",
    "sts:assumerole",
})

# IAM actions that target a POLICY ARN (Resource = policy ARN) → resolve to role
_POLICY_TARGET_ACTIONS = frozenset({
    "iam:createpolicyversion",
    "iam:setdefaultpolicyversion",
    "iam:deletepolicyversion",
})

# IAM actions that target a USER ARN directly (Resource = user ARN)
_USER_TARGET_ACTIONS = frozenset({
    "iam:createaccesskey",
    "iam:createloginprofile",
    "iam:updateloginprofile",
    "iam:attachuserpolicy",
    "iam:putuserpolicy",
    "iam:deleteaccesskey",
})


def _resolve_target_for_action(
    action: str,
    resource_arns: list[str],
    policy_to_roles: dict[str, list[str]],
) -> str | None:
    """Resolve o target ARN de ataque para uma ação IAM e lista de Resource ARNs."""
    action_lower = action.lower()
    wildcard_action = action_lower in ("iam:*", "*")

    for resource_arn in resource_arns:
        if not resource_arn or resource_arn == "*" or resource_arn.endswith("*"):
            continue

        if action_lower in _ROLE_TARGET_ACTIONS or (wildcard_action and ":role/" in resource_arn):
            if ":role/" in resource_arn:
                return resource_arn

        elif action_lower in _POLICY_TARGET_ACTIONS or (wildcard_action and ":policy/" in resource_arn):
            if ":policy/" in resource_arn:
                roles = policy_to_roles.get(resource_arn, [])
                if roles:
                    return roles[0]

        elif action_lower in _USER_TARGET_ACTIONS or (wildcard_action and ":user/" in resource_arn):
            if ":user/" in resource_arn:
                return resource_arn

    return None


# ---------------------------------------------------------------------------
# Bloco 4c — Privilege Scoring
# ---------------------------------------------------------------------------

# Pesos base por ação. Resource=* aplica multiplicador 2x.
# IMPORTANTE: o prefixo "*" NÃO é usado em prefix-matching (evita false positives).
# Prefix-matching só roda quando a própria ação na policy termina com "*"
# (e.g. iam:Create*, s3:*) — ações específicas (sem *) usam apenas exact-lookup.
_PRIV_ACTION_SCORES: dict[str, int] = {
    # Wildcards exatos — ação literalmente "*" ou "svc:*"
    # iam:* e * valem muito mais que ações individuais: representa TODAS as permissões.
    # Score alto o suficiente para sempre superar combinações de ações específicas.
    "iam:*":                          4000,
    "*":                              4500,   # usado apenas em exact-match, não em prefix
    # IAM mutation — altamente perigosas
    "iam:createpolicyversion":         500,
    "iam:attachrolepolicy":            500,
    "iam:putrolepolicy":               500,
    "iam:updateassumerolepolicy":      450,
    "iam:setdefaultpolicyversion":     400,
    "iam:createaccesskey":             350,
    "iam:passrole":                    350,
    "iam:attachuserpolicy":            350,
    "iam:attachgrouppolicy":           300,
    "iam:addusertogroup":              300,
    "iam:putuserpolicy":               300,
    "iam:createloginprofile":          250,
    "iam:updateloginprofile":          250,
    # IAM mutation wildcard sub-patterns (e.g. policy usa "iam:Create*")
    "iam:create*":                     400,
    "iam:attach*":                     400,
    "iam:put*":                        350,
    "iam:update*":                     300,
    "iam:delete*":                     150,
    # IAM read-only sub-patterns — baixíssimo risco
    "iam:list*":                         5,
    "iam:get*":                          5,
    "iam:describe*":                     0,
    "iam:generate*":                     0,
    "iam:simulate*":                     0,
    # STS
    "sts:assumerole":                  200,
    # Secrets
    "secretsmanager:*":               150,
    "secretsmanager:getsecretvalue":  120,
    # SSM
    "ssm:*":                          120,
    "ssm:getparameter":                80,
    "ssm:getparametersbypath":         80,
    # S3 — wildcard sub-patterns
    "s3:*":                           150,
    "s3:getobject":                    50,
    "s3:putobject":                    40,
    "s3:deleteobject":                 40,
    "s3:get*":                         10,
    "s3:list*":                         5,
    # Compute / data
    "ec2:*":                          100,
    "lambda:*":                       100,
    "glue:*":                         100,
    "sagemaker:*":                    100,
}

_HIGH_VALUE_THRESHOLD = 300


def _score_principal(r: dict) -> int:
    """Score de privilégio de um principal com base em suas policy_permissions.

    Score alto = principal é valioso como alvo de escalonamento (pode causar dano amplo).
    Resource=* dobra o peso de cada ação (permissão irrestrita > permissão específica).
    """
    meta = r.get("metadata") or {}
    score = 0
    for perm in meta.get("policy_permissions", []):
        for stmt in perm.get("statements", []):
            if stmt.get("Effect") != "Allow":
                continue
            actions = stmt.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            resource_field = stmt.get("Resource", "*")
            if isinstance(resource_field, str):
                resource_field = [resource_field]

            is_wildcard = all(ra in ("*",) or ra.endswith("*") for ra in resource_field)
            multiplier = 2.0 if is_wildcard else 1.0

            for action in actions:
                al = action.lower()
                action_score = _PRIV_ACTION_SCORES.get(al, 0)
                if not action_score and al.endswith("*") and al != "*":
                    # Ação na policy é um wildcard sub-pattern (e.g. iam:Create*, s3:*)
                    # Busca o padrão mais específico que contenha este prefixo.
                    # Exclui "*" do matching (prefixo vazio causaria false positives).
                    for pat, ps in _PRIV_ACTION_SCORES.items():
                        if pat != "*" and pat.endswith("*") and al.startswith(pat[:-1]):
                            action_score = max(action_score, ps)
                score += int(action_score * multiplier)

    return min(score, 9999)


def _compute_privilege_scores(resources: list[dict]) -> None:
    """Adiciona privilege_score e is_high_value_target a cada principal no snapshot.

    Chamado ANTES de _derive_attack_targets para que Pass 2 use scores reais
    em vez de heurísticas de naming convention.
    """
    for r in resources:
        if r.get("resource_type") not in ("identity.user", "identity.role"):
            continue
        if not r.get("metadata"):
            r["metadata"] = {}
        score = _score_principal(r)
        r["metadata"]["privilege_score"] = score
        r["metadata"]["is_high_value_target"] = score >= _HIGH_VALUE_THRESHOLD


def _best_role_by_score(
    role_arns: set[str],
    resources: list[dict],
    prefer_arns: list[str] | None = None,
) -> str | None:
    """Retorna o role ARN com maior privilege_score no snapshot.

    Se prefer_arns for fornecida (roles que o user pode assumir via trust),
    prefere candidatos dentro desse conjunto — fallback para qualquer role.
    Retorna None se nenhum role tiver score > 0 (e.g., testes offline).
    """
    score_map: dict[str, int] = {}
    for r in resources:
        if r.get("resource_type") == "identity.role":
            arn = r.get("identifier", "")
            if arn in role_arns:
                score_map[arn] = (r.get("metadata") or {}).get("privilege_score", 0)

    candidates = [(arn, sc) for arn, sc in score_map.items() if sc > 0]
    if not candidates:
        return None

    if prefer_arns:
        preferred = [(arn, sc) for arn, sc in candidates if arn in prefer_arns]
        if preferred:
            return max(preferred, key=lambda x: x[1])[0]

    return max(candidates, key=lambda x: x[1])[0]


def _name_match_role(principal_arn: str, role_arns: set[str]) -> str | None:
    """Fallback heurístico: principal -user → role com mesmo prefixo -role.

    Usado apenas quando privilege_score não está disponível (testes offline,
    discovery sem policy_permissions). Em produção, _best_role_by_score tem precedência.
    """
    name = principal_arn.rsplit("/", 1)[-1]
    if name.endswith("-user"):
        candidate = name[:-5] + "-role"
        for role_arn in role_arns:
            if role_arn.rsplit("/", 1)[-1] == candidate:
                return role_arn
    return None


def _derive_attack_targets(resources: list[dict]) -> None:
    """Pós-processa resources: adiciona derived_attack_targets a users e roles
    com base no Resource field das policy_permissions e trust relationships (determinístico).

    Pass 1 — Resource ARN específico: resolve diretamente (role, policy→role, user).
    Pass 2 — Resource=* com naming convention: user-X-user → busca role X-role no snapshot.
    Pass 3 — Trust inversion: se o user aparece no trust_principals de um role,
              pode assumir esse role (sts:AssumeRole).
    """
    policy_to_roles: dict[str, list[str]] = {}
    role_arns_in_snapshot: set[str] = set()
    # user_arn → [role_arns where user is in trust_principals]
    user_assumable_roles: dict[str, list[str]] = {}

    for r in resources:
        if r.get("resource_type") == "identity.role":
            role_arn = r.get("identifier", "")
            role_arns_in_snapshot.add(role_arn)
            meta = r.get("metadata") or {}
            for policy_arn in meta.get("attached_policy_arns", []):
                policy_to_roles.setdefault(policy_arn, []).append(role_arn)
            for principal in meta.get("trust_principals", []):
                if ":user/" in principal:
                    user_assumable_roles.setdefault(principal, []).append(role_arn)

    _wildcard_privesc_actions = _ROLE_TARGET_ACTIONS | _POLICY_TARGET_ACTIONS | {"iam:*", "*"}

    for r in resources:
        if r.get("resource_type") not in ("identity.user", "identity.role"):
            continue
        meta = r.get("metadata") or {}
        user_arn = r.get("identifier", "")
        policy_permissions = meta.get("policy_permissions", [])

        derived: list[dict] = []
        seen_targets: set[tuple] = set()
        wildcard_privesc_actions: list[str] = []

        # Pass 1 + collect wildcard actions
        for perm in policy_permissions:
            for stmt in perm.get("statements", []):
                if stmt.get("Effect") != "Allow":
                    continue
                actions = stmt.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                resource_field = stmt.get("Resource", "*")
                if isinstance(resource_field, str):
                    resource_field = [resource_field]

                is_wildcard = all(ra == "*" or ra.endswith("*") for ra in resource_field)

                for action in actions:
                    if is_wildcard:
                        if action.lower() in _wildcard_privesc_actions:
                            wildcard_privesc_actions.append(action)
                        continue
                    target_arn = _resolve_target_for_action(action, resource_field, policy_to_roles)
                    if target_arn:
                        key = (action.lower(), target_arn)
                        if key not in seen_targets:
                            seen_targets.add(key)
                            derived.append({"action": action, "target_arn": target_arn})

        # Pass 2: wildcard IAM mutation (Resource=*) → escolhe melhor alvo por score.
        # Roda SEMPRE que há ações de mutação wildcard (independente do Pass 1).
        # sts:AssumeRole wildcard é excluído aqui — tratado no Pass 3 via trust inversion.
        # Prefere roles que o user já pode assumir; fallback para maior score global;
        # último recurso: name-match (lab convention).
        non_sts_wildcard = [a for a in wildcard_privesc_actions if a.lower() != "sts:assumerole"]
        if non_sts_wildcard:
            assumable_here = user_assumable_roles.get(user_arn, [])
            best_role = _best_role_by_score(
                role_arns_in_snapshot, resources, prefer_arns=assumable_here or None
            )
            if best_role is None:
                best_role = _name_match_role(user_arn, role_arns_in_snapshot)
            if best_role:
                for action in non_sts_wildcard:
                    key = (action.lower(), best_role)
                    if key not in seen_targets:
                        seen_targets.add(key)
                        derived.append({"action": action, "target_arn": best_role})

        # Pass 3: trust inversion — roles que listam este user em trust_principals
        assumable = user_assumable_roles.get(user_arn, [])
        for role_arn in assumable:
            key = ("sts:assumerole", role_arn)
            if key not in seen_targets:
                seen_targets.add(key)
                derived.append({"action": "sts:AssumeRole", "target_arn": role_arn})

        if derived:
            meta["derived_attack_targets"] = derived


_RECURSIVE_DAMPEN = 0.5   # cada hop reduz o score herdado à metade


def _apply_recursive_scores(resources: list[dict]) -> None:
    """Propaga privilege_score através de chains de sts:AssumeRole (determinístico).

    Se o principal A pode assumir o principal B, o score efetivo de A é:
        effective(A) = own(A) + DAMPEN * max(effective(B) para cada B assumível por A)

    Usa DFS com detecção de ciclo (frozenset de visitados).
    Chamado DEPOIS de _derive_attack_targets (usa derived_attack_targets como arestas).
    """
    # Mapa arn → resource
    resource_map: dict[str, dict] = {
        r.get("identifier", ""): r
        for r in resources
        if r.get("resource_type") in ("identity.user", "identity.role")
    }

    # Score base já calculado por _compute_privilege_scores
    base_score: dict[str, int] = {
        arn: (r.get("metadata") or {}).get("privilege_score", 0)
        for arn, r in resource_map.items()
    }

    # Grafo de assunção: arn → [role arns que pode assumir via sts:AssumeRole]
    assume_edges: dict[str, list[str]] = {}
    for arn, r in resource_map.items():
        meta = r.get("metadata") or {}
        targets = [
            d["target_arn"]
            for d in meta.get("derived_attack_targets", [])
            if d.get("action", "").lower() == "sts:assumerole"
            and d.get("target_arn", "") in resource_map
        ]
        if targets:
            assume_edges[arn] = targets

    if not assume_edges:
        return  # nada a propagar (testes offline, sem derived_attack_targets)

    # DFS com memoização e detecção de ciclo
    effective: dict[str, int] = {}

    def _compute(arn: str, visiting: frozenset) -> int:
        if arn in effective:
            return effective[arn]
        own = base_score.get(arn, 0)
        reachable = assume_edges.get(arn, [])
        if not reachable:
            effective[arn] = own
            return own
        # evita ciclo: se já estamos visitando, retorna score base
        downstream = [
            _compute(r, visiting | {arn})
            for r in reachable
            if r not in visiting
        ]
        bonus = int(_RECURSIVE_DAMPEN * max(downstream)) if downstream else 0
        result = min(own + bonus, 9999)
        effective[arn] = result
        return result

    for arn in resource_map:
        _compute(arn, frozenset())

    # Atualiza metadata in-place
    for arn, score in effective.items():
        r = resource_map[arn]
        meta = r.get("metadata") or {}
        if not r.get("metadata"):
            r["metadata"] = meta
        meta["privilege_score"] = score
        meta["is_high_value_target"] = score >= _HIGH_VALUE_THRESHOLD


def _ssm_parameter_arn(region: str, account_id: str, name: str) -> str:
    normalized = name if name.startswith("/") else f"/{name}"
    return f"arn:aws:ssm:{region}:{account_id}:parameter{normalized}"


def _ec2_arn(region: str, account_id: str, resource_type: str, resource_id: str) -> str:
    return f"arn:aws:ec2:{region}:{account_id}:{resource_type}/{resource_id}"


def _is_customer_managed_policy(policy_arn: str) -> bool:
    return bool(policy_arn) and not policy_arn.startswith("arn:aws:iam::aws:policy/")


def _compact_policy_doc(doc: dict, max_statements: int = 8) -> list[dict]:
    """Extrai Effect/Action/Resource/Condition de um policy document."""
    if not doc:
        return []
    statements = doc.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    result = []
    for stmt in statements[:max_statements]:
        compact: dict = {
            "Effect": stmt.get("Effect", "Allow"),
            "Action": stmt.get("Action", []),
            "Resource": stmt.get("Resource", "*"),
        }
        condition = stmt.get("Condition")
        if condition:
            compact["Condition"] = condition
        result.append(compact)
    return result


def _fetch_policy_permissions(
    *,
    aws_client: "AwsClient",
    region: str,
    attached_policy_arns: list[str],
    inline_policy_names: list[str],
    principal_type: str,
    principal_name: str,
    max_policies: int,
) -> list[dict]:
    """Retorna policy_permissions: lista de {source, statements} para roles e users."""
    _get_policy_doc = getattr(aws_client, "get_policy_default_version", None)
    _get_role_inline = getattr(aws_client, "get_role_inline_policy", None)
    _get_user_inline = getattr(aws_client, "get_user_inline_policy", None)

    permissions: list[dict] = []
    count = 0

    for policy_arn in attached_policy_arns:
        if count >= max_policies:
            break
        if not _is_customer_managed_policy(policy_arn):
            continue
        if _get_policy_doc is None:
            break
        doc = _get_policy_doc(region=region, policy_arn=policy_arn)
        if doc:
            policy_name = policy_arn.rsplit("/", 1)[-1]
            statements = _compact_policy_doc(doc)
            if statements:
                permissions.append({"source": policy_name, "policy_arn": policy_arn, "statements": statements})
                count += 1

    for policy_name in inline_policy_names:
        if count >= max_policies:
            break
        doc = None
        if principal_type == "role" and _get_role_inline is not None:
            doc = _get_role_inline(region=region, role_name=principal_name, policy_name=policy_name)
        elif principal_type == "user" and _get_user_inline is not None:
            doc = _get_user_inline(region=region, user_name=principal_name, policy_name=policy_name)
        if doc:
            statements = _compact_policy_doc(doc)
            if statements:
                permissions.append({"source": f"inline:{policy_name}", "statements": statements})
                count += 1

    return permissions


def run_foundation_discovery(
    *,
    bundle_name: str,
    target: TargetConfig,
    authorization: AuthorizationConfig,
    output_dir: Path,
    client: AwsClient | None = None,
    limits: DiscoveryLimits | None = None,
) -> tuple[Path, Path, dict]:
    issues = validate_target(target)
    if issues:
        raise ValueError("; ".join(issues))

    profiles = resolve_bundle(bundle_name)
    for profile in profiles:
        validate_profile_access(profile.name, authorization)

    aws_client = client or Boto3AwsClient()
    effective_limits = limits or DiscoveryLimits()
    region = target.allowed_regions[0]
    caller_identity = aws_client.get_caller_identity(region=region)

    resources: list[dict] = []
    relationships: list[dict] = []
    evidence: list[dict] = []
    services_scanned: list[str] = []
    account_id = target.accounts[0]

    users = aws_client.list_users(region=region)
    services_scanned.append("iam")
    evidence.append({"service": "iam", "api_calls": ["iam:ListUsers", "iam:ListAttachedUserPolicies", "iam:ListUserPolicies", "iam:GetUserPolicy", "iam:GetPolicyVersion"]})
    _list_attached_user_policies = getattr(aws_client, "list_attached_user_policies", None)
    _list_user_inline_policies = getattr(aws_client, "list_user_inline_policies", None)
    for user_arn in users:
        user_name = user_arn.rsplit("/", 1)[-1]
        attached_policies: list[dict] = []
        inline_policy_names: list[str] = []
        if _list_attached_user_policies is not None:
            try:
                attached_policies = _list_attached_user_policies(region=region, user_name=user_name) or []
            except Exception:
                attached_policies = []
        if _list_user_inline_policies is not None:
            try:
                inline_policy_names = _list_user_inline_policies(region=region, user_name=user_name) or []
            except Exception:
                inline_policy_names = []
        user_attached_arns = [p.get("PolicyArn") for p in attached_policies if p.get("PolicyArn")]
        policy_permissions = _fetch_policy_permissions(
            aws_client=aws_client,
            region=region,
            attached_policy_arns=user_attached_arns,
            inline_policy_names=inline_policy_names,
            principal_type="user",
            principal_name=user_name,
            max_policies=effective_limits.max_policies_per_principal,
        )
        user_meta: dict = {
            "user_name": user_name,
            "attached_policy_names": [p.get("PolicyName") for p in attached_policies if p.get("PolicyName")],
            "attached_policy_arns": user_attached_arns,
            "inline_policy_names": inline_policy_names,
        }
        if policy_permissions:
            user_meta["policy_permissions"] = policy_permissions
        resources.append(
            {
                "service": "iam",
                "resource_type": "identity.user",
                "identifier": user_arn,
                "region": region,
                "metadata": user_meta,
                "source": "aws_api",
            }
        )

    roles = aws_client.list_roles(region=region)[: effective_limits.max_roles]
    services_scanned.append("iam")
    evidence.append({"service": "iam", "api_calls": ["sts:GetCallerIdentity", "iam:ListRoles", "iam:GetRole", "iam:ListAttachedRolePolicies", "iam:ListRolePolicies", "iam:GetRolePolicy", "iam:GetPolicyVersion"]})
    for role_arn in roles:
        if _is_service_linked_role(role_arn):
            continue
        role_name = role_arn.rsplit("/", 1)[-1]
        role_details = aws_client.get_role_details(region=region, role_name=role_name)
        trust_principals = _extract_trust_principals(role_details.get("AssumeRolePolicyDocument"))
        attached_policies = role_details.get("AttachedPolicies", [])
        inline_policy_names = role_details.get("InlinePolicyNames", [])
        role_attached_arns = [policy.get("PolicyArn") for policy in attached_policies if policy.get("PolicyArn")]
        policy_permissions = _fetch_policy_permissions(
            aws_client=aws_client,
            region=region,
            attached_policy_arns=role_attached_arns,
            inline_policy_names=inline_policy_names,
            principal_type="role",
            principal_name=role_name,
            max_policies=effective_limits.max_policies_per_principal,
        )
        role_meta: dict = {
            "is_service_linked": False,
            "role_name": role_name,
            "trust_principals": trust_principals,
            "trust_is_broad": any(principal == "*" for principal in trust_principals),
            "attached_policy_arns": role_attached_arns,
            "attached_policy_names": [policy.get("PolicyName") for policy in attached_policies if policy.get("PolicyName")],
            "inline_policy_names": inline_policy_names,
            "permissions_boundary_arn": (role_details.get("PermissionsBoundary") or {}).get("PermissionsBoundaryArn"),
            "managed_policy_count": len(attached_policies),
            "inline_policy_count": len(inline_policy_names),
        }
        if policy_permissions:
            role_meta["policy_permissions"] = policy_permissions
        resources.append(
            {
                "service": "iam",
                "resource_type": "identity.role",
                "identifier": role_arn,
                "region": region,
                "metadata": role_meta,
                "source": "aws_api",
            }
        )
        for principal in trust_principals:
            if principal.startswith("arn:aws:iam::") and (":role/" in principal or ":user/" in principal):
                relationships.append(
                    {
                        "source": principal,
                        "target": role_arn,
                        "type": "can_assume",
                    }
                )

    buckets = aws_client.list_buckets(region=region)[: effective_limits.max_buckets]
    services_scanned.append("s3")
    evidence.append({"service": "s3", "api_calls": ["s3:ListBuckets", "s3:ListBucket"]})
    for bucket_name in buckets:
        bucket_arn = f"arn:aws:s3:::{bucket_name}"
        resources.append(
            {
                "service": "s3",
                "resource_type": "data_store.s3_bucket",
                "identifier": bucket_arn,
                "region": region,
                "metadata": {},
                "source": "aws_api",
            }
        )
        object_keys = aws_client.list_objects(region=region, bucket=bucket_name)[
            : effective_limits.max_objects_per_bucket
        ]
        for object_key in object_keys:
            resources.append(
                {
                    "service": "s3",
                    "resource_type": "data_store.s3_object",
                    "identifier": f"{bucket_arn}/{object_key}",
                    "region": region,
                    "metadata": {"bucket": bucket_name, "object_key": object_key},
                    "source": "aws_api",
                }
            )

    secrets = aws_client.list_secrets(region=region)[: effective_limits.max_secrets]
    services_scanned.append("secretsmanager")
    evidence.append({"service": "secretsmanager", "api_calls": ["secretsmanager:ListSecrets"]})
    for secret_name in secrets:
        resources.append(
            {
                "service": "secretsmanager",
                "resource_type": "secret.secrets_manager",
                "identifier": f"arn:aws:secretsmanager:{region}:{account_id}:secret:{secret_name}",
                "region": region,
                "metadata": {"name": secret_name},
                "source": "aws_api",
            }
        )

    ssm_prefixes = _resolve_ssm_discovery_prefixes(target=target, profiles=profiles)
    services_scanned.append("ssm")
    evidence.append({"service": "ssm", "api_calls": ["ssm:GetParametersByPath"]})
    for path_prefix in ssm_prefixes:
        parameter_names = aws_client.list_parameters_by_path(region=region, path=path_prefix)[
            : effective_limits.max_parameters_per_prefix
        ]
        for name in parameter_names:
            parameter_arn = _ssm_parameter_arn(region, account_id, name)
            resources.append(
                {
                    "service": "ssm",
                    "resource_type": "secret.ssm_parameter",
                    "identifier": parameter_arn,
                    "region": region,
                    "metadata": {"name": name, "path_prefix": path_prefix},
                    "source": "aws_api",
                }
            )

    instance_profiles = aws_client.list_instance_profiles(region=region)
    instances = aws_client.list_instances(region=region)
    internet_gateways = aws_client.list_internet_gateways(region=region)
    route_tables = aws_client.list_route_tables(region=region)
    subnets = aws_client.list_subnets(region=region)
    security_groups = aws_client.list_security_groups(region=region)
    load_balancers = aws_client.list_load_balancers(region=region)
    rest_apis = aws_client.list_rest_apis(region=region)
    target_groups = aws_client.list_target_groups(region=region)
    services_scanned.append("ec2")
    evidence.append(
        {
            "service": "ec2",
            "api_calls": [
                "iam:ListInstanceProfiles",
                "ec2:DescribeInstances",
                "ec2:DescribeInternetGateways",
                "ec2:DescribeRouteTables",
                "ec2:DescribeSubnets",
                "ec2:DescribeSecurityGroups",
            ],
        }
    )
    services_scanned.append("elasticloadbalancing")
    evidence.append(
        {
            "service": "elasticloadbalancing",
            "api_calls": [
                "elasticloadbalancing:DescribeLoadBalancers",
                "elasticloadbalancing:DescribeTargetGroups",
                "elasticloadbalancing:DescribeListeners",
            ],
        }
    )
    services_scanned.append("apigateway")
    evidence.append(
        {
            "service": "apigateway",
            "api_calls": ["apigateway:GET /restapis", "apigateway:GET /restapis/*/resources"],
        }
    )

    subnet_arns: dict[str, str] = {}
    route_table_arns: dict[str, str] = {}
    security_group_arns: dict[str, str] = {}
    internet_gateway_arns: dict[str, str] = {}

    for profile in instance_profiles:
        profile_arn = profile.get("Arn")
        if not profile_arn:
            continue
        resources.append(
            {
                "service": "iam",
                "resource_type": "compute.instance_profile",
                "identifier": profile_arn,
                "region": region,
                "metadata": {
                    "role": next(iter(profile.get("Roles", [])), None),
                    "roles": profile.get("Roles", []),
                    "name": profile.get("InstanceProfileName"),
                },
                "source": "aws_api",
            }
        )
        for role_arn in profile.get("Roles", []):
            relationships.append(
                {
                    "source": role_arn,
                    "target": profile_arn,
                    "type": "attached_to_instance_profile",
                }
            )

    for gateway in internet_gateways:
        gateway_id = gateway.get("InternetGatewayId")
        if not gateway_id:
            continue
        gateway_arn = _ec2_arn(region, account_id, "internet-gateway", gateway_id)
        internet_gateway_arns[gateway_id] = gateway_arn
        resources.append(
            {
                "service": "ec2",
                "resource_type": "network.internet_gateway",
                "identifier": gateway_arn,
                "region": region,
                "metadata": {
                    "vpc_ids": [
                        attachment.get("VpcId")
                        for attachment in gateway.get("Attachments", [])
                        if attachment.get("VpcId")
                    ]
                },
                "source": "aws_api",
            }
        )

    for subnet in subnets:
        subnet_id = subnet.get("SubnetId")
        if not subnet_id:
            continue
        subnet_arn = _ec2_arn(region, account_id, "subnet", subnet_id)
        subnet_arns[subnet_id] = subnet_arn
        resources.append(
            {
                "service": "ec2",
                "resource_type": "network.subnet",
                "identifier": subnet_arn,
                "region": region,
                "metadata": {
                    "vpc_id": subnet.get("VpcId"),
                    "availability_zone": subnet.get("AvailabilityZone"),
                    "map_public_ip_on_launch": subnet.get("MapPublicIpOnLaunch", False),
                },
                "source": "aws_api",
            }
        )

    for security_group in security_groups:
        group_id = security_group.get("GroupId")
        if not group_id:
            continue
        group_arn = _ec2_arn(region, account_id, "security-group", group_id)
        security_group_arns[group_id] = group_arn
        public_ingress = sorted(
            {
                permission.get("FromPort")
                for permission in security_group.get("IpPermissions", [])
                for ip_range in permission.get("IpRanges", [])
                if ip_range.get("CidrIp") == "0.0.0.0/0" and permission.get("FromPort") is not None
            }
        )
        resources.append(
            {
                "service": "ec2",
                "resource_type": "network.security_group",
                "identifier": group_arn,
                "region": region,
                "metadata": {
                    "vpc_id": security_group.get("VpcId"),
                    "group_name": security_group.get("GroupName"),
                    "public_ingress_ports": public_ingress,
                },
                "source": "aws_api",
            }
        )

    for route_table in route_tables:
        route_table_id = route_table.get("RouteTableId")
        if not route_table_id:
            continue
        route_table_arn = _ec2_arn(region, account_id, "route-table", route_table_id)
        route_table_arns[route_table_id] = route_table_arn
        internet_route_targets = sorted(
            {
                route.get("GatewayId")
                for route in route_table.get("Routes", [])
                if route.get("GatewayId", "").startswith("igw-")
                and route.get("DestinationCidrBlock") == "0.0.0.0/0"
            }
        )
        associated_subnets = [
            association.get("SubnetId")
            for association in route_table.get("Associations", [])
            if association.get("SubnetId")
        ]
        resources.append(
            {
                "service": "ec2",
                "resource_type": "network.route_table",
                "identifier": route_table_arn,
                "region": region,
                "metadata": {
                    "vpc_id": route_table.get("VpcId"),
                    "subnet_ids": associated_subnets,
                    "internet_gateway_ids": internet_route_targets,
                    "routes_to_internet": bool(internet_route_targets),
                },
                "source": "aws_api",
            }
        )
        for subnet_id in associated_subnets:
            subnet_arn = subnet_arns.get(subnet_id)
            if subnet_arn:
                relationships.append(
                    {
                        "source": subnet_arn,
                        "target": route_table_arn,
                        "type": "associated_with_route_table",
                    }
                )
        for gateway_id in internet_route_targets:
            gateway_arn = internet_gateway_arns.get(gateway_id)
            if gateway_arn:
                relationships.append(
                    {
                        "source": route_table_arn,
                        "target": gateway_arn,
                        "type": "routes_to_internet_gateway",
                    }
                )

    for instance in instances:
        instance_id = instance.get("InstanceId")
        if not instance_id:
            continue
        instance_arn = instance.get("Arn") or _ec2_arn(region, account_id, "instance", instance_id)
        resources.append(
            {
                "service": "ec2",
                "resource_type": "compute.ec2_instance",
                "identifier": instance_arn,
                "region": region,
                "metadata": {
                    "instance_id": instance_id,
                    "state": instance.get("State"),
                    "public_ip": instance.get("PublicIpAddress"),
                    "private_ip": instance.get("PrivateIpAddress"),
                    "instance_profile": instance.get("IamInstanceProfileArn"),
                    "subnet_id": instance.get("SubnetId"),
                    "vpc_id": instance.get("VpcId"),
                    "security_group_ids": instance.get("SecurityGroupIds", []),
                    "network_reachable_from_internet": bool(instance.get("PublicIpAddress")),
                },
                "source": "aws_api",
            }
        )
        profile_arn = instance.get("IamInstanceProfileArn")
        if profile_arn:
            relationships.append(
                {
                    "source": instance_arn,
                    "target": profile_arn,
                    "type": "uses_instance_profile",
                }
            )
        subnet_id = instance.get("SubnetId")
        subnet_arn = subnet_arns.get(subnet_id)
        if subnet_arn:
            relationships.append(
                {
                    "source": instance_arn,
                    "target": subnet_arn,
                    "type": "deployed_in_subnet",
                }
            )
        for group_id in instance.get("SecurityGroupIds", []):
            group_arn = security_group_arns.get(group_id)
            if group_arn:
                relationships.append(
                    {
                        "source": instance_arn,
                        "target": group_arn,
                        "type": "protected_by_security_group",
                    }
                )

    for load_balancer in load_balancers:
        load_balancer_arn = load_balancer.get("LoadBalancerArn")
        if not load_balancer_arn:
            continue
        scheme = load_balancer.get("Scheme")
        listeners = aws_client.list_listeners(region=region, load_balancer_arn=load_balancer_arn)
        resources.append(
            {
                "service": "elasticloadbalancing",
                "resource_type": "network.load_balancer",
                "identifier": load_balancer_arn,
                "region": region,
                "metadata": {
                    "exposure": "public" if scheme == "internet-facing" else "private",
                    "internet_facing": scheme == "internet-facing",
                    "dns_public": bool(load_balancer.get("DNSName")) and scheme == "internet-facing",
                    "dns_name": load_balancer.get("DNSName"),
                    "vpc_id": load_balancer.get("VpcId"),
                    "state": load_balancer.get("State"),
                    "listener_public": any(listener.get("Port") in {80, 443} for listener in listeners),
                },
                "source": "aws_api",
            }
        )
        for listener in listeners:
            listener_arn = listener.get("ListenerArn")
            if not listener_arn:
                continue
            resources.append(
                {
                    "service": "elasticloadbalancing",
                    "resource_type": "network.lb_listener",
                    "identifier": listener_arn,
                    "region": region,
                    "metadata": {
                        "load_balancer_arn": load_balancer_arn,
                        "port": listener.get("Port"),
                        "protocol": listener.get("Protocol"),
                        "listener_public": listener.get("Port") in {80, 443},
                        "target_group_arns": listener.get("TargetGroupArns", []),
                        "listener_forwarding": bool(listener.get("TargetGroupArns")),
                    },
                    "source": "aws_api",
                }
            )
            relationships.append(
                {
                    "source": load_balancer_arn,
                    "target": listener_arn,
                    "type": "exposes_listener",
                }
            )
            for target_group_arn in listener.get("TargetGroupArns", []):
                relationships.append(
                    {
                        "source": listener_arn,
                        "target": target_group_arn,
                        "type": "forwards_to_target_group",
                    }
                )

    for target_group in target_groups:
        target_group_arn = target_group.get("TargetGroupArn")
        if not target_group_arn:
            continue
        resources.append(
            {
                "service": "elasticloadbalancing",
                "resource_type": "network.target_group",
                "identifier": target_group_arn,
                "region": region,
                "metadata": {
                    "target_type": target_group.get("TargetType"),
                    "protocol": target_group.get("Protocol"),
                    "port": target_group.get("Port"),
                    "vpc_id": target_group.get("VpcId"),
                    "health_check_protocol": target_group.get("HealthCheckProtocol"),
                    "load_balancer_arns": target_group.get("LoadBalancerArns", []),
                },
                "source": "aws_api",
            }
        )
        for load_balancer_arn in target_group.get("LoadBalancerArns", []):
            relationships.append(
                {
                    "source": load_balancer_arn,
                    "target": target_group_arn,
                    "type": "uses_target_group",
                }
            )

    for rest_api in rest_apis:
        api_arn = rest_api.get("Arn")
        if not api_arn:
            continue
        endpoint_types = (rest_api.get("EndpointConfiguration") or {}).get("types", [])
        public_stage = "PRIVATE" not in endpoint_types
        integrations = aws_client.list_api_integrations(region=region, rest_api_id=rest_api.get("RestApiId"))
        resources.append(
            {
                "service": "apigateway",
                "resource_type": "network.api_gateway",
                "identifier": api_arn,
                "region": region,
                "metadata": {
                    "name": rest_api.get("Name"),
                    "exposure": "public" if public_stage else "private",
                    "public_stage": public_stage,
                    "endpoint_types": endpoint_types,
                    "integration_status": "active" if integrations else "not_configured",
                },
                "source": "aws_api",
            }
        )
        for integration in integrations:
            integration_id = f"{api_arn}/integration/{integration.get('HttpMethod', 'ANY')}{integration.get('ResourcePath', '/')}"
            target_uri = integration.get("Uri")
            target_instance = None
            target_load_balancer = None
            if target_uri:
                for instance in instances:
                    private_ip = instance.get("PrivateIpAddress")
                    if private_ip and private_ip in target_uri:
                        target_instance = instance.get("Arn")
                        break
                for load_balancer in load_balancers:
                    dns_name = load_balancer.get("DNSName")
                    if dns_name and dns_name in target_uri:
                        target_load_balancer = load_balancer.get("LoadBalancerArn")
                        break
            resources.append(
                {
                    "service": "apigateway",
                    "resource_type": "network.api_integration",
                    "identifier": integration_id,
                    "region": region,
                    "metadata": {
                        "rest_api_arn": api_arn,
                        "resource_path": integration.get("ResourcePath"),
                        "http_method": integration.get("HttpMethod"),
                        "integration_type": integration.get("Type"),
                        "connection_type": integration.get("ConnectionType"),
                        "uri": target_uri,
                        "target_instance": target_instance,
                        "target_load_balancer": target_load_balancer,
                        "integration_status": "active" if target_uri else "not_configured",
                    },
                    "source": "aws_api",
                }
            )
            relationships.append(
                {
                    "source": api_arn,
                    "target": integration_id,
                    "type": "uses_integration",
                }
            )
            if target_load_balancer:
                relationships.append(
                    {
                        "source": integration_id,
                        "target": target_load_balancer,
                        "type": "integrates_with_load_balancer",
                    }
                )
            if target_instance:
                relationships.append(
                    {
                        "source": integration_id,
                        "target": target_instance,
                        "type": "integrates_with_instance",
                    }
                )

    _compute_privilege_scores(resources)
    _derive_attack_targets(resources)
    _apply_recursive_scores(resources)

    summary = {
        "roles": sum(1 for resource in resources if resource["resource_type"] == "identity.role"),
        "buckets": sum(1 for resource in resources if resource["resource_type"] == "data_store.s3_bucket"),
        "objects": sum(1 for resource in resources if resource["resource_type"] == "data_store.s3_object"),
        "secrets": sum(
            1 for resource in resources if resource["resource_type"] == "secret.secrets_manager"
        ),
        "parameters": sum(
            1 for resource in resources if resource["resource_type"] == "secret.ssm_parameter"
        ),
        "instance_profiles": sum(
            1 for resource in resources if resource["resource_type"] == "compute.instance_profile"
        ),
        "instances": sum(1 for resource in resources if resource["resource_type"] == "compute.ec2_instance"),
        "internet_gateways": sum(
            1 for resource in resources if resource["resource_type"] == "network.internet_gateway"
        ),
        "route_tables": sum(1 for resource in resources if resource["resource_type"] == "network.route_table"),
        "subnets": sum(1 for resource in resources if resource["resource_type"] == "network.subnet"),
        "security_groups": sum(
            1 for resource in resources if resource["resource_type"] == "network.security_group"
        ),
        "load_balancers": sum(
            1 for resource in resources if resource["resource_type"] == "network.load_balancer"
        ),
        "api_gateways": sum(
            1 for resource in resources if resource["resource_type"] == "network.api_gateway"
        ),
        "target_groups": sum(
            1 for resource in resources if resource["resource_type"] == "network.target_group"
        ),
        "lb_listeners": sum(
            1 for resource in resources if resource["resource_type"] == "network.lb_listener"
        ),
        "api_integrations": sum(
            1 for resource in resources if resource["resource_type"] == "network.api_integration"
        ),
        "relationships": len(relationships),
    }

    snapshot = {
        "target": target.name,
        "bundle": bundle_name,
        "collected_at": datetime.now(UTC).isoformat(),
        "caller_identity": caller_identity,
        "services_scanned": services_scanned,
        "regions_scanned": target.allowed_regions,
        "resources": resources,
        "relationships": relationships,
        "evidence": evidence,
        "summary": summary,
        "discovery_config": {
            "ssm_prefixes": ssm_prefixes,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "discovery.json"
    md_path = output_dir / "discovery.md"
    json_path.write_text(json.dumps(snapshot, indent=2))
    md_path.write_text(_render_discovery_markdown(snapshot))
    return json_path, md_path, snapshot


def _render_discovery_markdown(snapshot: dict) -> str:
    summary = snapshot["summary"]
    lines = [
        "# Discovery Summary",
        "",
        f"- Target: {snapshot['target']}",
        f"- Bundle: {snapshot['bundle']}",
        f"- Collected at: {snapshot['collected_at']}",
        f"- Services scanned: {snapshot['services_scanned']}",
        f"- Regions scanned: {snapshot['regions_scanned']}",
        f"- SSM prefixes: {snapshot.get('discovery_config', {}).get('ssm_prefixes', [])}",
        "",
        "## Summary",
        f"- Roles: {summary['roles']}",
        f"- Buckets: {summary['buckets']}",
        f"- Objects: {summary['objects']}",
        f"- Secrets: {summary['secrets']}",
        f"- Parameters: {summary['parameters']}",
        f"- Instance profiles: {summary.get('instance_profiles', 0)}",
        f"- Instances: {summary.get('instances', 0)}",
        f"- Internet gateways: {summary.get('internet_gateways', 0)}",
        f"- Route tables: {summary.get('route_tables', 0)}",
        f"- Subnets: {summary.get('subnets', 0)}",
        f"- Security groups: {summary.get('security_groups', 0)}",
        f"- Load balancers: {summary.get('load_balancers', 0)}",
        f"- API Gateways: {summary.get('api_gateways', 0)}",
        f"- Target groups: {summary.get('target_groups', 0)}",
        f"- LB listeners: {summary.get('lb_listeners', 0)}",
        f"- API integrations: {summary.get('api_integrations', 0)}",
        f"- Relationships: {summary.get('relationships', 0)}",
        "",
        "## Sample Resources",
    ]
    for resource in snapshot["resources"][:15]:
        lines.append(
            f"- {resource['resource_type']}: {resource['identifier']}"
        )
    if snapshot.get("relationships"):
        lines.extend(
            [
                "",
                "## Sample Relationships",
            ]
        )
        for relationship in snapshot["relationships"][:10]:
            lines.append(
                f"- {relationship['type']}: {relationship['source']} -> {relationship['target']}"
            )
    lines.append("")
    return "\n".join(lines)


def _resolve_ssm_discovery_prefixes(*, target: TargetConfig, profiles: list) -> list[str]:
    if target.discovery_ssm_prefixes:
        return sorted(set(target.discovery_ssm_prefixes))
    profile_prefixes = {
        prefix
        for profile in profiles
        for prefix in getattr(profile, "discovery_ssm_prefixes", [])
    }
    if profile_prefixes:
        return sorted(profile_prefixes)
    return list(DEFAULT_SSM_DISCOVERY_PREFIXES)


def _extract_trust_principals(policy_document) -> list[str]:
    if not policy_document:
        return []
    statements = policy_document.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    principals: set[str] = set()
    for statement in statements:
        principal = statement.get("Principal")
        if principal == "*":
            principals.add("*")
            continue
        if not isinstance(principal, dict):
            continue
        aws_principal = principal.get("AWS")
        if aws_principal == "*":
            principals.add("*")
            continue
        if isinstance(aws_principal, str):
            principals.add(aws_principal)
        elif isinstance(aws_principal, list):
            principals.update(item for item in aws_principal if isinstance(item, str))
    return sorted(principals)
