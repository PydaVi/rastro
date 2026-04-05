# EXP-060 — Mixed Generalization Generic Fixture Aliases

## Identificacao

- ID: EXP-060
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Depois de `EXP-059`, o proximo gap mais claro era a curadoria manual residual
de aliases nos fixture sets mistos.

Objetivo:

- reduzir a necessidade de duplicar `available_actions` e `transitions` para
  cada alias novo
- tornar o harness sintetico menos curado manualmente sem perder estabilidade
  ponta a ponta

## Hipoteses

H1. O `Fixture` deveria conseguir expandir aliases de target de forma genérica
na enumeracao e na execucao.

H2. Com isso, seria possivel abrir uma nova variante mista com menos edicoes
manuais nos fixture sets.

## Desenho experimental

### Intervencao estrutural

Foi adicionado suporte generico a aliases no `Fixture`:

- `src/core/fixture.py`

Capacidades novas:

- expandir `available_actions` a partir de `aliases`
- canonicalizar `target` e `parameters` no matching de transicoes
- derivar aliases de:
  - `secret_id`
  - `parameter`
  - `s3 bucket/object key`

### Variavel independente

Foi criada:

- `fixtures/mixed_generalization_variant_o.discovery.json`

Novos aliases de baixo valor semantico:

- local secret:
  - `prod/r/a1`
- deep targets enterprise:
  - `prod/r/e1`
  - `prod/r/e2`

Fixture sets atualizados apenas com `aliases` top-level:

- `fixtures/serverless_business_app_iam_secrets_lab.json`
- `fixtures/compute_pivot_app_external_entry_lab.json`
- `fixtures/compute_pivot_app_iam_secrets_lab.json`
- `fixtures/mixed_generalization_cross_account_lab.json`
- `fixtures/mixed_generalization_multi_step_lab.json`

## Resultados por etapa

### Etapa 1 — Teste unitario do alias engine

Confirmada.

O `Fixture` passou a:

- enumerar action com target alias
- ajustar `parameters.secret_id` junto com o alias
- casar a execucao com a transicao canonica

### Etapa 2 — Selection

Confirmada.

Selecao observada na variante O:

- `aws-iam-secrets`
  - `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/r/a1`
- `aws-cross-account-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/r/e1`
- `aws-multi-step-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/r/e2`

### Etapa 3 — Assessment discovery-driven

Confirmada.

Resultado observado:

- `outputs_mixed_generalization_variant_o_assessment/`
- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Houve uma falha inicial apenas no teste unitario novo.

### Causa raiz

- falha de infraestrutura/harness sintetico: sim
- falha de engine ofensivo: nao

Diagnostico:

- a canonicalizacao reversa ainda nao incluia os derivados de alias
  (`secret_id`, `parameter`, `s3 bucket/object key`)
- isso fazia a action alias casar na enumeracao, mas nao na execucao

### Correcao

`_reverse_alias_map()` foi expandido para incluir tambem os derivados produzidos
por `_derived_replacements(...)`.

## Descoberta principal

O harness sintetico pode ficar menos curado manualmente sem perder controle
deterministico, desde que o suporte de alias exista na camada do `Fixture`.

## Interpretacao

Esse bloco melhora a qualidade do benchmark misto sem empurrar complexidade
especifica para cada fixture set.

O ganho mais importante nao foi um alias novo em si, mas a reducao do custo
arquitetural para continuar removendo naming favorecido.

## Implicacoes arquiteturais

- novos aliases deixam de exigir duplicacao sistematica de actions/transitions
- o mixed benchmark pode continuar pressionando naming desfavoravel com menos
  curadoria manual
- o suporte generico de alias reduz um sinal explicito de drift para
  `campaign validator`

## Ameacas a validade

- continua sendo harness sintetico
- alias support ainda depende de relacoes canonicas bem definidas por fixture

## Conclusao

H1 confirmada.

H2 confirmada.

O bloco empurrou o produto para mais generalizacao ofensiva ao reduzir um
atalho manual do harness sintetico.

## Proximos passos

1. continuar removendo curadoria residual de metadata em benchmarks mistos
2. pressionar o selection com menos naming favorecido e menos suporte manual
3. manter os mixed benchmarks como régua primária contra drift de produto
