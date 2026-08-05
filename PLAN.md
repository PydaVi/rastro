# PLAN.md — Rastro

Plano operacional vivo.

Referencias:
- `REGUA.md`: criterio permanente de generalizacao ofensiva vs operacionalizacao
- `HISTORY.md`: historico experimental completo
- `AGENTS.md`: contrato de desenvolvimento e arquitetura

---

## Visao de longo prazo

Rastro nao e uma ferramenta de nicho cloud com Kubernetes como adendo distante.
E o canivete suico do defensor: a mesma disciplina — discovery real -> grafo de
capacidades -> hipoteses por traversal -> prova com evidencia auditavel — deve
servir pra qualquer superficie que o defensor precisa validar: rede, firewall,
WAF, aplicacao web, cloud (AWS) e containers (Kubernetes).

A diferenciacao de mercado nao e "pentest automatico". E dar ao defensor a
capacidade de se antecipar ao atacante: rodar, sob autorizacao e controle
proprios, a mesma disciplina de prova que um atacante real usaria, com a
frequencia que a velocidade de mudanca do ambiente exige — nao um ciclo anual
de pentest.

AWS e a primeira superficie porque foi onde essa disciplina foi provada
primeiro (Blocos 1-14 deste documento), nao porque e o teto do produto.
Detalhamento por superficie: README.md. Regua de honestidade de sinal que
qualquer superficie nova precisa respeitar: REGUA.md.

## Direcao estrategica fixa (tatica — sequenciamento, nao teto do produto)

1. AWS primeiro — profundidade antes de expansao de superficie
2. Produto 01 antes do Produto 02
3. profundidade antes de expansao
4. Kubernetes e a segunda superficie candidata; rede, firewall, WAF e
   aplicacao web entram depois, na mesma regua de profundidade-antes-de-expansao

O objetivo do Rastro nao e ser um bom executor de campaigns conhecidas.
O objetivo e um engine que raciocina sobre o ambiente real e prova chains de
comprometimento — hoje em AWS, e por extensao da mesma disciplina, em
qualquer superficie que o defensor precisa validar.

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

### Bloco 6c — Identity Pivot Mid-Chain (salto arquitetural) [FECHADO 2026-04-19]

**Direcao**: profundidade de chain — o engine passa de "um identity, um path" para "multi-hop real".
**Objetivo**: engine prova chain completa que atravessa um servico de dados como elo intermediario.

#### O que foi implementado

- `_extract_full_aws_credentials(secret_string)` em `aws_executor.py`: extrai creds completas (AccessKeyId + SecretAccessKey + SessionToken) de JSON do secret para pivot real
- `_execute_secretsmanager_read_secret` atualizado: se `credential_extracted=True`, armazena creds em `_credentials_by_actor[f"extracted://{secret_id}"]` e retorna `synthetic_actor` no resultado
- `BlindRealRuntime.observe_real`: quando `secretsmanager_read_secret` retorna `credential_extracted=True` + `synthetic_actor`, registra identidade sintética em `state["identities"]` com flag `extracted=True`
- `BlindRealRuntime.enumerate_actions`: atores extraídos recebem apenas `assume_role` actions — sem enumeration, sem policy abuse
- `AttackHypothesis`: novo campo `intermediate_resource: str | None` + nova attack_class `"credential_pivot"`
- `catalog.py`: novo profile `aws-credential-pivot` (target=role, bundle=aws-iam-heavy)
- `campaign_synthesis.py`: `aws-credential-pivot` → `assume_role_proved`
- `service.py`: `_attack_class_to_profile("credential_pivot")` → `"aws-credential-pivot"` + `_derive_credential_pivot_hypotheses()` wired em `run_discovery_driven_assessment`
- 18 novos testes (Bloco 6c), 269/269 passando

#### Bugs encontrados e corrigidos durante run real no lab AWS

- `BlindRealRuntime._target_access_actions` não gerava `secretsmanager_read_secret` para `aws-credential-pivot` (target=role) → adicionado `_pivot_secret_read_actions` com lookup via `readable_by`
- `BlindRealRuntime.enumerate_actions` para `aws-credential-pivot` gerava `iam_passrole` para o entry user → corrigido para que non-extracted actors no pivot profile só recebam enumerate + pivot_secret_read
- `_blind_real_allowed_resources` não incluía secrets no scope → corrigido para incluir `secret.secrets_manager` e `secret.ssm_parameter`
- `_restore_objective_target_access_actions` não restaurava `secretsmanager_read_secret` no modo `assume_role_proved` → adicionado restore para `secretsmanager_read_secret` e `ssm_read_parameter`
- `_pivot_secret_read_actions` usava nome do secret como `secret_id` → trocado para ARN completo (IAM policy matching exige ARN)

#### Criterio atingido

- **Chain provada no lab real AWS em 2 passos**:
  - Step 1: `rastro-pivot-entry-user` lê secret → `credential_extracted=True` → registra `extracted://ARN` como nova identidade
  - Step 2: identidade extraída assume `rastro-pivot-target-role` → `objective_met=True`
- `_extract_full_aws_credentials`: extrai JSON com case-insensitive, inclui SessionToken
- `observe_real` registra synthetic actor corretamente
- `enumerate_actions` limita extracted actors a assume_role only
- `_derive_credential_pivot_hypotheses` gera hipóteses para cada (entry, secret, role) elegível
- Profile `aws-credential-pivot` presente no catálogo e bundle `aws-iam-heavy`
- terraform module `credential_pivot_real/` com render script para provisionar o lab
- 269/269 testes passando

---

### Bloco 6d — SSM + S3 + CreateAccessKey Chains [FECHADO 2026-04-19]

**Direcao**: cobertura completa de credential pivot — SSM, S3 e IAM como fontes de nova identidade.
**Objetivo**: engine prova 3 chains de pivot usando fontes de credencial distintas.

#### O que foi implementado

- **SSM Parameter Pivot** (`aws-credential-pivot-ssm`):
  - `_pivot_ssm_read_actions`: queries `secret.ssm_parameter` com `readable_by`, oferece `ssm_read_parameter`
  - `_execute_ssm_read_parameter` detecta credenciais embutidas no valor, armazena `extracted://ARN` em `_credentials_by_actor`
  - Attack class `ssm_pivot` roteado via `_attack_class_to_profile`
