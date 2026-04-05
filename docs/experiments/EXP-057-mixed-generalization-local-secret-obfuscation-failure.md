# EXP-057 — Mixed Generalization Local Secret Obfuscation Failure

## Identificacao

- ID: EXP-057
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Depois de `EXP-056`, o proximo alvo de maior leverage era o secret local
compartilhado com `external-entry`.

Objetivo:

- reduzir naming favorecido do secret local principal
- medir se o benchmark misto continuaria estavel quando `aws-iam-secrets` e
  `aws-external-entry-data` passassem a competir com menos apoio lexical no
  alvo local de segredo

## Hipoteses

H1. O benchmark enterprise deveria continuar estavel mesmo com o secret local
principal obfuscado.

H2. Se houvesse falha, ela deveria revelar um limite localizado de harness ou
roteamento sintetico, nao do engine ofensivo.

## Desenho experimental

### Variavel independente

Foi criada:

- `fixtures/mixed_generalization_variant_l.discovery.json`

Renomeacoes principais:

- `prod/payroll-api-key` -> `prod/sys/kv_a`
- `prod/payroll-backend-password` -> `prod/sys/kv_b`
- `prod/payroll-webhook-password` -> `prod/sys/kv_c`

## Resultados por etapa

### Etapa 1 — Selection

Confirmada.

Selecao observada:

- `aws-iam-secrets`
  - `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/sys/kv_a`
- `aws-external-entry-data`
  - mudou de um secret local para:
    - `arn:aws:s3:::mixed-payroll-data-prod/data/2026-03/r1.bin`

Essa mudanca foi coerente:

- com o secret local menos semantico
- o objeto S3 passou a ser o alvo local mais expressivo para `external-entry`

### Etapa 2 — Assessment discovery-driven inicial

Falhou.

Resumo observado:

- `campaigns_total = 9`
- `campaigns_passed = 8`
- `campaigns_objective_not_met = 1`

Campanha afetada:

- `aws-iam-secrets`

Sinal observado:

- `objective.target = prod/sys/kv_a`
- `proof.secret_id = prod/reporting/export-token`

## Erros, intervencoes e motivos

### Causa raiz

- falha de infraestrutura/harness sintetico: sim
- falha de representacao de estado: nao
- falha de policy do engine: nao
- falha do planner: nao

Diagnostico:

- o benchmark escolheu o novo secret local obfuscado corretamente
- o run sintetico de `aws-iam-secrets` estava sendo roteado para o fixture
  `compute-pivot-app`, nao apenas para o fixture serverless que ja havia sido
  expandido
- esse fixture ainda mantinha o target legado
  `prod/reporting/export-token`
- o resultado foi uma campanha coerente no profile, mas ainda ancorada em um
  target legado do harness sintetico

### Intervencao

Correcao aplicada:

- `fixtures/compute_pivot_app_iam_secrets_lab.json`
  - suporte adicionado aos aliases:
    - `prod/sys/kv_a`
    - `prod/sys/kv_b`
- `examples/scope_compute_pivot_app_iam_secrets.json`
  - recursos permitidos atualizados para incluir os aliases novos

Essa correcao foi geral para o fixture set `compute-pivot-app`, nao um remendo
exclusivo da variante L.

### Etapa 3 — Assessment discovery-driven apos correcao

Confirmada.

Resultado observado:

- `outputs_mixed_generalization_variant_l_assessment/`
- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Descoberta principal

Obfuscar o secret local principal pressiona simultaneamente:

- `aws-iam-secrets`
- `aws-external-entry-data`

e por isso expõe mais facilmente desalinhamentos do harness sintetico entre
benchmark misto e fixture sets alternativos usados pelo roteamento estrutural.

## Interpretacao

A falha inicial nao apontou regressao do engine.

Ela isola um ponto mais delicado do benchmark:

- recursos locais compartilhados entre classes precisam de suporte de alias mais
  cuidadoso do que alvos enterprise ou recursos locais isolados
- esse cuidado precisa cobrir todos os fixture sets que podem ser inferidos no
  `execution_fixture_set`, nao apenas o fixture mais obvio do profile

## Implicacoes arquiteturais

- a reducao de naming favorecido em recursos compartilhados deve ser feita com
  mais cuidado que em recursos exclusivos
- benchmarks mistos precisam validar explicitamente fixture routing estrutural
  quando um mesmo profile pode ser resolvido por mais de um ambiente sintetico
- o bloco continua empurrando o produto para `mais generalização ofensiva`
  porque expõe e remove uma dependencia escondida do harness

## Ameacas a validade

- continua sendo benchmark sintetico
- o bloco continua dependente de harness sintetico
- ainda existem alvos locais compartilhados que podem revelar novos aliases
  faltantes em fixture sets alternativos

## Conclusao

H1 confirmada tambem para assessment ponta a ponta.

H2 confirmada: a falha foi isolada como mismatch localizado de harness
sintetico e corrigida sem mudanca de engine.

## Proximos passos

1. reduzir o apoio lexical restante no secret local compartilhado com
   `external-entry`
2. continuar removendo naming favorecido dos alvos locais sem quebrar o routing
   estrutural dos fixture sets
3. manter mixed benchmark como régua de generalização ofensiva, nao apenas de
   estabilidade do harness
