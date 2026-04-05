# EXP-052 — Mixed Generalization Without Semantic Tags

## Identificacao

- ID: EXP-052
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

Depois de `EXP-051`, o benchmark misto enterprise ja derivava estrutura
ofensiva de `relationships`, mas ainda mantinha `semantic_tags` curado no
metadata dos recursos.

Essas tags ajudavam o scorer, mas ainda representavam um atalho semantico
relevante demais para um benchmark cujo objetivo e medir generalizacao.

## Hipoteses

H1. O benchmark misto poderia continuar estavel mesmo sem `semantic_tags` em
nenhum recurso.

H2. A combinacao de:

- nomes reais dos recursos
- relacoes estruturais
- qualidade dos pivots

seria suficiente para manter a selecao correta dos principais alvos enterprise.

## Desenho experimental

### Variavel independente

Foi criada:

- `fixtures/mixed_generalization_variant_g.discovery.json`

Diferencas para a Variante F:

- remocao de `semantic_tags` de todos os recursos
- manutencao da estrutura relacional:
  - `can_access`
  - `can_assume`

### Criterio

O benchmark so seria considerado valido se preservasse:

- `aws-external-entry-data`
  - `prod/payroll-api-key`
- `aws-cross-account-data`
  - `prod/finance/warehouse-api-key`
- `aws-multi-step-data`
  - `prod/finance/warehouse-master-api-key`

e se o assessment discovery-driven permanecesse com `9/9`.

## Resultados por etapa

### Etapa 1 — Selecao sem semantic tags

Confirmada.

Top candidates observados:

- `aws-external-entry-data`
  - `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key`
- `aws-cross-account-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key`
- `aws-multi-step-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-master-api-key`

### Etapa 2 — Assessment discovery-driven ponta a ponta

Confirmada.

Output gerado:

- `outputs_mixed_generalization_variant_g_assessment/`

Resumo observado:

- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Nao houve falha experimental do engine.

O bloco foi uma pressao deliberada de benchmark para medir o quanto o sistema
ja dependia menos de semantica curada.

## Descoberta principal

O benchmark misto enterprise continua estavel sem `semantic_tags` curado.

## Interpretacao

Esse resultado importa porque reduz outro apoio manual do benchmark:

- antes: semantica estrutural derivada, mas tags ainda ajudavam
- agora: nomes reais + relacoes + scoring estrutural bastam para manter os
  principais alvos corretos

Ainda existe heuristica lexical, mas ha menos metadata “explicando a resposta”.

## Implicacoes arquiteturais

- o selection ficou menos dependente de anotacao manual semantica
- os benchmarks mistos passam a medir melhor o valor real do scorer estrutural
- o caminho para discovery e target selection mais autonomos ficou mais claro

## Ameacas a validade

- continua havendo naming favoravel (`payroll`, `warehouse`, `api-key`)
- o benchmark continua sintetico
- isso nao substitui validacao real dos cenarios enterprise

## Conclusao

H1 e H2 confirmadas.

O benchmark misto enterprise manteve estabilidade ponta a ponta sem
`semantic_tags` curado.

## Proximos passos

1. continuar reduzindo dependencia de naming favorecido no benchmark misto
2. aproximar o benchmark de casos com aliases e nomes menos evidentes
3. usar esse benchmark para medir quando o scorer estrutural realmente supera o
   lexical