- **S3 Object Pivot** (`aws-credential-pivot-s3`):
  - `_pivot_s3_read_actions`: queries `data_store.s3_object` com `readable_by`, oferece `s3_read_sensitive`
  - `_execute_s3_read_sensitive` detecta credenciais no preview, armazena `extracted://ARN`
  - Attack class `s3_pivot` roteado
- **CreateAccessKey Pivot** (`aws-iam-create-access-key-pivot`):
  - `iam_create_access_key.yaml` + `_execute_iam_create_access_key`: cria chave no user alvo, registra `extracted://iam_user/{arn}`
  - `RollbackTracker.register_delete_access_key`: rollback automatico em qualquer outcome
  - `_create_access_key_actions`: queries `identity.user` com `createkey_by`
  - `_derive_create_access_key_hypotheses` wired em `run_discovery_driven_assessment`
- `_PIVOT_PROFILES` frozenset unifica routing de todos os 4 profiles de pivot
- `_PIVOT_READ_RESOURCE_TYPES` cobre `secret.secrets_manager`, `secret.ssm_parameter`, `data_store.s3_object`
- `_restore_objective_target_access_actions` restaura `ssm_read_parameter`, `s3_read_sensitive`, `iam_create_access_key`
- 3 labs Terraform + fixtures + scripts de integracao
- 288/288 testes passando (+19 novos Bloco 6d)

#### Chains provadas no lab real AWS

- **SSM pivot**: `queue-indexer-user` → `ssm_read_parameter(/svc/mesh/runtime/bootstrap)` → `batch-distributor-role` (2 steps, `objective_met=True`)
- **S3 pivot**: `asset-manifest-user` → `s3_read_sensitive(bootstrap.json)` → `delivery-broker-role` (2 steps, `objective_met=True`)
- **CreateAccessKey**: `mesh-dispatch-operator` → `iam_create_access_key(cache-sync-bot)` → `runtime-broker-role` (4 steps, `objective_met=True`, `rollback_ok=True`)

#### O que aproximou do polo generalista

- Engine prova chains multi-hop via qualquer fonte de credencial (secrets, SSM, S3, IAM key creation)
- `_compute_data_resource_access` + `readable_by` / `createkey_by` detectam elos automaticamente no discovery
- Rollback automatico garante que access keys criadas sao sempre deletadas

#### O que permaneceu dependente de campaigns conhecidas

- Profiles de execucao ainda sao templates pre-definidos
- `createkey_by` ainda requer metadata no fixture — nao deriva de policy analysis automatica

---

## Proximo salto arquitetural — Do reconhecimento de padroes ao raciocínio sobre grafos

### Diagnostico (2026-04-19)

O Bloco 6d expôs o problema central do produto: **para cada novo cenário o código precisa crescer**.
Codex criou 3 labs e foram necessárias 7 classes de mudança manual para o engine os cobrir.

O engine hoje opera em **mundo fechado**: executa bem os ataques que reconhece, mas não infere.
Cada novo vetor de ataque requer: nova função de hipótese, novo método de enumeração, novo profile,
novo roteador, nova lógica de executor. Isso é incompatível com a escala de um produto generalista.

A causa raiz está em três camadas:

```
Camada 1 — Discovery incompleto
  readable_by / createkey_by ainda dependem de anotações manuais em fixtures.
  O engine não deriva automaticamente "quem pode fazer o quê sobre cada recurso"
  diretamente dos documentos de policy IAM que já busca.

Camada 2 — Hipóteses por template, não por traversal
  _derive_credential_pivot_hypotheses, _derive_create_access_key_hypotheses, etc.
  são funções hardcoded para padrões nomeados.
  Um engine cego precisa de traversal de grafo, não de reconhecimento de padrão.

Camada 3 — Efeitos de ação hardcoded no executor
  O que cada tool produz (uma nova identidade, uma credencial extraída) está
  hardcoded por profile no aws_executor.py.
  Um engine cego precisa que cada tool declare seus efeitos — não que o executor
  os conheça antecipadamente.
```

O alvo: dado qualquer conta AWS, o engine entra, constrói o grafo de capacidades,
encontra caminhos por traversal e executa sem nenhuma adaptação de código.

---

### Bloco 7 — Capability Graph Completo

**Direcao**: discovery produz grafo de capacidades completo — sem anotações manuais.
**Objetivo**: ao final do discovery, cada recurso sabe quais principals podem fazer o quê sobre ele,
derivado automaticamente dos documentos de policy IAM já coletados.

**O problema hoje**

`_compute_data_resource_access` calcula `readable_by` para secrets/SSM/S3 a partir de policies.
Mas `createkey_by` foi adicionado manualmente ao fixture. E ações IAM sobre outros principals
(AttachRolePolicy, CreatePolicyVersion, PutRolePolicy) não têm campo equivalente nos recursos.

O resultado: cada novo vetor de pivot requer uma nova anotação manual de metadados.

**O que implementar**

Generalizar `_compute_data_resource_access` para um `_compute_capability_graph(resources)` que:

1. Para cada par (principal, recurso), verifica se alguma policy do principal contém
   uma ação relevante sobre o recurso — usando o mesmo `_action_grants_read` já existente,
   generalizado para qualquer action.

2. Popula campos calculados em cada recurso:
   - `readable_by`: já existe para secret/SSM/S3 — manter
   - `createkey_by`: quem tem `iam:CreateAccessKey` sobre `identity.user`
   - `assumable_by`: quem tem `sts:AssumeRole` sobre `identity.role` via permission policy
     (além do trust policy que já existe em `trust_principals`)
   - `mutable_by`: quem tem `iam:AttachRolePolicy`, `iam:PutRolePolicy`,
     `iam:CreatePolicyVersion` sobre `identity.role` — por ação separada

3. O campo `mutable_by` é um dict: `{"iam:AttachRolePolicy": [arn, ...], ...}` — não collapsa
   ações distintas num único campo.

**Por que isso resolve o problema da Camada 1**

Após este bloco, criar um novo lab (como Codex fez) não requer anotação manual de metadados.
O discovery computa o grafo de capacidades diretamente das policies reais.

**Critérios de saída**

