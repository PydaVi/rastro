# EXP-045 — Mixed Generalization End-to-End

## Identificacao

- ID: EXP-045
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

Depois de `EXP-044`, o proximo passo natural era levar o benchmark misto para o
assessment discovery-driven ponta a ponta, nao apenas selection e synthesis.

## Hipoteses

H1. O benchmark misto conseguiria rodar ponta a ponta com synthesis menos
`profile-first`.

H2. Se houvesse falha, ela provavelmente estaria na camada sintetica de profile
resolution, nao no engine central.

## Desenho experimental

- snapshot: `fixtures/mixed_generalization_variant_a.discovery.json`
- bundle: `aws-enterprise`
- synthesis com `dedupe_resource_targets=True`
- execution via `execute_run`

## Resultados por etapa

### Etapa 1 — Primeira execucao ponta a ponta

Parcial.

Resultado observado:

- `campaigns_total = 8`
- `campaigns_passed = 6`
- falhas:
  - `aws-iam-s3`
  - `aws-iam-role-chaining`

### Etapa 2 — Rerun apos correcao do resolver sintetico

Confirmada.

Resultado observado em
`outputs_mixed_generalization_variant_a_assessment/assessment.json`:

- `campaigns_total = 8`
- `campaigns_passed = 8`
- `assessment_ok = true`

Campanhas executadas:

- `aws-external-entry-data`
- `aws-multi-step-data`
- `aws-iam-compute-iam`
- `aws-iam-ssm`
- `aws-iam-s3`
- `aws-iam-kms-data`
- `aws-iam-role-chaining`
- `aws-iam-lambda-data`

## Erros, intervencoes e motivos

### Causa raiz

Nao foi falha do engine de run.

Foi um gap de representacao/catalogo do ambiente sintetico:

- o assessment resolvia fixture apenas por `profile_name`
- no benchmark misto, o mesmo profile family podia existir em mais de um
  arquétipo sintetico
- o resolver escolheu fixtures do `compute-pivot-app` para campanhas cujo alvo
  e semantica estavam mais proximos de outro contexto misto

Isso fez o assessment ficar preso a:

- `profile -> fixture` fixo

quando o benchmark misto exige algo mais proximo de:

- `profile + target context -> fixture`

### Classificacao da causa

- falha de infraestrutura/catalogo sintetico: sim
- falha de representacao de estado do engine: nao
- falha de policy: nao
- falha de framing do planner: nao
- limitacao do modelo: nao

## Descoberta principal

O produto avancou em generalizacao ofensiva na selecao, mas o harness sintetico
de execucao ainda estava acoplado a resolucao fixa por profile family.

Depois da correcao, o assessment misto passou a refletir melhor o objetivo
arquitetural do bloco:

- selecao menos lexical
- synthesis menos profile-first
- execucao ponta a ponta coerente com o contexto estrutural do plano

## Implicacoes arquiteturais

- `profile_resolver` do assessment precisa aceitar contexto do plano
- campanhas sinteticas mistas precisam resolver fixture por:
  - profile
  - target resource
  - semantica estrutural do plano

## Ameacas a validade

- a falha e da camada sintetica, nao da execucao real
- o experimento ainda nao concluiu a etapa ponta a ponta apos a correcao

## Conclusao

H1 e H2 confirmadas.

Antes da correcao, o experimento revelou um drift residual importante:
- o assessment estava menos `profile-first` na selecao
- mas ainda `profile-first` demais na resolucao sintetica de fixture

Depois da correcao:
- `profile_resolver` passou a aceitar contexto do plano
- o benchmark misto passou ponta a ponta
- o Rastro ficou mais proximo de escolher e executar o caminho mais expressivo
  para o mesmo alvo, em vez de obedecer a uma associacao fixa

## Proximos passos

1. inferencia estrutural de profile sem `candidate_profiles` curado
2. mixed environment com mais de um alvo valido por mesma superficie
3. competicao real entre compute/external entry e caminhos IAM-first para o
   mesmo recurso
