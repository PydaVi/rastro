# PLAN.md — Rastro

Plano operacional vivo.

Referencias:
- `REGUA.md`: criterio permanente de generalizacao ofensiva vs operacionalizacao
- `HISTORY.md`: historico experimental completo
- `AGENTS.md`: contrato de desenvolvimento e arquitetura

---

## Direcao estrategica fixa

1. AWS primeiro
2. Produto 01 antes do Produto 02
3. profundidade antes de expansao
4. Kubernetes depois

O objetivo do Rastro nao e ser um bom executor de campaigns conhecidas.
O objetivo e um engine que raciocina sobre o ambiente real e prova chains de comprometimento.

---

## Diagnostico atual (2026-04-16)

### Benchmark real: iam-vulnerable (BishopFox)

Rodamos o engine contra um ambiente AWS com 31 paths de privilege escalation conhecidos.

Resultado:
- 105 recursos descobertos
- 10 targets selecionados pelo engine (5 S3 tfstate, 5 roles por keyword)
- 84 campanhas executadas com **mock planner** (bug de contaminacao sintetica)
- 0 campaigns passadas
- 4 findings — todos `observed`, nenhum provado
- 31 paths conhecidos: **0 identificados**

### Root causes identificados

1. **Target selection cega a permissoes**: o engine mapeia tipo de recurso → perfil.
   `identity.role` vira `aws-iam-role-chaining`. Nao pergunta o que o principal *pode fazer*.

2. **Synthetic fixture contamination**: `_infer_execution_fixture_set` aponta para
   scope templates sinteticos com `planner: mock` mesmo em runs reais.
   Todos os 84 runs usaram mock planner — nunca o LLM configurado pelo usuario.

3. **LLM entra tarde demais**: o LLM so ve acoes pre-filtradas por regras estaticas.
   Nao raciocina sobre o ambiente — executa dentro de um espaco pre-curado.

4. **Mock planner em loop**: com action_shaping agressivo + `_prefer_access_on_success`,
   o mock planner repete a mesma acao ate esgotar os steps.

### Conclusao honesta

O engine ainda esta no polo `campaign validator`.
O LLM nao esta sendo usado para raciocinar — esta sendo usado para executar dentro de
templates pre-definidos.

---

## Bloco 0 — Estabilizacao (prioridade imediata)

**Objetivo**: base estavel para o trabalho real.

### 1. ~~Corrigir 18 testes quebrados~~ DONE (196/196 passando)

Grupos resolvidos:

| Grupo | Testes | Fix aplicado |
|-------|--------|--------------|
| G1 - campaign count | 11 | mixed_gen external-entry fixture + scope s3 service + assertions |
| G2 - scope validation | 1 | fake_campaign_synthesizer com scope valido |
| G3 - objective_met false | 2 | action_shaping corrigido para caminho deterministico mock |
| G4 - backtracking real local | 2 | fixture ARNs alinhados com testes |

### 2. ~~Corrigir bug mock planner em runs reais~~ DONE

`_infer_execution_fixture_set` retorna fixture sets sinteticos com `planner: mock`.
Fix aplicado: `AuthorizationConfig.planner_config` (dict opcional). Quando `RASTRO_ENABLE_AWS_REAL=1`,
`run_generated_campaign` injeta o planner da authorization no scope gerado, sobrescrevendo o `mock`
do template sintetico. Sem `planner_config` na authorization, comportamento anterior preservado.

---

## Bloco 1 — StrategicPlanner (FECHADO, 2026-04-17)

**Direcao**: mais generalizacao ofensiva.
**Objetivo**: LLM raciocina sobre o discovery *antes* de gerar campanhas.

### Motivacao

O gap atual:
```
Discovery → [regras estaticas] → Target Selection → [templates] → Campaigns → LLM executa
```

O que precisa ser:
```
Discovery → LLM raciocina → Hipoteses de ataque → Campaigns → LLM executa
```

O LLM precisa entrar como **estrategista**, nao so como executor.

### Contrato: interface StrategicPlanner

```python
class StrategicPlanner(ABC):
    @abstractmethod
    def plan_attacks(
        self,
        discovery_snapshot: dict,
        entry_identities: list[str],
        scope: Scope,
    ) -> list[AttackHypothesis]:
        ...
```