1. `_compute_capability_graph` substitui `_compute_data_resource_access` e cobre todos os tipos acima
2. Lab do Bloco 6d (create_access_key_pivot) rodado sem `createkey_by` no fixture — derivado automaticamente
3. Lab do Bloco 5 (terraform-realistic-iam) com `mutable_by` correto para os 5 users
4. 288+ testes passando, sem regressão

---

### Bloco 8 — Tool Effects Declarativos

**Direcao**: tools declaram seus efeitos; executor para de ser o repositório de conhecimento de ataque.
**Objetivo**: adicionar um novo tool = escrever um YAML. Sem mudança de código no executor.

**O problema hoje**

`_execute_iam_create_access_key`, `_execute_ssm_read_parameter` (com detecção de credencial),
`_execute_s3_read_sensitive` — cada um tem lógica hardcoded para:
- detectar se o output contém credenciais
- criar um `synthetic_actor` com a chave correta
- armazenar em `_credentials_by_actor`
- registrar rollback

Para cada novo tool com efeito de pivot, alguém precisa escrever esse handler no executor.

**O que implementar**

Adicionar seção `produces:` nos YAMLs de tools:

```yaml
# iam_create_access_key.yaml
produces:
  - effect: synthetic_actor
    condition: success == true
    actor_key_template: "extracted://iam_user/{parameters.user_arn}"
    credential_source: response.credentials
    rollback:
      op: delete_access_key
      params: [parameters.user_arn, response.access_key_id]

# ssm_read_parameter.yaml
produces:
  - effect: synthetic_actor
    condition: response.credential_extracted == true
    actor_key_template: "extracted://{parameters.parameter_arn}"
    credential_source: response.extracted_credentials
```

O executor passa a ter um `_apply_produces(tool_yaml, action, result)` genérico que:
1. Lê `produces:` do YAML do tool
2. Avalia a `condition`
3. Cria o `synthetic_actor` com o template
4. Armazena em `_credentials_by_actor`
5. Registra rollback se declarado

**Por que isso resolve o problema da Camada 3**

Após este bloco, um novo tool com efeito de pivot requer apenas o YAML.
O executor não precisa crescer. O `BlindRealRuntime.observe_real` também pode
ser generalizado para ler `produces:` em vez de checar `action.tool in (lista hardcoded)`.

**Critérios de saída**

1. `_apply_produces` implementado no executor, lendo `produces:` do YAML
2. Handlers hardcoded de create_access_key, ssm_read_parameter, s3_read_sensitive,
   secretsmanager_read_secret removidos — substituídos por declaração no YAML
3. `observe_real` usa `produces:` para registrar synthetic actors
4. 288+ testes passando, sem regressão

---

### Bloco 9 — Graph Traversal Hypothesis Engine

**Direcao**: hipóteses derivadas por traversal de grafo, não por funções por padrão.
**Objetivo**: dado o capability graph (Bloco 7), o engine encontra todos os caminhos
possíveis por BFS — sem funções específicas por classe de ataque.

**O problema hoje**

```python
_derive_credential_pivot_hypotheses()   # para secret/SSM/S3
_derive_create_access_key_hypotheses()  # para iam:CreateAccessKey
_derive_hypotheses_from_snapshot()      # para IAM direto
_derive_credential_access_hypotheses()  # para leitura direta de secret
```

Cada nova classe de ataque requer uma nova função de derivação.

**O que implementar**

Um `CapabilityGraph` formal com três tipos de nó e dois tipos de aresta:

```
Nós:
  IdentityNode(arn)          — principal (user, role, extracted)
  ResourceNode(arn, type)    — recurso (secret, ssm, s3, role)
  StateNode                  — estado abstrato (e.g. "holds_credentials_for X")

Arestas (derivadas do Bloco 7):
  CanRead(identity → resource)           — via readable_by
  CanMutate(identity → resource, action) — via mutable_by
  CanCreateKey(identity → user)          — via createkey_by
  CanAssume(identity → role)             — via trust_principals + assumable_by
  ProducesActor(resource → identity)     — quando resource contém credenciais
```

`derive_all_hypotheses(graph, entry_identities, objectives)`:
- BFS/DFS de cada entry identity
- Cada traversal de aresta = um passo da chain
- Caminho que termina em `CanAssume(X → objective_role)` = hipótese válida
- Retorna hipóteses com `path: list[Step]` completo — não só entry + target

**Por que isso resolve o problema da Camada 2**

Após este bloco, um novo vetor de ataque = um novo tipo de aresta no grafo.
Não requer nova função de derivação. O engine encontra caminhos que atravessam
qualquer combinação de serviços e permissões — incluindo chains de 3+ saltos.

**Dependência**: Bloco 7 (capability graph completo) deve estar fechado.

**Critérios de saída**

1. `CapabilityGraph` construído a partir do discovery snapshot
2. `derive_all_hypotheses` substitui as 4 funções `_derive_*` atuais
3. Lab do Bloco 6d (3 cenários) com hipóteses geradas por traversal sem funções hardcoded
4. Lab do Bloco 5 (5 users, empresa simulada) com hipóteses corretas por traversal
5. 288+ testes passando

---

### Bloco 10 — Execução por Caminho

**Direcao**: executor segue o caminho da hipótese, não o template do profile.
**Objetivo**: o profile deixa de ser o repositório de conhecimento de ataque.
O executor recebe um `path: list[Step]` e o executa passo a passo.

**O problema hoje**

`BlindRealRuntime` tem métodos específicos por profile:
`_pivot_ssm_read_actions`, `_pivot_s3_read_actions`, `_create_access_key_actions`, etc.
Cada profile tem uma lógica de enumeração diferente — a superfície de ação disponível
depende de qual profile está ativo, não do estado atual da execução.

**O que implementar**

O caminho completo da hipótese (Bloco 9) é injetado na execução:

```python
plan["path"] = [
  Step(actor=entry_arn, tool="ssm_read_parameter", resource=param_arn),
  Step(actor="extracted://...", tool="iam_passrole", resource=role_arn),
]
```

`BlindRealRuntime.enumerate_actions` passa a derivar as ações disponíveis do próximo
passo pendente no path, em vez de chamar um método por profile:

```python
def enumerate_actions(self, state):
    next_step = self._next_pending_step(state)
    if next_step:
        return [self._step_to_action(next_step, state)]
    return []  # sem path pendente = sem ações
```

