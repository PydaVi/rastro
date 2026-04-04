# EXP-070 — Compute Unified Fixture Set

## Identificacao

- ID: EXP-070
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Depois de unificar `serverless-business-app`, o principal acoplamento residual
de fixture sets por familia ficou em `compute-pivot-app`.

O arquétipo ainda tinha fixtures separados para:

- S3
- Secrets
- SSM
- Role chaining
- Compute pivot
- External entry

## Hipoteses

H1. Um fixture unificado de `compute-pivot-app` pode sustentar foundation e
advanced principais sem degradar:

- compute foundation
- mixed benchmark enterprise

H2. Isso reduz a dependencia residual de fixture sets por familia no arquétipo
compute.

## Desenho experimental

### Intervencao

Foi criado:

- `fixtures/compute_pivot_app_unified_lab.json`

O catálogo sintético passou a apontar para ele nas classes:

- `aws-iam-s3`
- `aws-iam-secrets`
- `aws-iam-ssm`
- `aws-iam-role-chaining`
- `aws-iam-compute-iam`
- `aws-external-entry-data`

### Critério

1. revalidar `compute-pivot-app` foundation
2. revalidar `mixed_generalization_variant_p`

## Resultados por etapa

### Etapa 1 — Compute foundation

Confirmada.

Resultado:

- `outputs_compute_pivot_app_variant_a_assessment/`
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

Houve uma regressao inicial em `aws-external-entry-data`.

Causa raiz:

- o fixture unificado preservou o pivô publico
- mas nao atualizava a identidade alcançada com as acoes de dado

Classificacao:

- infraestrutura/harness sintético

Correcao geral:

- transicoes de `external entry` passaram a atualizar explicitamente
  `PayrollAppInstanceRole` com acoes de dado relevantes

## Descoberta principal

O arquétipo `compute-pivot-app` também já suporta consolidação de várias
classes no mesmo fixture, sem voltar a family routing rígido.

## Interpretacao

Esse bloco foi `mais generalização ofensiva`.

Ele reduz mais um atalho forte do harness e aproxima o ambiente sintético da
ideia de um workspace ofensivo com múltiplos caminhos concorrentes.

## Implicacoes arquiteturais

- foundation e advanced de compute já não dependem de fixtures por familia
- o acoplamento residual mais forte agora fica em:
  - fixtures enterprise especializados
  - principalmente `cross-account` e `multi-step`

## Ameacas a validade

- isso ainda é sintético
- `cross-account` e `multi-step` continuam especializados

## Conclusao

H1 confirmada.

H2 confirmada.

O bloco reduziu significativamente a dependência residual de fixture sets por
familia no arquétipo compute sem quebrar o benchmark enterprise.

## Proximos passos

1. consolidar formalmente o fechamento desta subfase
2. decidir entre:
   - próximo salto de generalização
   - ou promoção real seletiva com maior leverage
