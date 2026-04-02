# Produto 01 — Discovery e Target Selection

## Objetivo

Transformar o Rastro de um executor de campanhas conhecidas em um sistema que:
- descobre recursos dentro de um escopo autorizado
- identifica alvos provaveis
- sintetiza campanhas a partir desses alvos

Sem essa camada, o Produto 01 continua dependente de fixture, objetivo e scope
predefinidos para um alvo ja conhecido.

## Problema que esta camada resolve

Hoje o Rastro prova attack paths completos, mas parte de uma premissa forte:
o operador ja sabe qual bucket, secret, parameter ou chain quer validar.

Em uma conta real isso nao e suficiente. O fluxo operacional correto precisa ser:

1. `scan controlado`
2. `selecao de alvos`
3. `sintese de campanhas`
4. `execucao e evidencia`

## Principios

- discovery nunca pode virar varredura irrestrita da conta
- toda descoberta respeita `Target` + `Authorization` + `Profile`
- target selection deve ser explicavel e auditavel
- campanhas geradas automaticamente precisam preservar o mesmo contrato de
  `scope`, `preflight`, `audit` e `report`
- resultado negativo de discovery tambem e evidencia operacional

## Camadas

### 1. Discovery

Responsavel por construir um inventario controlado do ambiente dentro do escopo.

Entradas:
- `TargetConfig`
- `AuthorizationConfig`
- `ProfileDefinition`

Saida:
- `DiscoverySnapshot`

Conteudo esperado do `DiscoverySnapshot`:
- identidades observadas
- roles assumiveis
- trusts relevantes
- buckets e objetos relevantes
- secrets
- parameters
- funcoes Lambda
- instancias/perfis de instancia
- chaves KMS
- relacoes entre recursos e principals

Regras:
- sem fetch fora de `allowed_regions`
- sem recursos fora de `accounts`
- servicos limitados pelo `Profile`
- tudo com timestamp e origem da evidencia

### 2. Resource Classification

Responsavel por classificar recursos descobertos em tipos operacionais.

Exemplos:
- `data_store.s3_bucket`
- `data_store.s3_object`
- `secret.secrets_manager`
- `secret.ssm_parameter`
- `identity.role`
- `compute.instance_profile`
- `compute.lambda_role`
- `crypto.kms_key`

Essa camada existe para desacoplar enumeracao bruta de selecao de alvo.

### 3. Target Selection

Responsavel por ranquear candidatos de alvo por profile.

Saida:
- `TargetCandidate[]`

Cada `TargetCandidate` deve carregar:
- `resource_arn`
- `resource_type`
- `profile_family`
- `selection_reason[]`
- `signals`
- `score`
- `confidence`

Exemplos de sinais:
- nome sugestivo: `payroll`, `prod`, `finance`, `secret`, `token`
- tags: `classification=confidential`, `environment=prod`
- politica associada
- relacao com roles assumiveis
- presenca em superfícies de alto valor

Target selection nao escolhe o path. Escolhe o alvo.

### 4. Campaign Synthesis

Responsavel por transformar `ProfileDefinition + TargetCandidate` em campanha executavel.

Saida:
- `CampaignPlan`

Cada `CampaignPlan` deve conter:
- `profile`
- `target_candidate`
- `generated_objective`
- `generated_scope`
- `expected_services`
- `entry_principals`
- `safety_constraints`

Exemplo:
- profile: `aws-iam-secrets`
- alvo: `arn:aws:secretsmanager:...:secret:prod/payroll-api-key`
- objective gerado: acesso controlado ao secret
- scope gerado: somente roles, regions e services necessarios para provar o path

### 5. Assessment Orchestration

Responsavel por decidir quais campanhas serao executadas em um assessment.

Fluxo:
- carregar profiles do bundle
- executar discovery por familia relevante
- gerar `TargetCandidate[]`
- limitar quantidade por profile
- gerar campanhas
- executar campanhas
- consolidar resultados

## Fluxo operacional alvo

```text
Target + Authorization + Bundle
  -> Discovery
  -> Resource Classification
  -> Target Selection
  -> Campaign Synthesis
  -> Preflight
  -> Campaign Execution
  -> Assessment Consolidation
```

## Contratos propostos

### DiscoverySnapshot

Campos minimos:
- `target`
- `bundle`
- `collected_at`
- `services_scanned`
- `regions_scanned`
- `resources`
- `relationships`
- `evidence`

### TargetCandidate

Campos minimos:
- `id`
- `resource_arn`
- `resource_type`
- `profile_family`
- `score`
- `confidence`
- `selection_reason`
- `supporting_evidence`

### CampaignPlan

Campos minimos:
- `profile`
- `target_candidate_id`
- `objective_path` ou `generated_objective`
- `scope_path` ou `generated_scope`
- `priority`
- `planned_services`

## Heuristicas iniciais de selecao

Primeiro corte deve ser simples e explicavel.

### Foundation

**IAM -> S3**
- priorizar buckets/objetos com nomes sensiveis
- priorizar buckets privados com nomes `prod`, `finance`, `backup`, `payroll`

**IAM -> Secrets**
- priorizar secrets com prefixos `prod/`, `payroll/`, `finance/`, `token/`

**IAM -> SSM**
- priorizar parameters `SecureString`
- priorizar namespaces `prod/`, `app/`, `finance/`

**IAM -> Role chaining**
- priorizar roles com trust chain observavel e acesso subsequente a dado

## Guardrails

- limite maximo de recursos por service no discovery inicial
- limite maximo de candidatos por profile
- discovery e target selection precisam gerar artefato proprio
- selecao automatica nunca pode escapar do escopo autorizado
- qualquer heuristica precisa registrar o motivo da pontuacao

## Artefatos novos do Produto 01

Primeiro corte desta camada deve gerar:
- `discovery.json`
- `discovery.md`
- `target_candidates.json`
- `campaign_plan.json`

Esses artefatos entram antes do `assessment.json`.

## Escopo do primeiro corte

O primeiro corte nao precisa resolver tudo.

Ele precisa:
- funcionar para `aws-foundation`
- cobrir S3, Secrets, SSM e role chaining
- produzir poucos candidatos bons e auditaveis
- gerar campanhas automaticamente a partir do discovery

Ele ainda nao precisa:
- priorizacao por risco financeiro
- ML ou ranking sofisticado
- correlacao cross-account complexa
- descoberta enterprise em larga escala

## Backlog recomendado

### Bloco 1 — Discovery foundation
- inventario controlado de S3, Secrets, SSM e IAM roles
- snapshot persistido em artefato proprio

### Bloco 2 — Target selection foundation
- ranking heuristico simples por classe
- justificativa auditavel por candidato

### Bloco 3 — Campaign synthesis foundation
- gerar `scope` e `objective` automaticamente para cada candidato
- integrar ao `assessment run`

### Bloco 4 — Assessment discovery-driven
- executar bundle a partir de discovery real, sem objetivo manual
- consolidar candidatos nao explorados e campanhas descartadas

## Definicao de pronto

Essa camada estara pronta quando:
- `assessment run --bundle aws-foundation` puder operar sem fixture manual de alvo
- o sistema descobrir recursos reais dentro do escopo
- o sistema selecionar alvos de forma explicavel
- o sistema gerar campanhas automaticamente
- a consolidacao final mostrar: recursos descobertos, candidatos gerados,
  campanhas executadas e cobertura alcancada