O executor torna-se um "path follower" — inteligente sobre estado (detecta se precondições
foram atendidas, se um passo falhou e precisa de alternativa), mas não precisa conhecer
o semântico de cada profile.

**Dependência**: Blocos 8 e 9 devem estar fechados.

**Critérios de saída**

1. `BlindRealRuntime.enumerate_actions` deriva ações do path, não do profile
2. Métodos `_pivot_*_actions` e `_create_access_key_actions` removidos
3. Bloco 6d (3 cenários), Bloco 5 (5 users) e Bloco 2 (IAM privesc) ainda passam
4. Novo cenário arbitrário rodado sem nenhuma adaptação de código além de YAML de tool
5. 288+ testes passando

---

### Bloco 11 — Governanca Real: Deny Explicito, Boundary, Trust Policy (EM ANDAMENTO, iniciado 2026-08-04)

**Direcao**: correcao antes de expansao. Regua revisada (2026-08-04): o criterio de
sucesso deixa de ser so "prova um caminho de forma auditavel" e passa a ser
"raciocina corretamente sobre a governanca real de uma conta AWS complexa". Um
caminho que o engine reporta mas que a propria AWS ja bloquearia nao e uma prova,
e um erro de modelagem — essa classe de erro vale mais consertar do que qualquer
cobertura de servico nova.

**O problema diagnosticado**

`_principal_has_capability` (Bloco 7) so olhava para statements `Effect=Allow` —
nunca cruzava com um `Effect=Deny` do mesmo principal cobrindo a mesma
action+resource. Um guardrail de Deny explicito coexistindo com um Allow amplo
(`iam:*`) era ignorado silenciosamente: falso positivo.

`assumable_by` (usado para popular arestas `CanAssume` no CapabilityGraph) era
computado *so* a partir da permission policy do principal candidato — nunca
cruzava com o `trust_principals` da propria role, que ja e coletado no discovery
desde o Bloco 7 mas nunca foi consultado pelo `_compute_capability_graph`. Um
principal com `sts:AssumeRole` amplo na propria policy, mas que a role alvo nao
lista no trust policy, virava uma hipotese de role-chaining que nao existe de
verdade em AWS real — a classe exata de falso positivo que a regua deste
documento marca como "sinal de confianca inflada", nao progresso.

`permissions_boundary_arn` era coletado no discovery (metadata de toda role) e
descartado — nao entrava em nenhum calculo de capacidade.

**O que foi implementado nesta fatia**

1. `_principal_has_capability` (`src/operations/discovery.py`) agora aplica a
   regra de precedencia que a propria AWS aplica: um `Deny` que cobre a mesma
   action+resource sempre vence um `Allow`, checado contra a identity policy e,
   quando resolvida, contra a boundary policy.
2. `_fetch_boundary_policy_permissions` busca o documento da permission boundary
   (mesmo mecanismo de `_fetch_policy_permissions`, reaproveitado) quando a
   boundary e customer-managed. Cada role passa a carregar `boundary_visibility`
   (`no_boundary` / `resolved` / `unresolved`) — quando a boundary existe mas nao
   e resolvivel (ex.: AWS-managed), isso fica visivel no snapshot em vez de
   silenciosamente assumido como "sem restricao".
3. `assumable_by` agora exige *os dois* sinais: permission policy do candidato
   E trust policy da role (`_trust_policy_allows_principal`), cobrindo `"*"`,
   ARN exato, e `:root`/account-id (confianca no nivel de conta). `trust_principals`
   ausente do metadata (fixture parcial) preserva o comportamento anterior
   (fallback permissivo, so a permission policy decide) — `trust_principals=[]`
   (discovery rodou e nao achou nenhum principal AWS, ex. role so-servico) nega.
4. `_extract_trust_principals` passa a ignorar statements `Effect=Deny` do trust
   policy (nao contam mais como principal confiavel).

**Fatia 2 (2026-08-04) — SCP visibility (so leitura, nao entra na computacao ainda)**

`AwsClient.list_service_control_policies(account_id)` busca os SCPs anexados
*diretamente* na conta via Organizations (`list_policies_for_target` +
`describe_policy`), best-effort — qualquer excecao (sem `organizations:*`,
conta fora de uma Org, sem trusted access) degrada para `None`, nunca para
"lista vazia". O snapshot ganha `governance.scp_visibility`:
`"directly_attached_only"` (vimos os SCPs da conta, mas nao os herdados de
OUs/root acima na hierarquia) ou `"unknown"` (nao resolvivel).

Decisao deliberada: os SCPs coletados **ainda nao entram** em
`_principal_has_capability`. Diferente de boundary policy, SCP tem semantica
de baseline "Allow all" (a policy AWS-managed `FullAWSAccess` por padrao) que
so e restringida por Deny/`NotAction` — tratar SCP como "precisa de Allow
explicito" do mesmo jeito que a boundary produziria falso negativo sistematico
sempre que so guardrails de Deny estivessem anexados sem um Allow-all
explicito visivel. Fazer isso direito exige (a) resolver a hierarquia de OUs
(`list_parents` recursivo, que a credencial de entry point tipicamente nao
tem) e (b) modelar o baseline Allow-all separado de Deny/`NotAction` — isso e
trabalho do avaliador de politica do Bloco 12, nao uma extensao pontual de
`_principal_has_capability`. Expor os SCPs no snapshot sem fingir que ja
influenciam o grafo e a opcao honesta: visibilidade antes de enforcement.

**Fatia 3 (2026-08-04) — Boundary em `identity.user`**

Mesmo mecanismo da role, estendido para user: `AwsClient.get_user_permissions_boundary`
(via `iam:GetUser`) busca o ARN, e `_fetch_boundary_policy_permissions` (ja existente,
reaproveitado sem mudanca) resolve o conteudo quando customer-managed. Diferença
deliberada em relação ao caminho de role: `get_role_details` é uma chamada
obrigatória (se falha, o discovery do role inteiro falha), enquanto
`get_user_permissions_boundary` é **opcional e best-effort** (getattr-defensivo) —
então `boundary_visibility` do user distingue três casos, não dois: `unresolved`
quando o cliente não implementa a chamada OU ela levanta exceção (nunca vira
"sem boundary" por omissão), `no_boundary` só quando o cliente confirma
positivamente a ausência, `resolved` quando o conteúdo foi buscado.

