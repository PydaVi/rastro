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

from core.policy_evaluator import evaluate_effective_access, evaluate_scope

# (action_type, from_arn, to_arn, extra)
_Step = tuple[str, str, str, Any]

# Resource types that carry potentially extractable credentials
_CREDENTIAL_RESOURCE_TYPES = {
    "secret.secrets_manager",
    "secret.ssm_parameter",
    "data_store.s3_object",
    "compute.lambda_function",  # Bloco 16.3: env vars como fonte de credencial
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
    "compute.lambda_function": "lambda:GetFunctionConfiguration",
}

# Bloco 10: resource_type do alvo de um passo "read" → tool de tools/aws/*.yaml
# que o executor sabe rodar. Ação e tool são conceitos distintos (Bloco 12
# usa action pra avaliar política; Bloco 10 usa tool pra executar de verdade)
# mas nascem do mesmo resource_type, por isso os dois dicts ficam lado a lado.
_READ_TOOL_BY_RESOURCE_TYPE: dict[str, str] = {
    "secret.secrets_manager": "secretsmanager_read_secret",
    "secret.ssm_parameter":   "ssm_read_parameter",
    "data_store.s3_object":   "s3_read_sensitive",
    "compute.lambda_function": "lambda_read_env",
}

# Bloco 16.1: teto de fan-out do pivot. Uma credencial extraída (de um secret,
# SSM, S3 ou create-key) pode, na modelagem, assumir roles que NÃO têm aresta de
# assumability visível — porque a aresta é computada a partir da policy de OUTROS
# principals, não da identidade extraída, cujo dono real o discovery não resolve.
# Por isso o sweep não pode ser gateado por `can_assume` (os testes do Bloco 9
# provam que um role sem `assumable_by` precisa ser alcançável). Mas varrer TODOS
# os roles gera explosão O(users × roles) (medido na 16.1: 245k hipóteses a 800
# recursos). Solução: varrer só os TOP-N roles por valor de alvo — um atacante
# pivota pra privilégio, não pra qualquer role. O executor path-driven ainda
# resolve a identidade extraída real em runtime; cortar hipóteses especulativas
# aqui é exatamente o certo. N alto o bastante pra não cortar labs pequenos.
_MAX_PIVOT_FANOUT = 8

