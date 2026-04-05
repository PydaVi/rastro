# EXP-054 — Mixed Generalization Obfuscated Enterprise Targets

## Identificacao

- ID: EXP-054
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

Depois de `EXP-053`, o benchmark misto ja reduzia naming favorecido em pivots e
entry surfaces. O atalho mais forte restante estava nos alvos enterprise
profundos:

- `warehouse-api-key`
- `warehouse-master-api-key`

Esses nomes ainda traziam semantica de negocio demais para `cross-account` e
`multi-step`.

## Hipoteses

H1. Era possivel reduzir naming favorecido nos alvos enterprise profundos sem
quebrar o benchmark ponta a ponta.

H2. A separacao entre:

- `aws-cross-account-data`
- `aws-multi-step-data`

continuaria correta principalmente por estrutura, nao por naming de negocio.

## Desenho experimental

### Variavel independente

Foi criada:

- `fixtures/mixed_generalization_variant_i.discovery.json`

Mudancas principais:

- alvos enterprise profundos renomeados para:
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/ops/core-api-key`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/ops/core-master-api-key`
- remocao de `finance` e `warehouse` desses recursos finais

### Ajuste de harness

Os fixtures sinteticos mistos foram expandidos para aceitar tambem os novos
ARNs:

- `fixtures/mixed_generalization_cross_account_lab.json`
- `fixtures/mixed_generalization_multi_step_lab.json`

Sem remover suporte aos ARNs anteriores, para preservar compatibilidade com os
benchmarks anteriores.

## Resultados por etapa

### Etapa 1 — Selection

Confirmada.

Top candidates observados:

- `aws-cross-account-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/ops/core-api-key`
- `aws-multi-step-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/ops/core-master-api-key`

### Etapa 2 — Assessment discovery-driven ponta a ponta

Confirmada.

Output gerado:

- `outputs_mixed_generalization_variant_i_assessment/`

Resumo observado:

- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Nao houve falha experimental do engine neste bloco.

O cuidado principal foi de harness:

- os fixtures sinteticos mistos precisaram aceitar os novos ARNs obfuscados
  para `cross-account` e `multi-step`

## Descoberta principal

O benchmark enterprise continua estavel mesmo quando os alvos profundos deixam
de carregar naming de negocio explicito como `finance` e `warehouse`.

## Interpretacao

Esse e um ganho relevante de generalizacao ofensiva:

- `cross-account` e `multi-step` continuam corretos com menos apoio lexical de
  negocio
- a diferenciacao entre as classes passa a depender mais de:
  - estrutura da chain
  - profundidade
  - fronteira de conta

## Implicacoes arquiteturais

- o benchmark misto enterprise ficou menos dependente de naming de negocio nos
  alvos profundos
- o harness sintetico agora suporta aliases de alvos enterprise sem quebrar
  benchmarks anteriores
- isso aumenta a qualidade do benchmark como medidor de generalizacao real

## Ameacas a validade

- os alvos ainda preservam `api-key` e `master`, entao ainda existe algum apoio
  lexical
- o benchmark continua sintetico

## Conclusao

H1 e H2 confirmadas.

O benchmark misto enterprise permaneceu estavel com alvos profundos menos
evidentes semanticamente.

## Proximos passos

1. reduzir apoio lexical restante em `api-key` vs `master`
2. introduzir aliases e nomes menos explicitos tambem em recursos finais locais
   quando o harness permitir
3. seguir pressionando o selection para separar estrutura de semantica de nome