**Escopo explicitamente deixado de fora desta fatia** (nao esconder atras de "feito"):

- SCP como fator do calculo de `assumable_by`/`mutable_by`/etc — pendente, depende do Bloco 12
- SCP herdado de OUs/root (so vemos o diretamente anexado a conta)
- Cross-account de verdade (trust principal de outra conta que a discovery nao
  enumerou) — exige discovery multi-conta ou leitura de Organizations; hoje
  esses principals simplesmente nao aparecem no `principals` loop e por isso
  nunca geram aresta (nem falso positivo, nem cobertura real).
- `Condition` do trust policy (ex. `aws:PrincipalOrgID`, external ID) — ainda
  nao influencia `_trust_policy_allows_principal`.

**Criterios de saida (parcial)**

1. ~~`_principal_has_capability` respeita precedencia de Deny (identity + boundary)~~ DONE
2. ~~`assumable_by` exige trust policy E permission policy~~ DONE
3. ~~SCP visibility no snapshot (`governance.scp_visibility`), best-effort~~ DONE
4. ~~Boundary em `identity.user` resolvida com a mesma honestidade de sinal~~ DONE
5. ~~361 testes passando, sem regressao (341 base + 20 novos)~~ DONE
6. SCP incorporado ao calculo de capacidade — pendente, depende do Bloco 12
7. Revalidar os 6 chains do acme_showcase em AWS real com o novo `assumable_by`
   mais restrito (nenhum falso negativo esperado, mas nao revalidado ainda)

**Proximo experimento de maior leverage**

O que resta do Bloco 11 (SCP herdado de OU/root, cross-account real, `Condition`
de trust policy) todos convergem para a mesma necessidade: um avaliador de
politica de verdade, que e o proprio Bloco 12. Revalidar acme_showcase/Bloco 5
contra o `assumable_by` mais restrito em AWS real segue como validacao pendente
(precisa de credenciais/infra que essa sessao nao tem) — registrar como o
primeiro teste a rodar antes de declarar Bloco 11 fechado.

---

### Bloco 12 — PolicyEvaluator: avaliação determinística de política (INICIADO, 2026-08-04)

**Direcao**: camada de prova graduada — nem toda hipótese precisa de mutação real
pra ganhar confiança, mas nenhuma ganha confiança por afirmação do LLM.

**O que foi implementado**

`src/core/policy_evaluator.py` — módulo novo, puro, sem I/O, sem dependência de
`discovery.py`/`capability_graph.py` (é o contrário: `capability_graph.py` importa
dele). Avalia Action+Resource+Condition contra um conjunto de statements com a
semântica real de precedência da AWS:

- `evaluate_scope(statements, action, resource_arn, context)` — uma camada
  isolada (identity, boundary ou SCP). Retorna `Allow` / `Deny` / `NoMatch` +
  qual statement decidiu + `certain` (False quando um operador de Condition não
  suportado apareceu em qualquer statement que casou Action+Resource — nesse
  caso o statement nunca decide o resultado, mas a incerteza propaga em vez de
  ser ignorada).
- `evaluate_effective_access(identity, boundary, scp, action, resource_arn)` —
  combina as três camadas. `boundary=None`/`scp=None` (não resolvida) não
  restringe — mesma regra do Bloco 11. SCP só contribui `Deny`: ausência de
  Allow no SCP não bloqueia, porque o baseline real de uma conta é a policy
  AWS-managed `FullAWSAccess` salvo substituição explícita, e este avaliador
  não resolve a hierarquia de OUs pra saber se isso foi substituído — tratar
  SCP como "precisa de Allow explícito" geraria falso negativo sistemático.

Wildcard de Action/Resource é glob completo (`*`/`?` em qualquer posição, não só
sufixo — `_action_grants_read` do Bloco 7 só cobria sufixo). `NotAction`/`NotResource`
suportados. Condition: `StringEquals`, `StringNotEquals`, `StringLike`,
`StringNotLike`, `ArnLike`, `ArnEquals`, `ArnNotLike`, `Bool`, `Null` — qualquer
outro operador (`Date*`, `IpAddress`, `Numeric*`, `ForAllValues`/`ForAnyValue`,
sufixos `*IfExists`) marca `certain=False` em vez de fingir que avaliou.

**Integração**: `CapabilityGraph` ganhou `evaluation_tier` em cada `AttackHypothesis`
(`AttackHypothesis.evaluation_tier: "structural" | "evaluated"`, default
`"structural"`). No `build()`, o grafo passa a guardar `policy_permissions` +
`boundary_policy_permissions` por principal real e `governance.scp_policies` do
snapshot. Em `_path_to_hypothesis`, o **primeiro passo** do path (sempre a partir
do `entry_arn`, uma identidade real — garantido por `_traverse`) é avaliado pelo
`PolicyEvaluator`; se `allowed and certain`, a hipótese é promovida a `evaluated`.

**Escopo explicitamente deixado de fora** (não esconder atrás de "feito"):

- Só o primeiro passo do path é avaliado. Passos seguintes de um pivot (ex.:
  `credential_pivot`, `s3_pivot`) partem de identidades sintéticas
  (`extracted://...`) sem `policy_permissions` própria no discovery — avaliar
  isso exigiria resolver qual principal real a credencial extraída realmente
  corresponde, o que o engine não modela hoje.
- Resource-based policy (bucket policy, key policy, secret resource policy) —
  discovery não coleta esses documentos ainda; o parâmetro existe na assinatura
  de `evaluate_effective_access` pra quando existir, mas não é usado.
- Hierarquia de OU/root pra SCP — mesma limitação já registrada no Bloco 11.
- `_principal_has_capability`/`_statements_grant` em `discovery.py` (a camada
  grossa que popula `readable_by`/`assumable_by`/etc, usada pra achar hipóteses
  candidatas) **não foi substituída** pelo `PolicyEvaluator` — continua com
  wildcard só-sufixo e sem `Condition`. Decisão deliberada: são consultas
  diferentes (classe de actions × 1 principal × todos os recursos, vs. 1 action
  exata × 1 recurso × 1 principal) e trocar a primeira por N chamadas do
  avaliador por par (principal, recurso) tem custo quadrático sem necessidade —
  o grafo continua servindo pra achar candidatos, o avaliador serve pra
  confirmar o candidato mais promissor. Reavaliar se isso virar gargalo real.

