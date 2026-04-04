# EXP-069 — Serverless Unified Fixture Set

## Identificacao

- ID: EXP-069
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Mesmo com menos dependencia de resolver, a camada sintética ainda carregava
fixture sets separados por familia para o arquétipo `serverless-business-app`:

- S3
- Secrets
- SSM
- Role chaining
- Lambda
- KMS

Isso mantinha curadoria residual de harness em um ambiente onde a mesma
topologia operacional podia sustentar varias classes.

## Hipoteses

H1. Um fixture unificado de `serverless-business-app` pode sustentar essas
classes sem quebrar:

- foundation discovery-driven do arquétipo
- mixed benchmark enterprise

H2. Consolidar esses paths em um fixture unificado reduz dependencia residual
de fixture sets por familia.

## Desenho experimental

### Intervencao

Foi criado:

- `fixtures/serverless_business_app_unified_lab.json`

O catálogo sintético passou a apontar para ele nas classes serverless:

- `aws-iam-s3`
- `aws-iam-secrets`
- `aws-iam-ssm`
- `aws-iam-role-chaining`
- `aws-iam-lambda-data`
- `aws-iam-kms-data`

### Critério

1. revalidar `serverless-business-app` foundation
2. revalidar `mixed_generalization_variant_p`

## Resultados por etapa

### Etapa 1 — Serverless foundation

Confirmada.

Resultado:

- `outputs_serverless_business_app_variant_a_assessment/`
- `campaigns_total = 4`
- `campaigns_passed = 4`
- `assessment_ok = true`

### Etapa 2 — Mixed enterprise

Confirmada.

Resultado:

- `outputs_mixed_generalization_variant_p_assessment/`
- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Houve uma regressao inicial.

Causa raiz:

- ao embutir `fixture_path`, o routing de `aws-iam-s3` em `serverless-business-app`
  passou a usar `mixed-generalization`
- isso nao era falha do engine
- era falha de inferencia de fixture set no contexto do arquétipo

Classificacao:

- infraestrutura/harness sintético

Correcao geral:

- `_infer_execution_fixture_set(...)` passou a respeitar o arquétipo do target
  para:
  - `serverless-business-app`
  - `compute-pivot-app`
  - `internal-data-platform`

sem colapsar o benchmark `mixed-generalization`.

## Descoberta principal

O arquétipo `serverless-business-app` ja suporta varias classes no mesmo
fixture, e o routing pode respeitar contexto do ambiente sem voltar a
`profile-first`.

## Interpretacao

Esse bloco foi `mais generalização ofensiva`.

O ganho principal foi reduzir curadoria de harness por familia dentro de um
mesmo ambiente sintetico.

## Implicacoes arquiteturais

- fixture sets por familia podem ser consolidados por arquétipo
- o proximo acoplamento residual forte agora fica mais concentrado em:
  - fixture sets de `compute-pivot-app`
  - fixture sets enterprise especializados (`cross-account`, `multi-step`)

## Ameacas a validade

- isso ainda e sintético
- nem todos os arquétipos foram unificados

## Conclusao

H1 confirmada.

H2 confirmada.

O bloco reduziu dependencia residual de fixture sets por familia no arquétipo
serverless sem quebrar foundation nem mixed enterprise.

## Proximos passos

1. avaliar unificacao semelhante em `compute-pivot-app`
2. decidir se o proximo leverage esta em consolidar compute ou promover real
