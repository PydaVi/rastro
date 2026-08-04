"""Bloco 9 — CapabilityGraph: travessia de grafo para derivação de hipóteses.

Substitui as funções manuais _derive_credential_access_hypotheses,
_derive_credential_pivot_hypotheses e _derive_create_access_key_hypotheses
por BFS sobre um grafo formal de capacidades derivado do discovery snapshot
(com anotações produzidas pelo Bloco 7 _compute_capability_graph).

Tipos de aresta:
  CanRead(identity → resource)           — via readable_by
  CanMutate(identity → resource, action) — via mutable_by
  CanCreateKey(identity → user)          — via createkey_by
  CanAssume(identity → role)             — via assumable_by
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from core.policy_evaluator import evaluate_effective_access

# (action_type, from_arn, to_arn, extra)
_Step = tuple[str, str, str, Any]

# Resource types that carry potentially extractable credentials
_CREDENTIAL_RESOURCE_TYPES = {
    "secret.secrets_manager",
    "secret.ssm_parameter",
    "data_store.s3_object",
}

# Mutation action → attack_class
_MUTATE_ACTION_TO_CLASS: dict[str, str] = {
    "iam:AttachRolePolicy":    "iam_attach_role_policy_privesc",
    "iam:PutRolePolicy":       "iam_put_role_policy_privesc",
    "iam:CreatePolicyVersion": "iam_create_policy_version_privesc",
}

# resource_type do alvo de um passo "read" → action concreta usada pelo
# PolicyEvaluator (Bloco 12). Só o necessário para avaliar o PRIMEIRO passo
# do path (sempre a partir do entry_arn real) — passos seguintes partem de
# identidades sintéticas (extracted://...) que não têm policy_permissions
# própria no discovery, então não são avaliados nesta versão.
_READ_ACTION_BY_RESOURCE_TYPE: dict[str, str] = {
    "secret.secrets_manager": "secretsmanager:GetSecretValue",
    "secret.ssm_parameter":   "ssm:GetParameter",
    "data_store.s3_object":   "s3:GetObject",
    "data_store.s3_bucket":   "s3:GetObject",
}


@dataclass
class CapabilityGraph:
    """Grafo de capacidades derivado do discovery snapshot.

    Edges são dicts[str, list] para suportar adjacency lookup O(1).
    """
    # identity_arn → [resource_arns] readable by that identity
    can_read: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    # identity_arn → [(resource_arn, action)] mutable by that identity
    can_mutate: dict[str, list[tuple[str, str]]] = field(default_factory=lambda: defaultdict(list))
    # identity_arn → [user_arns] for which that identity can create access keys
    can_create_key: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    # identity_arn → [role_arns] assumable by that identity
    can_assume: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    # arn → resource_type
    resource_types: dict[str, str] = field(default_factory=dict)
    # all non-service role ARNs in the environment
    _all_role_arns: list[str] = field(default_factory=list)
    # identity_arn (real, nao sintetica) → {"policy_permissions": [...], "boundary_policy_permissions": [...] | None}
    _principal_policy_data: dict[str, dict] = field(default_factory=dict)
    # SCPs diretamente anexados a conta (Bloco 11), ou None se nao resolvivel
    _scp_statements: list[dict] | None = None

    @classmethod
    def build(cls, discovery_snapshot: dict) -> "CapabilityGraph":
        """Constrói o grafo a partir do snapshot com anotações do Bloco 7."""
        g = cls()
        resources = discovery_snapshot.get("resources", [])
        governance = discovery_snapshot.get("governance") or {}
        g._scp_statements = governance.get("scp_policies")

        # Pass 1: collect resource types, role ARNs and per-principal policy data
        for r in resources:
            arn = r.get("identifier", "")
            rtype = r.get("resource_type", "")
            if arn:
                g.resource_types[arn] = rtype
            if rtype == "identity.role" and ":role/aws-service-role/" not in arn:
                g._all_role_arns.append(arn)
            if rtype in ("identity.user", "identity.role") and arn:
                meta = r.get("metadata") or {}
                g._principal_policy_data[arn] = {
                    "policy_permissions": meta.get("policy_permissions", []),
                    "boundary_policy_permissions": meta.get("boundary_policy_permissions"),
                }

        # Pass 2: build edges from Bloco 7 capability annotations
        for r in resources:
            arn = r.get("identifier", "")
            rtype = r.get("resource_type", "")
            meta = r.get("metadata") or {}

            # readable_by → CanRead edges
            for principal in meta.get("readable_by", []):
                g.can_read[principal].append(arn)

            # createkey_by → CanCreateKey edges (only on users)
            if rtype == "identity.user":
                for principal in meta.get("createkey_by", []):
                    g.can_create_key[principal].append(arn)

            # assumable_by → CanAssume edges (only on roles)
            if rtype == "identity.role":
                for principal in meta.get("assumable_by", []):
                    g.can_assume[principal].append(arn)

            # mutable_by → CanMutate edges (only on roles)
            if rtype == "identity.role":
                mutable_by: dict[str, list[str]] = meta.get("mutable_by", {})
                for action, principals in mutable_by.items():
                    for principal in principals:
                        g.can_mutate[principal].append((arn, action))

        return g

    def derive_all_hypotheses(
        self,
        entry_identities: list[str],
        max_depth: int = 3,
    ) -> list:
        """BFS a partir de cada entry identity — retorna todas as hipóteses de ataque.

        Substitui:
          - _derive_credential_access_hypotheses
          - _derive_credential_pivot_hypotheses
          - _derive_create_access_key_hypotheses
        """
        hypotheses = []
        for entry_arn in entry_identities:
            hypotheses.extend(self._traverse(entry_arn, max_depth))
        return hypotheses

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _traverse(self, entry_arn: str, max_depth: int) -> list:
        """BFS de um entry identity. Retorna hipóteses encontradas."""
        hypotheses: list = []

        # queue: (identity_arn, path_so_far, depth)
        queue: deque[tuple[str, list[_Step], int]] = deque([(entry_arn, [], 0)])
        visited_identities: set[str] = {entry_arn}

        while queue:
            current_arn, path, depth = queue.popleft()
            if depth >= max_depth:
                continue

            # CanAssume: current → role (terminal — gerou uma hipótese)
            for role_arn in self.can_assume.get(current_arn, []):
                full_path = path + [("assume", current_arn, role_arn, None)]
                hyp = self._path_to_hypothesis(entry_arn, role_arn, full_path)
                if hyp is not None:
                    hypotheses.append(hyp)

            # CanMutate: current → role/resource (terminal)
            for (resource_arn, action) in self.can_mutate.get(current_arn, []):
                full_path = path + [("mutate", current_arn, resource_arn, action)]
                hyp = self._path_to_hypothesis(entry_arn, resource_arn, full_path)
                if hyp is not None:
                    hypotheses.append(hyp)

            # CanRead: current → resource
            for resource_arn in self.can_read.get(current_arn, []):
                full_path = path + [("read", current_arn, resource_arn, None)]
                rtype = self.resource_types.get(resource_arn, "")

                # Leitura direta: credential_access_direct (target = o próprio recurso)
                if rtype in ("secret.secrets_manager", "secret.ssm_parameter"):
                    hyp = self._path_to_hypothesis(entry_arn, resource_arn, full_path)
                    if hyp is not None:
                        hypotheses.append(hyp)

                # O recurso pode carregar credenciais embutidas → pivota para roles
                if rtype in _CREDENTIAL_RESOURCE_TYPES:
                    extracted_arn = f"extracted://{resource_arn}"
                    if extracted_arn not in visited_identities:
                        visited_identities.add(extracted_arn)
                        # Heurística: identidade extraída pode assumir qualquer role disponível
                        for role_arn in self._all_role_arns:
                            pivot_path = full_path + [("assume", extracted_arn, role_arn, None)]
                            hyp = self._path_to_hypothesis(
                                entry_arn, role_arn, pivot_path,
                                intermediate=resource_arn,
                            )
                            if hyp is not None:
                                hypotheses.append(hyp)

            # CanCreateKey: current → user (pivota para roles via extracted identity)
            for user_arn in self.can_create_key.get(current_arn, []):
                full_path = path + [("create_key", current_arn, user_arn, None)]
                extracted_arn = f"extracted://iam_user/{user_arn}"
                if extracted_arn not in visited_identities:
                    visited_identities.add(extracted_arn)
                    for role_arn in self._all_role_arns:
                        pivot_path = full_path + [("assume", extracted_arn, role_arn, None)]
                        hyp = self._path_to_hypothesis(
                            entry_arn, role_arn, pivot_path,
                            intermediate=user_arn,
                        )
                        if hyp is not None:
                            hypotheses.append(hyp)

        return hypotheses

    def _path_to_hypothesis(
        self,
        entry_arn: str,
        target_arn: str,
        path: list[_Step],
        intermediate: str | None = None,
    ):
        """Converte um caminho de travessia em AttackHypothesis."""
        from planner.strategic_planner import AttackHypothesis  # lazy import

        if not path:
            return None

        last_step = path[-1]
        last_type = last_step[0]

        # ---------- Derivação do attack_class ----------
        if last_type == "assume":
            if len(path) == 1:
                attack_class = "role_chain"
            else:
                # Pivot: olha para o tipo do primeiro passo
                first_type = path[0][0]
                first_to = path[0][2]
                if first_type == "read":
                    rtype = self.resource_types.get(first_to, "")
                    if "secretsmanager" in first_to:
                        attack_class = "credential_pivot"
                    elif "ssm" in first_to or rtype == "secret.ssm_parameter":
                        attack_class = "ssm_pivot"
                    elif "s3" in first_to or rtype == "data_store.s3_object":
                        attack_class = "s3_pivot"
                    else:
                        attack_class = "credential_pivot"
                elif first_type == "create_key":
                    attack_class = "iam_create_access_key_pivot"
                else:
                    attack_class = "role_chain"

        elif last_type == "mutate":
            action = last_step[3]
            attack_class = _MUTATE_ACTION_TO_CLASS.get(action, "iam_mutation_privesc")

        elif last_type == "read":
            rtype = self.resource_types.get(target_arn, "")
            if rtype in ("secret.secrets_manager", "secret.ssm_parameter"):
                attack_class = "credential_access_direct"
            else:
                attack_class = "data_access"

        else:
            return None

        # ---------- Construção dos attack_steps ----------
        attack_steps: list[str] = []
        for stype, from_a, to_a, extra in path:
            if stype == "assume":
                attack_steps.append(
                    f"Call sts:AssumeRole as {from_a} to assume {to_a}"
                )
            elif stype == "read":
                attack_steps.append(f"Read {to_a} to extract embedded credentials")
            elif stype == "create_key":
                attack_steps.append(
                    f"Call iam:CreateAccessKey on {to_a} to create long-term credentials"
                )
            elif stype == "mutate":
                attack_steps.append(f"Call {extra} on {to_a} to escalate privileges")

        # ---------- Confiança e reasoning ----------
        confidence = "high" if len(path) == 1 else "medium"
        intermediate_note = f" via {intermediate}" if intermediate else ""
        reasoning = (
            f"CapabilityGraph BFS (depth {len(path)}): "
            f"{entry_arn} → {target_arn}{intermediate_note} [{attack_class}]"
        )

        return AttackHypothesis(
            entry_identity=entry_arn,
            target=target_arn,
            attack_class=attack_class,
            intermediate_resource=intermediate,
            attack_steps=attack_steps,
            confidence=confidence,
            reasoning=reasoning,
            evaluation_tier=self._compute_evaluation_tier(entry_arn, path),
        )

    def _step_action(self, step: _Step) -> str | None:
        """Action concreta de um passo, para o PolicyEvaluator. None se nao mapeavel."""
        stype, _from_a, to_a, extra = step
        if stype == "assume":
            return "sts:AssumeRole"
        if stype == "create_key":
            return "iam:CreateAccessKey"
        if stype == "mutate":
            return extra
        if stype == "read":
            return _READ_ACTION_BY_RESOURCE_TYPE.get(self.resource_types.get(to_a, ""))
        return None

    def _compute_evaluation_tier(self, entry_arn: str, path: list[_Step]) -> str:
        """Bloco 12: tenta promover de "structural" pra "evaluated".

        So avalia o PRIMEIRO passo do path — e sempre a partir de entry_arn,
        uma identidade real com policy_permissions no discovery (garantido por
        _traverse). Passos seguintes partem de identidades sinteticas
        (extracted://...) sem policy_permissions propria — nao avaliaveis
        nesta versao (ver limitacoes no PLAN.md Bloco 12).
        """
        if not path:
            return "structural"
        step = path[0]
        _stype, from_a, to_a, _extra = step
        if from_a != entry_arn:
            return "structural"
        action = self._step_action(step)
        if action is None:
            return "structural"
        principal_data = self._principal_policy_data.get(from_a)
        if principal_data is None:
            return "structural"

        result = evaluate_effective_access(
            identity_statements=principal_data["policy_permissions"],
            action=action,
            resource_arn=to_a,
            boundary_statements=principal_data["boundary_policy_permissions"],
            scp_statements=self._scp_statements,
        )
        if result.allowed and result.certain:
            return "evaluated"
        return "structural"