**Critérios de saída (parcial)**

1. ~~`PolicyEvaluator` com wildcard completo, NotAction/NotResource, Condition~~ DONE
2. ~~34 testes puros do avaliador (`tests/test_policy_evaluator.py`, arquivo
   próprio — primeiro passo do Bloco 17, quebrar o monólito por domínio)~~ DONE
3. ~~`evaluation_tier` em `AttackHypothesis`, integrado ao `CapabilityGraph`~~ DONE
4. ~~`evaluation_tier` propagado até `target_candidates.json`, com bônus de
   score (+10, menor que priv_bonus — desempata, não sobrepõe confidence)~~ DONE
5. ~~401 testes passando, sem regressão (361 base + 40 novos)~~ DONE
6. Report Engine (MD/HTML final, pós-execução) expor `evaluation_tier` — pendente
7. SCP incorporado ao cálculo de `assumable_by`/etc em `discovery.py` — ainda
   não decidido se vale a pena dado o item de escopo acima
8. Avaliar segundo/terceiro passo de paths de pivot (resolver identidade
   sintética → principal real) — pendente, maior escopo

**Validação em AWS real (2026-08-04) — acme_showcase relançado via Terraform**

Reaplicado `terraform-realistic-iam/acme_showcase_real` (estava destruído desde a
última demo) contra a conta de lab real (`550192603632`), com `planner_config`
forçado pra `mock` (backend determinístico — sem chave de LLM nesta sessão; BFS +
PolicyEvaluator não dependem de LLM de qualquer forma) e rodado
`assessment run --discovery-driven --bundle aws-iam-heavy` de verdade, com
`RASTRO_ENABLE_AWS_REAL=1`. Isso expôs **dois bugs reais**, ambos corrigidos e
cobertos por teste de regressão nesta mesma sessão:

1. **Merge de hipóteses mascarava evaluation_tier.** `_derive_hypotheses_from_snapshot`
   (a função legada que Bloco 9 deveria ter aposentado) rodava ANTES do
   `CapabilityGraph` BFS na Fase 1 de `run_discovery_driven_assessment`, e o dedup por
   `(entry, target, profile_family)` mantém a primeira ocorrência — então a versão
   legada (sempre `evaluation_tier: structural`, nunca passa pelo `PolicyEvaluator`)
   vencia silenciosamente sempre que colidia com a hipótese do grafo no mesmo alvo.
   Confirmado ao vivo: `iam_privesc`/`role_chain` sempre `structural`, `s3_pivot`/
   `iam_create_access_key_pivot` (que a legada não cobre) corretamente `evaluated`.
   **Fix**: inverter a ordem — grafo primeiro, legado só preenche o que sobrar
   (`src/operations/service.py`). Teste de regressão:
   `test_discovery_driven_graph_hypothesis_wins_dedup_over_legacy_and_keeps_evaluation_tier`.
2. **PolicyEvaluator não tolerava o sufixo aleatório do Secrets Manager.**
   `_resource_covers_arn` (discovery.py, o matching grosso do Bloco 7) já tinha essa
   tolerância; `policy_evaluator.py` (Bloco 12) não replicou — toda hipótese de
   `credential_pivot`/`credential_access_direct` via Secrets Manager ficava presa em
   `structural` porque o statement da policy real usa o ARN COM sufixo
   (`...deploy-creds-VzNv2I`) e o discovery guarda o ARN sem sufixo. **Fix**: mesma
   regra replicada em `_resource_pattern_matches` (`src/core/policy_evaluator.py`).

Depois dos dois fixes: **20/20 hipóteses geradas pelo grafo BFS chegam como
`evaluated`** (antes: só 9/20 — s3_pivot e create_access_key_pivot). 3 campanhas
provadas com mutação real + rollback (`aws-credential-pivot-s3`,
`aws-credential-pivot`, `aws-credential-pivot-ssm`) usando o planner mock
determinístico — o BFS + PolicyEvaluator não precisaram de LLM em nenhum momento.

**Achado novo, não corrigido nesta sessão**: o corte `hypotheses[:max_hypotheses]`
(padrão 20) em `run_discovery_driven_assessment` não é ordenado por score/
`evaluation_tier`/confidence antes de truncar — é ordem de iteração pura. Com os
dois fixes acima o grafo passou a gerar 25 hipóteses cruas pro acme_showcase (mais
do que antes, já que menos coisa se perde no dedup/matching), e isso empurrou
`iam_attach_role_policy_privesc` (cicd-agent → ops-role, confirmado `evaluated`)
pra fora do corte de 20 — mesmo sendo uma hipótese de alta confiança e já avaliada.
O bônus de score do `evaluation_bonus` (+10) que já existe em
`_hypotheses_to_candidates_payload` nunca chega a atuar sobre essa hipótese porque
o corte acontece ANTES dela virar candidato. Vale ordenar por
`(evaluation_tier, confidence)` antes do slice, ou subir `max_hypotheses` pro
bundle `aws-iam-heavy` — não decidido ainda qual.

**As duas frentes acima foram fechadas em seguida (2026-08-04):**

1. ~~Corte de `max_hypotheses` sem prioridade~~ DONE — `run_discovery_driven_assessment`
   agora ordena (`evaluated` antes de `structural`, depois por `confidence`) com sort
   estável antes do `[:max_hypotheses]`. Teste de regressão reproduz exatamente o caso
   achado ao vivo (entry alfabeticamente anterior sem policy_permissions vs. entry
   posterior com policy_permissions reais).
2. ~~`evaluation_tier` exposto até o artefato final~~ DONE — em vez de mexer no
   `ReportGenerator` (que não conhece a hipótese de origem), o campo foi propagado pela
   cadeia que já existia: `signals.evaluation_tier` no candidato → `plan["signals"]` →
   `CampaignResult.evaluation_tier` (novo campo) → `AssessmentFinding.evaluation_tier`
   (novo campo), com linha nova em `assessment_findings.md`. 406 testes passando (+2).

**Próximo experimento de maior leverage**