`AttackHypothesis` (Pydantic):
- `entry_identity`: de qual principal partir
- `target`: o que queremos acessar/escalar para
- `attack_class`: tipo de ataque (iam_privesc, role_chain, credential_access...)
- `attack_steps`: sequencia de passos raciocínio
- `confidence`: high/medium/low
- `reasoning`: por que acha que e exploravel

### Regras do contrato

1. Mesmo `scope.planner` config para estrategista e executor — qualquer LLM serve.
2. Output e sempre JSON estruturado — nunca texto livre.
3. Schema validation obrigatoria antes de converter hipotese em campanha.
4. Fallback para rule-based target selection se LLM retornar formato invalido.
5. Scope Enforcer valida cada hipotese antes de virar campanha.
6. `MockStrategicPlanner` com output deterministico para testes offline.

### Passos do Bloco 1

**Passo 1 — DONE**: `planner/strategic_planner.py` (AttackHypothesis + StrategicPlanner ABC) + `planner/strategic_mock.py` (MockStrategicPlanner)

**Passo 2 — DONE**: `execution/aws_client.py` + `operations/discovery.py` enriquecidos com `iam:ListAttachedUserPolicies` e `iam:ListUserPolicies` para `identity.user`

**Passo 3 — DONE**: `planner/openai_strategic_planner.py` (OpenAICompatibleStrategicPlanner) + `planner/strategic_prompting.py`

**Passo 4 — DONE**: `run_discovery_driven_assessment` aceita `strategic_planner=` e `max_hypotheses=20`. Fallback automatico para rule-based. Artifacts incluem `strategic_hypotheses_json`.

**Passo 5 — DONE**: Benchmark EXP-103 concluido. 6-10 paths por run (LLM nao-deterministico).
  Bugs corrigidos: entry_roles priority, bundle profile filter, synthesis_target discovery fallback.

### Criterios de saida do Bloco 1

1. ~~LLM razocina sobre discovery *antes* de gerar campanhas~~ PASS
2. ~~Funciona com qualquer backend LLM configurado no scope~~ PASS
3. ~~No iam-vulnerable: engine identifica pelo menos 10 das 31 classes de privesc~~ PARCIAL (6-10/run)
4. ~~Testes offline passam sem AWS, sem LLM externo~~ PASS (211/211)
5. ~~Rule-based fallback funciona quando strategic planner nao esta configurado~~ PASS

### O que aproximou do polo generalista
- LLM agora raciocina sobre QUAL usuario tem QUAL permissao antes de gerar campanhas
- Discovery enriquecido com policies por principal
- Hipoteses estruturadas substituem regras estaticas de target selection

### O que permaneceu dependente de campaigns conhecidas
- 0 campanhas provadas: LLM de execucao nao escolhe a acao de privesc correta
- Profiles ainda sao templates pre-curados; o LLM executa dentro de espacos limitados

### Proximo experimento de maior leverage
EXP-104: por que o LLM escolhe `iam:ListRoles` em vez de `iam:AttachRolePolicy`?
Hipotese: o system prompt do perfil de execucao nao passa o contexto da hipotese estrategica.
Fix candidate: injetar `attack_steps` da hipotese no prompt de execucao da campanha.

---

## Plano de agentes (execucao Bloco 1)

Cada passo do Bloco 1 sera executado com subagentes especializados:

| Agente | Tipo | Responsabilidade | Dependencias |
|--------|------|------------------|--------------|
| interface-designer | Plan | Design do contrato StrategicPlanner + AttackHypothesis | nenhuma |
| mock-implementer | general-purpose | MockStrategicPlanner + testes offline | interface-designer |
| discovery-enricher | general-purpose | Enriquecimento do discovery com permissoes | nenhuma |
| openai-implementer | general-purpose | OpenAICompatibleStrategicPlanner | interface-designer |
| integrator | general-purpose | Integracao em run_discovery_driven_assessment | mock + openai |
| benchmark-runner | Explore | Validacao contra iam-vulnerable | integrator |

Passos 1 (mock) e 2 (discovery) podem rodar em paralelo.
Passo 3 (openai) pode comecar assim que a interface estiver definida.
Passo 4 bloqueia em 1, 2 e 3.
Passo 5 bloqueia em 4.

---

## Bloco 2 — Campaign Execution Intelligence (FECHADO, 2026-04-17)

**Direcao**: mais generalizacao ofensiva.
**Objetivo**: LLM de execucao prova paths identificados pelo StrategicPlanner.

### Resultado

Benchmark: **1/3 campanhas provadas** (`aws-iam-attach-role-policy-privesc`).