# mutate action → tool executável. iam:PutRolePolicy fica de fora de propósito:
# não existe tools/aws/iam_put_role_policy_mutate.yaml hoje — sem tool real,
# o path fica incompleto e o hypothesis não ganha path estruturado (ver
# _build_structured_path), preservando o fallback por profile.
_MUTATE_ACTION_TO_TOOL: dict[str, str] = {
    "iam:AttachRolePolicy":    "iam_attach_role_policy_mutate",
    "iam:CreatePolicyVersion": "iam_create_policy_version_mutate",
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
    # identity_arn → [(role_arn, instance_profile_arn)] reachable via EC2 compute pivot
    # (Bloco 16.3): rodar comando numa instância cujo profile concede a role.
    can_pivot_compute: dict[str, list[tuple[str, str]]] = field(default_factory=lambda: defaultdict(list))
    # arn → resource_type
    resource_types: dict[str, str] = field(default_factory=dict)
    # all non-service role ARNs in the environment
    _all_role_arns: list[str] = field(default_factory=list)
    # role_arn → (is_high_value_target, privilege_score) para priorizar o fan-out
    # do pivot (Bloco 16.1). Vazio quando o discovery não computou scores.
    _role_priority: dict[str, tuple[bool, int]] = field(default_factory=dict)
    # cache do top-N de roles-alvo do pivot (computado sob demanda em _traverse)
    _pivot_roles_cache: list[str] | None = None
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
                rmeta = r.get("metadata") or {}
                g._role_priority[arn] = (
                    bool(rmeta.get("is_high_value_target", False)),
                    int(rmeta.get("privilege_score", 0) or 0),
                )
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

            # readable_by → CanRead edges (SCP Deny suprime — ver _scp_denies)
            read_action = _READ_ACTION_BY_RESOURCE_TYPE.get(rtype)
            if not (read_action and g._scp_denies(read_action, arn)):
                for principal in meta.get("readable_by", []):
                    g.can_read[principal].append(arn)

            # createkey_by → CanCreateKey edges (only on users)
            if rtype == "identity.user" and not g._scp_denies("iam:CreateAccessKey", arn):
                for principal in meta.get("createkey_by", []):
                    g.can_create_key[principal].append(arn)

            # assumable_by → CanAssume edges (only on roles)
            if rtype == "identity.role" and not g._scp_denies("sts:AssumeRole", arn):
                for principal in meta.get("assumable_by", []):
                    g.can_assume[principal].append(arn)

            # mutable_by → CanMutate edges (only on roles)
            if rtype == "identity.role":
                mutable_by: dict[str, list[str]] = meta.get("mutable_by", {})
                for action, principals in mutable_by.items():
                    if g._scp_denies(action, arn):
                        continue
                    for principal in principals:
                        g.can_mutate[principal].append((arn, action))

            # compute_pivot_by → CanPivotCompute edges (Bloco 16.3, only on roles)
            if rtype == "identity.role":
                profile_arn = meta.get("compute_pivot_profile", "")
                for principal in meta.get("compute_pivot_by", []):
                    g.can_pivot_compute[principal].append((arn, profile_arn))

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

    def _scp_denies(self, action: str, resource_arn: str) -> bool:
        """Fase de labs: um Deny de SCP diretamente anexada é AUTORITATIVO,
        independente da hierarquia de OU (diferente do baseline Allow-all, que o
        Bloco 11/12 adiou por exigir a hierarquia). Então suprimir aresta que uma
        SCP Deny visível bloqueia é correto e reduz falso positivo. Só suprime
        quando o Deny é CERTO (operador de Condition não-suportado → não suprime,
        pra não inventar falso negativo)."""
        if not self._scp_statements:
            return False
        result = evaluate_scope(self._scp_statements, action, resource_arn, {})
        return result.decision == "Deny" and result.certain

    def _pivot_target_roles(self) -> list[str]:
        """Bloco 16.1: top-N roles-alvo do pivot, priorizados por valor de alvo.

        Uma identidade extraída pode assumir roles sem aresta de assumability
        visível (ver _MAX_PIVOT_FANOUT), então não dá pra gatear por `can_assume`.
        Prioriza high-value target e privilege_score (Bloco 4c) quando o discovery
        os computou; empate/ausência cai em ordem de ARN (determinístico). Corta
        em _MAX_PIVOT_FANOUT pra evitar a explosão O(users × roles) da 16.1.
        """
        if self._pivot_roles_cache is None:
            ordered = sorted(
                self._all_role_arns,
                key=lambda arn: (
                    0 if self._role_priority.get(arn, (False, 0))[0] else 1,  # high-value primeiro
                    -self._role_priority.get(arn, (False, 0))[1],             # privilege_score desc
                    arn,                                                       # desempate estável
                ),
            )
            self._pivot_roles_cache = ordered[:_MAX_PIVOT_FANOUT]
        return self._pivot_roles_cache

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

            # CanAssume: current → role. Multi-level (fase de labs): a role assumida
            # é ENFILEIRADA pra continuar a travessia (role-chain real, role→read,
            # role→mutate). Só arestas REAIS enfileiram — o sweep especulativo do
            # pivot (roles-alvo por palpite) continua terminal, pra não compor
            # especulação em cima de especulação. Bound: visited + max_depth + o
            # teto de fan-out da 16.1 no sweep do pivot.
            for role_arn in self.can_assume.get(current_arn, []):
                full_path = path + [("assume", current_arn, role_arn, None)]
                hyp = self._path_to_hypothesis(entry_arn, role_arn, full_path)
                if hyp is not None:
                    hypotheses.append(hyp)
                if role_arn not in visited_identities:
                    visited_identities.add(role_arn)
                    queue.append((role_arn, full_path, depth + 1))

            # CanPivotCompute: current → role via EC2 instance profile (Bloco 16.3).
            # A role alcançada é real → também continua a travessia.
            for (role_arn, profile_arn) in self.can_pivot_compute.get(current_arn, []):
                full_path = path + [("compute_pivot", current_arn, role_arn, profile_arn)]
                hyp = self._path_to_hypothesis(entry_arn, role_arn, full_path)
                if hyp is not None:
                    hypotheses.append(hyp)
                if role_arn not in visited_identities:
                    visited_identities.add(role_arn)
                    queue.append((role_arn, full_path, depth + 1))

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
                        # Identidade extraída: assume os top-N roles-alvo (Bloco 16.1,
                        # antes varria todos os roles → explosão O(users × roles))
                        for role_arn in self._pivot_target_roles():
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
                    for role_arn in self._pivot_target_roles():
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
                    elif ":lambda:" in first_to or rtype == "compute.lambda_function":
                        attack_class = "lambda_pivot"
                    else:
                        attack_class = "credential_pivot"
                elif first_type == "create_key":
                    attack_class = "iam_create_access_key_pivot"
                else:
                    attack_class = "role_chain"

        elif last_type == "compute_pivot":
            attack_class = "compute_pivot"

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
            elif stype == "compute_pivot":
                attack_steps.append(
                    f"Run commands on an EC2 instance via instance profile {extra} "
                    f"to steal the credentials of role {to_a} from IMDS"
                )

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
            path=self._build_structured_path(path),
        )

    def _step_tool(self, step: _Step) -> str | None:
        """Bloco 10: tool executável de um passo, ou None se não há tool real ainda."""
        stype, _from_a, to_a, extra = step
        if stype == "assume":
            return "iam_passrole"
        if stype == "create_key":
            return "iam_create_access_key"
        if stype == "compute_pivot":
            return "ec2_instance_profile_pivot"
        if stype == "mutate":
            return _MUTATE_ACTION_TO_TOOL.get(extra)
        if stype == "read":
            return _READ_TOOL_BY_RESOURCE_TYPE.get(self.resource_types.get(to_a, ""))
        return None

    def _build_structured_path(self, path: list[_Step]) -> list:
        """Bloco 10: converte o path interno em list[PathStep] executável.

        Retorna [] (não parcial) se QUALQUER passo não mapear pra uma tool
        real — um path parcialmente executável travaria o runtime no meio;
        melhor deixar vazio e cair no dispatch por profile (fallback).
        """
        from planner.strategic_planner import PathStep  # lazy import, evita ciclo

        steps = []
        for stype, from_a, to_a, extra in path:
            tool = self._step_tool((stype, from_a, to_a, extra))
            if tool is None:
                return []
            # compute_pivot: o executor age sobre o instance profile (extra),
            # não sobre a role (to_a, que é o alvo lógico da hipótese).
            step_target = extra if stype == "compute_pivot" else to_a
            steps.append(PathStep(step_type=stype, actor=from_a, target=step_target, tool=tool))
        return steps

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