Bloco 12 está com o essencial fechado: avaliador determinístico, integrado ao grafo,
validado contra AWS real com 2 bugs achados e corrigidos, e visível do início ao fim
do pipeline (hipótese → candidato → plano → campanha → finding). O que resta dentro
do próprio Bloco 12 (avaliar 2º/3º passo de paths de pivot, resource-based policy) é
escopo maior, não urgente. Os próximos blocos que fazem mais sentido agora: **Bloco 10**
(execução por caminho — o próprio projeto já tinha isso como próximo antes deste desvio
pro 11/12) ou revisitar o **Bloco 14** (deriva + verificação de remediação) do roadmap
reformulado, já que a base determinística pra sustentar isso está bem mais sólida agora
do que estava quando o roadmap foi desenhado.

---

### Bloco 10 — Execução por Caminho (FEITO — escopo reduzido, 2026-08-04)

**Direção**: executor segue o caminho da hipótese, não o template do profile.

**O que foi implementado**

Descoberta ao implementar: `AttackHypothesis` nunca carregava o path estruturado —
`_path_to_hypothesis` (Bloco 9) já tinha o `path: list[_Step]` internamente, mas
colapsava tudo em `attack_steps: list[str]` (texto solto) antes de devolver a
hipótese. O executor nunca recebia dado estruturado nenhum, só o nome do profile.
Corrigido: `PathStep` (novo modelo Pydantic — step_type/actor/target/tool) e
`AttackHypothesis.path: list[PathStep]`, populado por
`CapabilityGraph._build_structured_path`, que mapeia cada passo interno pra uma
tool real de `tools/aws/*.yaml`. Se QUALQUER passo não mapear pra tool executável
(caso real: `iam:PutRolePolicy` — não existe `iam_put_role_policy_mutate.yaml`
hoje), o path inteiro fica `[]` em vez de parcial — evita travar o runtime no meio.

`path` propaga pela mesma cadeia de `signals` que `evaluation_tier` já usa
(candidato → `plan["signals"]`) até `BlindRealRuntime.build()`.
`BlindRealRuntime.enumerate_actions` agora bifurca: se `state["path"]` existe,
devolve só o próximo passo pendente (`_next_pending_step` — actor tem que estar
ativo; senão espera); `observe_real` avança `path_index` quando a action
executada bate com o passo pendente. Sem path, cai no dispatch por profile
antigo (renomeado `_enumerate_actions_by_profile`), inalterado.

**Escopo reduzido em relação ao critério original — decisão deliberada**

O critério original (`_pivot_*_actions` e `_create_access_key_actions`
REMOVIDOS) foi trocado por: path-driven é o mecanismo PRIMÁRIO pra qualquer
hipótese que vem do `CapabilityGraph` (que desde a correção do Bloco 12 já é
a fonte que ganha o dedup contra a função legada), e o dispatch por profile
antigo fica como fallback pra tudo que não tem path (hipóteses do
`target_selector` rule-based, profiles fora do que o grafo cobre —
`external_entry_*`, `compute_pivot`, etc.). Risco avaliado: remover os
métodos de profile de uma vez, numa sessão só, sem ter mapeado todo esse
segundo grupo de profiles, arriscava quebrar cobertura comprovada em AWS
real por uma reformulação que não precisava ser tudo-ou-nada. Path-driven
já é o caminho de execução real pra toda hipótese que o BFS encontra hoje.

**Critérios de saída**

1. ~~`BlindRealRuntime.enumerate_actions` deriva ações do path quando presente~~ DONE
2. `_pivot_*_actions`/`_create_access_key_actions` removidos — NÃO feito (ver acima), mantidos como fallback deliberado
3. ~~7 testes novos cobrindo path de 1 e 2 passos, path incompleto, avanço de estado, espera por actor extraído, fallback sem path~~ DONE
4. ~~Validação em AWS real (acme_showcase)~~ DONE (2026-08-05, ver abaixo)
5. 425 testes passando (413 após Bloco 10 + 12 do Bloco 14)

**Validação em AWS real (2026-08-05) — path-driven execution, lab reaplicado**

Reaplicado `acme_showcase_real` de novo (o lab tinha sido destruído entre as
sessões) e rodado `assessment run --discovery-driven` de verdade contra ele.
Três chains provadas ponta a ponta com o executor path-driven, trace exatamente
como desenhado — zero passo de exploração desperdiçado:

```
aws-credential-pivot-s3: s3_read_sensitive (batch-runner) → iam_passrole (extracted) → admin-role   PROVADO
aws-credential-pivot:    secretsmanager_read_secret (log-collector) → iam_passrole (extracted)       PROVADO
aws-iam-ssm:             ssm_read_parameter (param-reader) — leitura direta                          PROVADO
```

Duas falhas, **nenhuma causada pelo Bloco 10** (confirmado lendo o `details` de
cada observation — não é o dispatch por path que errou):

- `aws-credential-access-secret`: bloqueada por `service_not_allowed` — o
  `generated_scope.json` desse profile específico não inclui `secretsmanager`
  em `allowed_services`, mesmo o alvo sendo um secret. Gap em
  `campaign_synthesis.py`/`build_campaign_scope`, pré-existente, não relacionado
  a path-driven (o mesmo bloqueio aconteceria com o dispatch por profile antigo
  — é um gate de escopo anterior a `enumerate_actions`).
- `aws-iam-create-access-key-pivot`: `CreateAccessKey` funcionou e o rollback
  limpou certinho (confirmado: só a access key do Terraform sobrou no user
  alvo), mas o `AssumeRole` subsequente falhou 5x com `InvalidClientTokenId` —
  atraso de propagação conhecido da AWS pra access keys recém-criadas. O
  runtime path-driven não tem retry-com-espera pra esse caso (nem o dispatch
  por profile antigo tinha) — achado real, não urgente, registrado aqui pra
  não se perder.

---

### Bloco 14 — Deriva e Verificação de Remediação (FEITO, 2026-08-04)

**Direção**: proteger um ambiente é contínuo, não um assessment único.

**O que foi implementado**

`src/core/graph_diff.py` — `diff_capability_graphs(old, new) -> GraphDiff`, puro,
compara os quatro tipos de aresta (`can_read`/`can_assume`/`can_create_key`/
`can_mutate`) entre dois `CapabilityGraph` já construídos. Zero AWS, zero LLM.