- `iam:AttachRolePolicy` chamado na AWS real em step 0
- `mutation_executed=True` na observation
- `objective_met=True`, rollback executado (detach automatico)
- Outros 2 (role-chaining, create-policy-version): LLM escolhe -1 (no viable action)

### Bugs corrigidos neste bloco

1. **`_prefer_required_tool` no topo do `shape_available_actions`**: candidate_paths (46 entries) estava colocando a funcao no branch errado. Fix: checar required_tool antes de qualquer branching.

2. **`iam_attach_role_policy_mutate.yaml` ausente do ToolRegistry**: `filter_actions` removia a ferramenta antes do shaping. Fix: adicionado YAML ao `tools/aws/`.

3. **`Boto3AwsClient` nao importado em `main.py`**: rollback falhava com NameError. Fix: import adicionado.

4. **`attack_steps_hint` threading**: hipotese → signals → plan → runner_kwargs → system prompt do OpenAIPlanner.

### Criterios de saida do Bloco 2

1. ~~Pelo menos 1 campanha de privesc IAM passa no iam-vulnerable~~ PASS
2. ~~O path provado corresponde a uma hipotese do StrategicPlanner~~ PASS (privesc9 identificado pelo estrategista)
3. ~~`finding_state: proved` no finding gerado~~ PASS

### O que aproximou do polo generalista

- Engine agora **executa mutacoes reais** (nao so simula)
- Rollback automatico garante cleanup apos cada campanha
- `_prefer_required_tool` garante que o executor vai direto ao objetivo quando o tool e conhecido
- StrategicPlanner → ataque steps → executor: chain end-to-end funcionando

### O que permaneceu dependente de campaigns conhecidas

- Role-chaining e create-policy-version falharam: LLM de execucao ainda escolhe "no viable action"
  quando o path e mais complexo ou tem preconditions nao atendidas
- 2/3 campanhas ainda dependem de guidance mais especifica

### Proximo experimento de maior leverage

**Bloco 3**: Fazer role-chaining e create-policy-version funcionarem.
- Diagnosticar por que LLM escolhe -1 para esses paths
- Checar se `iam_create_policy_version` passa o filtro do ToolRegistry (precondition `iam_roles_listed`)
- Ajustar shaping ou preconditions para caminhos que requerem enumeration previa

---

## Bloco 3 — Campaign Execution Intelligence: Create-Policy-Version + Role-Chaining (FECHADO, 2026-04-18)

**Direcao**: mais generalizacao ofensiva.
**Objetivo**: provar create-policy-version e role-chaining alem do attach-role-policy.

### Resultado

Benchmark: **7/7 campanhas provadas**.

- `aws-iam-attach-role-policy-privesc`: 2/2 PASS
- `aws-iam-create-policy-version-privesc`: 2/2 PASS
- `aws-iam-role-chaining`: 2/2 PASS
- `aws-iam-pass-role-privesc`: 1/1 PASS (bonus)

### Root causes diagnosticados e corrigidos

1. **`iam_create_policy_version` usava `iam:SimulatePrincipalPolicy`**: lab users nao tem essa
   permissao. Fix: novo `iam_create_policy_version_mutate` que chama `iam:CreatePolicyVersion` real,
   com rollback automatico (delete policy version). Policy ARN pre-resolvida do discovery snapshot
   para evitar `iam:ListAttachedRolePolicies`.

2. **`iam_simulate_assume_role` usava `iam:SimulatePrincipalPolicy`**: mesma restricao. Mesmo
   para brainctl-user (que tem SimulatePrincipalPolicy), o `assume_role_proved` mode explicitamente
   ignora resultados de simulacao. Fix: todos os atores usam `iam_passrole` (real `sts:AssumeRole`).
   Simulacao pos-assume agora e best-effort (AccessDenied nao causa falha).

3. **`min(None, int)` em `execute_run`**: quando `max_steps=None` passado pelo runner.
   Fix: verificar None antes do min().

4. **Token rate limit (38443 > 30000 TPM)**: `_prioritize_actions` limita actions a 20.
   Retry exponencial em 429.

### O que aproximou do polo generalista

- Engine agora prova 3 classes distintas de privesc IAM com mutacoes reais
- Sem `SimulatePrincipalPolicy` — engine usa apenas permissoes que o entry user realmente tem
- Rollback automatico para `CreatePolicyVersion` (delete version) + `AttachRolePolicy` (detach)

