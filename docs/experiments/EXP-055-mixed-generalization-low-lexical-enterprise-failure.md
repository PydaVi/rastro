# EXP-055 — Mixed Generalization Low Lexical Enterprise Failure

## Identificacao

- ID: EXP-055
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

Depois de `EXP-054`, o passo seguinte foi reduzir ainda mais o apoio lexical dos
alvos enterprise profundos, removendo tambem:

- `api-key`
- `master`

dos nomes finais dos recursos.

O objetivo era medir se `cross-account` e `multi-step` continuariam separados
quase inteiramente por estrutura.

## Hipoteses

H1. O benchmark enterprise deveria continuar estavel mesmo com os alvos finais
renomeados para identificadores muito menos semanticos.

H2. Se houvesse falha, ela deveria isolar um limite real do harness ou do
selection, nao um problema difuso.

## Desenho experimental

### Variavel independente

Foi criada:

- `fixtures/mixed_generalization_variant_j.discovery.json`

Renomeacoes principais:

- `prod/ops/core-api-key` -> `prod/ops/core-a`
- `prod/ops/core-master-api-key` -> `prod/ops/core-b`

## Resultados por etapa

### Etapa 1 — Selection

Confirmada.

Top candidates observados:

- `aws-cross-account-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/ops/core-a`
- `aws-multi-step-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/ops/core-b`

### Etapa 2 — Assessment discovery-driven inicial

Falhou.

Resumo observado:

- `campaigns_total = 9`
- `campaigns_passed = 8`
- `campaigns_objective_not_met = 1`

Campanha afetada:

- `aws-cross-account-data`

### Etapa 3 — Correcao de harness e rerun

Confirmada.

Correcao aplicada:

- o fixture `mixed_generalization_cross_account` passou a aceitar ambos os
  aliases:
  - `prod/ops/core-api-key`
  - `prod/ops/core-a`

Isso tambem preservou compatibilidade com a variante anterior.

Output gerado:

- `outputs_mixed_generalization_variant_j_assessment/`

Resumo observado:

- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

### Causa raiz

- falha de infraestrutura/harness sintetico: sim
- falha de representacao de estado: nao
- falha de policy do engine: nao
- falha do planner: nao

Diagnostico:

- a selecao continuou correta
- `aws-multi-step-data` ja tinha fixture expandido para o alias novo
- `aws-cross-account-data` ainda nao estava completo para o alias
  `prod/ops/core-a` no ponto exato exigido pelo run sintetico

Ou seja:

- o benchmark conseguiu escolher o alvo certo
- o harness nao conseguiu provar o alvo obfuscado de `cross-account`

## Descoberta principal

Com o apoio lexical quase minimo nos alvos enterprise profundos, o primeiro
limite observado foi de harness sintetico de `cross-account`, nao de selection.

## Interpretacao

Esse resultado e util porque separa claramente duas perguntas:

1. o selection ainda escolhe certo sem `api-key` e `master`?
   - sim
2. o harness atual consegue provar imediatamente esse alias novo?
   - ainda nao, no caso de `cross-account`

## Implicacoes arquiteturais

- o scorer estrutural continua carregando boa parte do peso
- o proximo ajuste deve ser localizado no fixture de `cross-account`
- nao ha justificativa para mexer no loop ofensivo por causa desta falha

## Ameacas a validade

- continua sendo benchmark sintetico
- o bloco ainda nao prova estabilidade total apos a correcao

## Conclusao

H1 confirmada apos a correcao de harness.

H2 confirmada: a falha foi isolada como problema localizado de harness
sintetico.

O bloco ficou consolidado assim:

- `cross-account` e `multi-step` continuam corretos sem apoio lexical de
  `api-key` e `master`
- o benchmark enterprise volta a fechar `9/9`

## Proximos passos

1. reduzir ainda mais naming favorecido nos recursos finais locais quando o
   harness permitir
2. continuar expandindo suporte a aliases no harness sintetico sem quebrar
   variantes anteriores
3. medir explicitamente quando o score estrutural supera o lexical nos
   principais candidatos enterprise