`src/operations/remediation.py` — `verify_remediation(snapshot, target_principal,
proposed_policy_permissions) -> RemediationResult`. Recomputa o grafo com a
policy do principal alvo substituída pela proposta (via o mesmo
`_compute_capability_graph` do Bloco 7, em memória, sem tocar AWS) e diffa
contra o original. `remediation_effective` só é `True` se fechou pelo menos
uma aresta do principal E não abriu nenhuma aresta nova em lugar nenhum do
grafo — a pergunta que uma prova de ataque isolada nunca responde.

**Bug real achado escrevendo os testes (não em produção, mas documentado porque
é exatamente a classe de erro que este bloco existe pra evitar)**:
`_compute_capability_graph` só GRAVA um campo (`readable_by`/`assumable_by`/etc)
quando o resultado novo é não-vazio — regra desenhada pra preservar anotação
manual de fixture de teste (Bloco 7). Rodar essa função direto em cima de um
snapshot que já tem esses campos pré-computados (como um `discovery.json` real)
faz uma permissão REMOVIDA não refletir — o campo antigo fica grudado. Corrigido
com `_strip_capability_annotations` antes de recomputar os dois lados (original
E proposto) do mesmo jeito, garantindo que a comparação parte da mesma base.

Dois comandos novos de CLI: `rastro drift <old.json> <new.json>` e
`rastro verify-fix <discovery.json> <policy_proposta.json> <principal_arn>` —
ambos testados funcionalmente contra discovery.json real (não só fixture) desta
sessão: `drift` detectou corretamente as 10 arestas novas entre o snapshot antes
e depois do lab acme_showcase ser aplicado; `verify-fix` confirmou corretamente
que remover `iam:AttachRolePolicy` da policy do cicd-agent fecha exatamente
essa aresta sem abrir nenhuma outra.

**Escopo explicitamente deixado de fora**:
- Persistência de snapshots ao longo do tempo (`drift` hoje compara dois
  arquivos que o operador já tem em mãos — não há um histórico automático)
- SCP na verificação de remediação (mesma limitação do Bloco 11/12 — SCP
  ainda não entra no cálculo de capacidade)

**Critérios de saída**

1. ~~`diff_capability_graphs` testado com casos de mesa~~ DONE (6 testes)
2. ~~`verify_remediation` confirma corretamente 2+ casos, incluindo um
   cenário com a forma real do acme_showcase~~ DONE (6 testes)
3. ~~Subcomandos `rastro drift` e `rastro verify-fix`~~ DONE, validados contra
   discovery.json real, não só fixture

---

### Bloco 15 — Auditor Offline Independente (FEITO, 2026-08-05)

**Direção**: reprodutibilidade científica — código determinístico revalida
as alegações do próprio run, nunca aceita "porque o relatório disse".

**O que foi implementado**

`src/operations/audit_verifier.py` — `audit_assessment(output_dir)` reabre
`assessment.json`, `report.json` + `audit.jsonl` por campanha,
`assessment_findings.json` e `discovery.json` (quando presentes) e reverifica,
por campanha, quatro alegações sem confiar no self-report:

1. **`scope_respected`** — nenhum step usou um serviço fora de
   `execution_policy.allowed_services`, mesmo que o step tenha falhado (a
   violação em si é o que importa, não só sucesso indevido).
2. **`objective_claim_grounded`** — se `objective_met=True`, existe um step
   cujo action+observation realmente satisfaz o `success_criteria.mode`
   declarado (`assume_role_proved`/`policy_mutation_proved`/`access_proved`/
   etc.) — `None` (não reprova) quando `objective_met=False`, nunca inferido.
3. **`rollback_attempted_when_needed`** — toda mutação bem-sucedida
   (`iam_attach_role_policy_mutate`/`iam_create_policy_version_mutate`/
   `iam_create_access_key`) tem um evento `rollback_executed` correspondente
   em `audit.jsonl`.
4. **`evaluation_tier_consistent`** — recomputa o PRIMEIRO passo via
   `PolicyEvaluator` (Bloco 12) a partir do `discovery.json` real e compara
   com o `evaluation_tier` que o finding reivindica — `None` (não reprova)
   quando não há `discovery.json`/finding correspondente pra checar.

**Validado contra dados reais desta sessão, não só fixture** — rodado contra
`outputs_bloco10_14_final_validation/` (o output do assessment que validou
o Bloco 10 ao vivo): o auditor **redescobriu sozinho, sem nenhuma pista minha**,
o mesmo bug de escopo do perfil `aws-credential-access-secret`
(`service_not_allowed`) que eu tinha achado manualmente mais cedo — é a
evidência mais forte de que o auditor tem valor real, não só passa nos
próprios testes que escrevi pra ele.

**Escopo explicitamente deixado de fora**: trace journal por chamada de LLM
(prompt+resposta bruta persistida por chamada ao `StrategicPlanner`/`Planner`)
— peça separada, exige instrumentar `openai_planner.py`/
`openai_strategic_planner.py`, que esta sessão não tocou; adiado, não
esquecido.

**Critérios de saída**

1. ~~4 checagens independentes, cada uma com estado ternário honesto
   (True/False/None — nunca inferido quando não há dado suficiente)~~ DONE
2. ~~16 testes cobrindo os quatro checks + leitura ponta a ponta do layout
   real de diretório~~ DONE
3. ~~Validado contra output real de assessment (não só fixture sintética)~~ DONE
4. Trace journal de chamadas LLM — pendente, registrado acima
5. ~~Subcomando `rastro audit <output_dir>`~~ DONE, testado contra output real

---

### O que fica para depois dos Blocos 7–10

Após o salto arquitetural, o roadmap de expansão horizontal volta a fazer sentido:

- **Entry Points Externos**: EC2 IMDS, Lambda env vars, S3 público — apenas novos tipos de
  aresta no grafo (`ExposedTo(internet → resource)`). Sem mudança de arquitetura.
- **Objetivos Não-IAM**: exfiltrar dado específico como objetivo final — apenas novo tipo de
  nó destino no traversal. Sem mudança de arquitetura.
- **Multi-cloud**: Azure RBAC, GCP IAM — novos grafos, mesmo engine de traversal.

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