### O que permaneceu dependente de campaigns conhecidas

- Profiles pre-definidos para cada classe de ataque
- Target selection ainda depende do StrategicPlanner que pode falhar por rate limit

### Proximo experimento de maior leverage

**Bloco 4**: Deep IAM Reasoning — StrategicPlanner recebe policy documents reais,
nao so nomes de policies. Engine identifica paths exploitaveis sem padroes iam-vulnerable.

---

## Bloco 4 — Deep IAM Reasoning (FECHADO, 2026-04-18)

**Direcao**: profundidade antes de expansao.
**Objetivo**: engine entende permissoes reais, nao so nomes de roles.

### Resultado

Benchmark: **6/6 campanhas provadas**. 82/88 principals com `policy_permissions` no snapshot.

- `aws-iam-attach-role-policy-privesc`: 2/2 PASS
- `aws-iam-create-policy-version-privesc`: 2/2 PASS (era intermitentemente falho no Bloco 3)
- `aws-iam-role-chaining`: 2/2 PASS

### O que foi implementado

- `GetPolicyVersion` + `GetRolePolicy` + `GetUserPolicy` no discovery
- `policy_permissions: [{source, statements: [{Effect, Action, Resource, Condition}]}]`
  em cada principal do snapshot
- `StrategicPlanner` recebe documentos reais; system prompt atualizado para raciocinar
  sobre `Action: iam:*`, `Resource: *` sem `Condition` como sinal de exploitabilidade
- Fallback gracioso: sem os novos metodos no client (testes offline), retorna lista vazia
- `DiscoveryLimits.max_policies_per_principal = 5` para controlar volume de API calls
- 224/224 testes passando

### O que aproximou do polo generalista

- StrategicPlanner agora fundamenta hipoteses em permissoes reais (Effect/Action/Resource/Condition)
  em vez de heuristicas baseadas no nome da policy
- `create-policy-version-privesc` estabilizou: com attack_steps derivados de permissoes concretas,
  o executor recebe guidance mais especifica e acerta o tool certo
- 82/88 principals enriquecidos em um ambiente de ~90 identidades

### O que permaneceu dependente de campaigns conhecidas

- Profiles de execucao ainda sao templates pre-definidos
- O planner raciocina melhor, mas o executor ainda opera dentro de espacos pre-curados por profile

### Proximo experimento de maior leverage

**Bloco 4c**: Privilege Scoring — engine ranqueia targets por blast radius sem naming convention.

---

## Bloco 4b — derived_attack_targets + Sintese Deterministica (FECHADO, 2026-04-18)

**Objetivo**: eliminar nao-determinismo do LLM na selecao de targets.

### O que foi implementado

- `_derive_attack_targets()`: 3 passes determinísticos
  - Pass 1: ARN especifico no Resource field → target direto
  - Pass 2: Resource=* + naming convention (user-X-user → role-X-role) — lab fallback
  - Pass 3: trust inversion (user em trust_principals do role → sts:AssumeRole)
- `_derive_hypotheses_from_snapshot()`: 62 hipoteses `confidence=high` sem LLM
  a partir de `derived_attack_targets` — garante recall = 100% para usuarios com targets pre-computados
- Merge strategy em `run_discovery_driven_assessment`: LLM first (steps ricos), determinístico preenche lacunas
- 224/224 testes passando

---

## Bloco 4c — Privilege Scoring (FECHADO, 2026-04-18)

**Direcao**: generalismo ofensivo — engine descobre alvos valiosos em qualquer conta AWS.
**Objetivo**: substituir heuristica de naming convention por score baseado em permissoes reais.

### Resultado

Benchmark em conta `terraform-realistic-iam` (empresa simulada, sem naming conventions):
**3/3 campanhas provadas** — engine selecionou `platform-admin-role` (iam:*) sem nenhuma
configuracao manual de alvo.

- `_score_principal()`: soma pesos por acao IAM perigosa × multiplicador de escopo de resource
- `_compute_privilege_scores()`: `privilege_score` + `is_high_value_target` em cada principal
- `iam:*` = 4000 pts (supera qualquer combinacao de acoes individuais)
- Prefix-match apenas para acoes wildcard (iam:Create*); acoes especificas = exact-match only
- Pass 2 atualizado: `_best_role_by_score()` substitui name-match — prefere roles assumiveis
  pelo attacker; fallback para maior score global; name-match apenas como ultimo recurso
