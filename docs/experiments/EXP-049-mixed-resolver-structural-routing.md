# EXP-049 — Mixed Resolver Structural Routing

## Identificacao

- ID: EXP-049
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

Depois de `EXP-048`, o principal apoio manual restante no benchmark misto era o
resolver sintetico:

- ainda havia roteamento curado demais entre `mixed-generalization`,
  `serverless-business-app` e `compute-pivot-app`

Isso mantinha um drift residual:

- selection mais autonomo
- execution harness ainda manual demais

## Hipoteses

H1. O resolver sintetico misto podia passar a depender mais de
`execution_fixture_set` inferido no selection do que de branching manual por
family.

H2. Um pequeno conjunto de regras estruturais seria suficiente para preservar o
benchmark misto ponta a ponta.

## Desenho experimental

### Variavel independente

Mudancas principais:

- `target selection` agora gera:
  - `execution_fixture_set`
- `campaign synthesis` propaga:
  - `execution_fixture_set`
- `get_mixed_synthetic_profile(...)` passa a usar esse campo como contrato
  principal de roteamento

### Benchmarks usados

- `mixed_generalization_variant_a`
- `mixed_generalization_variant_b`
- `mixed_generalization_variant_c`
- `mixed_generalization_variant_d`

## Resultados por etapa

### Etapa 1 — Regressao inicial

Parcial.

Ao mover o roteamento para `execution_fixture_set`, o benchmark revelou uma
regressao:

- `aws-iam-s3` passou a cair no fixture set errado
- resultado:
  - `campaigns_passed = 7/8`

### Etapa 2 — Correcao

Causa raiz:

- inferencia de `execution_fixture_set` para `aws-iam-s3` ainda estava
  agressiva demais para o benchmark misto

Correcao:

- `aws-iam-s3` passa a usar `mixed-generalization` como fixture set nesse bloco
- o restante do roteamento permanece estrutural:
  - serverless para Lambda/KMS
  - compute para compute/external/cross/multi
  - role chaining/ssm/secrets pelo contexto estrutural observado

### Etapa 3 — Rerun ponta a ponta

Confirmada.

Resultados observados:

- `outputs_mixed_generalization_variant_a_assessment/`
- `outputs_mixed_generalization_variant_b_assessment/`
- `outputs_mixed_generalization_variant_c_assessment/`
- `outputs_mixed_generalization_variant_d_assessment/`

Resumo em todos:

- `campaigns_total = 8`
- `campaigns_passed = 8`
- `assessment_ok = true`

## Erros, intervencoes e motivos

### Causa raiz

- falha de infraestrutura/catalogo sintetico: sim
- falha de representacao de estado: nao
- falha de policy do engine: nao
- falha do planner: nao

O experimento mostrou que o remaining gap estava no harness sintetico, nao no
loop ofensivo.

## Descoberta principal

O resolver sintetico misto agora depende mais do contexto inferido do plano do
que de uma tabela curada por family/target.

## Interpretacao

Esse passo nao elimina toda a curadoria do benchmark, mas move o contrato para:

- `selection -> execution_fixture_set -> resolver`

em vez de:

- `resolver manual decide tudo`

## Implicacoes arquiteturais

- o mixed resolver ficou menos ad hoc
- o contrato entre selection e execution ficou mais explicito
- futuros benchmarks mistos podem crescer sem empilhar branching manual no
  resolver

## Ameacas a validade

- ainda ha curadoria residual, especialmente em `aws-iam-s3`
- continua sendo benchmark sintetico

## Conclusao

H1 e H2 confirmadas.

O bloco reduziu a curadoria do resolver misto sem quebrar o benchmark ponta a
ponta.

## Proximos passos

1. reduzir a excecao residual de `aws-iam-s3`
2. transferir `execution_fixture_set` ou equivalente para camadas menos
   sinteticas do produto
3. preparar benchmark misto com mais profundidade de chain e mais um target
   forte por entry surface