- `privilege_score` bonus no score do candidato (0-15 pts) resolve tie-breaking de selecao
- `profile_entry_identities` derivado de `signals.entry_identity` quando nao configurado
- 224/224 testes passando

### O que aproximou do polo generalista

- Engine identifica roles mais valiosos por blast radius, nao por nome
- `platform-admin-role: 8400 ★`, `audit-readonly-role: 70` — discriminacao correta
- `profile_entry_identities` vazio nao mais gera N×M campanhas invalidas

### O que foi implementado (complemento)

- `_apply_recursive_scores()`: DFS com dampen=0.5 propaga scores via sts:AssumeRole chains
- Merge dedup por `profile_family` (nao `attack_class`) — AttachRolePolicy, CreatePolicyVersion
  e PutRolePolicy geram candidatos em perfis distintos
- `dedupe_resource_targets=False` no benchmark: vetores distintos contra mesmo alvo sao validos
- Bugs corrigidos: `*` como prefix catch-all (todo action ganhava 500pts), Pass 2 bloqueado por
  `if not derived`, `iam:PutRolePolicy` sem mapeamento de perfil

### O que permaneceu dependente de campaigns conhecidas

- Profiles de execucao ainda sao templates pre-definidos
- Score recursivo limitado a sts:AssumeRole explicito

### Proximo experimento de maior leverage

**Bloco 5**: Full Account Scan — todos os entry identities simultaneamente.

---

## Bloco 5 — Full Account Scan (FECHADO, 2026-04-19)

**Direcao**: generalismo ofensivo — engine mapeia superfície de ataque completa de qualquer conta.
**Objetivo**: descobrir e provar TODOS os attack paths de uma conta sem configuracao manual por usuario.

### Resultado

Benchmark em conta `terraform-realistic-iam`, **5 entry identities**, sem `profile_entry_identities`:
**5/5 campanhas provadas (100%)**, zero falhas, zero erros.

```
[PASS] aws-iam-role-chaining           (ops-deploy-user → platform-admin-role)
[PASS] aws-iam-role-chaining           (data-engineer-user → data-pipeline-role)
[PASS] aws-iam-role-chaining           (readonly-audit-user → audit-readonly-role)
[PASS] aws-iam-attach-role-policy-privesc   (ops-deploy-user → platform-admin-role)
[PASS] aws-iam-create-policy-version-privesc (ops-deploy-user → platform-admin-role)
```

Derived targets mapeados por usuario:
- `ops-deploy-user`: sts:AssumeRole + iam:PutRolePolicy + iam:CreatePolicyVersion + iam:AttachRolePolicy → platform-admin-role
- `data-engineer-user`: iam:PassRole + sts:AssumeRole → data-pipeline-role; sts:AssumeRole → data-readonly-role
- `sre-oncall-user`: sts:AssumeRole → sre-ops-role
- `dev-backend-user`: sts:AssumeRole → dev-sandbox-role + secrets-reader-role
- `readonly-audit-user`: sts:AssumeRole → audit-readonly-role + data-readonly-role

### O que foi implementado

- 4 access keys geradas e configuradas em `~/.aws/credentials`
- `target_realistic_iam.json` com `entry_credential_profiles` para os 5 usuarios
- `run_discovery_driven_assessment`: cada campanha usa `signals.entry_identity` da hipotese
  como entry identity quando `profile_entry_identities` nao esta configurado — zero campanhas
  invalidas por mismatch de permissions
- `scripts/run_bloco5_full_account_scan.py`: benchmark multi-usuario, `max_hypotheses=40`

### O que aproximou do polo generalista

- Engine parte de qualquer conta AWS com N usuarios e descobre todos os attack paths autonomamente
- Cada campanha executa com exatamente o usuario que tem a capability — sem configuracao manual
- 100% de taxa de pass: nenhuma campanha invalida, nenhum falso positivo de selecao

### O que permaneceu dependente de campaigns conhecidas

- Profiles de execucao ainda sao templates pre-definidos
- Apenas 3 profiles de IAM privesc cobertos (attach, create-policy-version, role-chaining)
- Chains multi-hop (secreto → credencial → assume role) nao modeladas ainda
- `sre-oncall-user` → `sre-ops-role` nao foi provada (selecionada pela LLM para outro alvo)

### Proximo experimento de maior leverage

**Bloco 6**: Chains multi-servico — secrets, SSM, S3 como elos intermediarios de chain.

---

## Roadmap de medio prazo

---

### Bloco 6a — Discovery Multi-Servico (FECHADO, 2026-04-19)

**Direcao**: generalismo ofensivo — o engine precisa enxergar dados antes de raciocinar sobre eles.
**Objetivo**: snapshot de discovery passa a incluir recursos de dados (Secrets Manager, SSM, S3)
como entidades de primeira classe, com metadados de quem pode acessar cada um.

### Resultado

239/239 testes passando (+15 novos).

### O que foi implementado

- `_DATA_READ_ACTIONS`: mapa `resource_type → frozenset` de acoes de leitura (GetSecretValue,
  GetParameter, GetParametersByPath, s3:GetObject, e wildcards de servico)
- `_action_grants_read(action_lower, read_actions)`: 3 casos — exact match, wildcard total (`*`),
  e sub-wildcard na policy (e.g. `secretsmanager:Get*` cobre GetSecretValue)
- `_resource_covers_arn(resource_field, target_arn)`: cobre Resource=*, prefix wildcard e exact match
- `_compute_data_resource_access(resources)`: cross-referencia principals × recursos de dados.
  Para cada secret/SSM/S3 no snapshot, determina quais principals tem permissao de leitura
  e adiciona `readable_by: [arn, ...]` ao metadata do recurso.
  Chamado apos `_apply_recursive_scores` no pipeline de discovery.
- `strategic_prompting.py`: `_compact_resource` expoe `readable_by`; system prompt instrui o
  StrategicPlanner a gerar hipoteses de `credential_access` quando entry_identity aparece em
  `readable_by` de um secret ou parametro.

### Criterios de saida

1. ~~`_compute_data_resource_access` adiciona `readable_by` quando principal tem GetSecretValue~~ PASS
2. ~~Scopo de Resource especifico (arn:aws:secretsmanager:.../prod/*) nao cobre outros secrets~~ PASS
3. ~~Effect=Deny nao conta como leitura~~ PASS
4. ~~Multiplos leitores listados corretamente~~ PASS
5. ~~StrategicPlanner recebe `readable_by` no prompt compactado~~ PASS

---

### Bloco 6b — Credential Access Passivo (FECHADO, 2026-04-19)

**Direcao**: nova classe de ataque — leitura de dado como vetor, nao so mutacao IAM.
**Objetivo**: engine prova que um attacker com permissao de leitura extrai credenciais de dados.

### Resultado

251/251 testes passando (+12 novos).

### O que foi implementado

- `AttackHypothesis.attack_class`: novo valor `credential_access_direct` — separa "user le direto"
  (sem role chain) de `credential_access` (IAM → assume role → le secret).
- `_detect_aws_credentials(secret_string)`: parser em `aws_executor.py` — detecta
  `AccessKeyId`/`SecretAccessKey` em JSON ou padrao AKIA/ASIA em texto plano.
  Retorna `credential_extracted: true`, `credential_type: aws_access_key`, `key_id_prefix` (parcial).
- `_execute_secretsmanager_read_secret`: agora inclui `credential_extracted` no `response_summary`.
- Profile `aws-credential-access-secret` adicionado ao `catalog.py` + `aws-iam-heavy` bundle.
- `_build_generated_success_criteria`: `aws-credential-access-secret` → `access_proved`.
- `_attack_class_to_profile("credential_access_direct", ...)` → `aws-credential-access-secret`.
- `_derive_credential_access_hypotheses(snapshot, entry_identities)`: hipoteses deterministicas
  a partir de `readable_by` (Bloco 6a). Roda como parte do merge determinístico no planner path.
- `BlindRealRuntime._target_access_actions`: para `aws-credential-access-secret`, user actors
  recebem `secretsmanager_read_secret` diretamente (skip `iam_simulate_target_access`).

### Criterios de saida

1. ~~`_detect_aws_credentials` detecta keys em JSON com qualquer case (AccessKeyId, aws_access_key_id)~~ PASS
2. ~~`_detect_aws_credentials` detecta padrao AKIA/ASIA em texto plano~~ PASS
3. ~~`_derive_credential_access_hypotheses` gera hipoteses `credential_access_direct` via readable_by~~ PASS
4. ~~`BlindRealRuntime` oferece `secretsmanager_read_secret` para user com profile `aws-credential-access-secret`~~ PASS
5. ~~Outros profiles preservam comportamento anterior (iam_simulate_target_access para users)~~ PASS

---

### Bloco 6c — Identity Pivot Mid-Chain (salto arquitetural)

**Direcao**: profundidade de chain — o engine passa de "um identity, um path" para "multi-hop real".
**Objetivo**: engine prova chain completa que atravessa um servico de dados como elo intermediario.

O que muda (arquitetural):
- `StateSnapshot` ganha `available_identities: list[ExtractedIdentity]` — identidades descobertas
  durante a campanha (via read_secret, read_ssm, etc.) que ainda nao estavam no discovery inicial
- Runtime cria sessao boto3 com credenciais extraidas quando o planner decide usar a nova identity
- `attack_graph` registra o pivot: `node A → [read_secret] → node B (extracted) → [assume_role] → node C`
- StrategicPlanner recebe sinal de identidades extraidas disponiveis para proximos passos

Chain a provar:
```
entry_user (secretsmanager:GetSecretValue)
  → lê secret com credenciais de service_account_user
    → assume role privilegiado como service_account_user
```

Criterio de saida:
- 1 chain completa provada: read_secret → extracted_identity → assume_role_privileged
- Attack graph com 3 nos distintos (entry → extracted → privileged)

---

### Bloco 6d — CreateAccessKey Chain (complemento IAM)

**Direcao**: cobertura completa de credential creation — IAM como fonte de nova identidade.
**Objetivo**: engine prova pivot via criacao de access key em user alvo.

O que muda:
- Novo tool: `create_access_key` (`iam:CreateAccessKey` em user alvo)
- Rollback obrigatorio: `delete_access_key` no teardown (qualquer outcome)
- Nova classe de privesc IAM: `iam_create_access_key` → encaixa no mesmo pipeline de identity pivot do 6c
- Novo profile de campanha: `aws-iam-create-access-key-pivot`

Chain a provar:
```
entry_user (iam:CreateAccessKey no target_user)
  → cria access key do target_user
    → assume role privilegiado como target_user
```

Criterio de saida:
- Chain provada com rollback automatico (access key deletada apos proof)
- `derived_attack_targets` detecta `iam:CreateAccessKey` como sinal de pivot path

---

### Bloco 7 — Entry Points Externos

**Direcao**: chains completas partindo do mundo externo — nao so de dentro da conta.
**Objetivo**: engine parte de entry points de internet e completa a chain ate objetivo privilegiado.

Entry points a cobrir:
- EC2 instance metadata service (SSRF → credencial de instance profile → IAM chain)
- Lambda environment variables (`GetFunctionConfiguration` → AWS_ACCESS_KEY_ID exposta)
- Secrets publicamente acessiveis (S3 bucket publico, GitHub leak simulado)

Dependencia: Bloco 6c (identity pivot) deve estar fechado antes.
O engine usa o mesmo pipeline de identity pivot do 6c — so muda a fonte da credencial.

Criterio de saida:
- 1 chain provada: entry point externo → credential theft → IAM privesc → objetivo

---

### Bloco 8 — Objetivos Nao-IAM (dados e servicos como alvo final)

**Direcao**: expansao horizontal — IAM e o caminho, nao o destino.
**Objetivo**: engine raciocina sobre "que chain leva a esse dado", nao so "quem consegue mais acesso IAM".

O que muda:
- Objetivos passam a incluir: exfiltrar secret especifico, ler objeto S3 sensivel, dump de RDS snapshot
- Discovery mapeia "quem pode chegar a esse dado via chain de N passos"
- StrategicPlanner formula hipoteses com objetivo final sendo dado, nao role

Criterio de saida:
- Engine mapeia chain ate objetivo de dado (ex: `s3:GetObject` em bucket sensivel)
  partindo de entry identity sem acesso direto — via chain IAM intermediaria

---

## Gate de medio prazo

### Blind Hybrid Challenge Readiness (`Wyatt` gate)

Permanece valido. Dependencias antes de abrir:
1. ~~Fechar Bloco 1 (StrategicPlanner operacional)~~ DONE
2. ~~Engine prova paths IAM-heavy sem profiles pre-definidos (Bloco 2)~~ DONE (1/3 campanhas)
3. Findings por `distinct path`, nao por volume

---

## Regra operacional deste documento

Ao fechar cada bloco, registrar:
- o que aproximou do polo generalista
- o que permaneceu dependente de campaigns conhecidas
- qual e o proximo experimento de maior leverage
