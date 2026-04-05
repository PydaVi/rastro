# EXP-058 — Mixed Generalization Lower Lexical Local Secret

## Identificacao

- ID: EXP-058
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Depois de `EXP-057`, o proximo passo de maior leverage era reduzir ainda mais o
apoio lexical do secret local compartilhado entre:

- `aws-iam-secrets`
- `aws-external-entry-data`

Objetivo:

- diminuir a dependencia residual de tokens como `sys` e `kv`
- medir se o benchmark misto continuaria estavel com aliases ainda menos
  semanticos no alvo local compartilhado

## Hipoteses

H1. O benchmark enterprise deveria continuar estavel com o secret local
renomeado para aliases ainda menos expressivos.

H2. `aws-external-entry-data` deveria continuar preferindo o alvo S3 local mais
expressivo, sem voltar a capturar o secret local apenas por coincidencia lexical.

## Desenho experimental

### Variavel independente

Foi criada:

- `fixtures/mixed_generalization_variant_m.discovery.json`

Renomeacoes principais:

- `prod/sys/kv_a` -> `prod/app/s1`
- `prod/sys/kv_b` -> `prod/app/s2`
- `prod/sys/kv_c` -> `prod/app/s3`

### Intervencoes de suporte

Fixture sets expandidos para aceitar os aliases novos:

- `fixtures/serverless_business_app_iam_secrets_lab.json`
- `fixtures/compute_pivot_app_external_entry_lab.json`
- `fixtures/compute_pivot_app_iam_secrets_lab.json`
- `examples/scope_serverless_business_app_iam_secrets.json`
- `examples/scope_compute_pivot_app_iam_secrets.json`

## Resultados por etapa

### Etapa 1 — Selection

Confirmada.

Selecao observada:

- `aws-iam-secrets`
  - `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/app/s1`
- `aws-external-entry-data`
  - `arn:aws:s3:::mixed-payroll-data-prod/data/2026-03/r1.bin`

Leitura:

- o secret local ainda e o melhor target da classe `aws-iam-secrets`
- `external-entry` continua escolhendo o alvo local mais expressivo de forma
  estrutural, sem regressao para o secret compartilhado

### Etapa 2 — Assessment discovery-driven

Confirmada.

Resultado observado:

- `outputs_mixed_generalization_variant_m_assessment/`
- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Nao houve falha experimental nova neste bloco.

As mudancas foram feitas preventivamente nos fixture sets que podem ser
selecionados pelo roteamento estrutural do benchmark misto.

## Descoberta principal

O benchmark enterprise permanece estavel mesmo quando o secret local
compartilhado perde quase todo o naming favoravel remanescente.

## Interpretacao

O scorer ainda usa algum apoio lexical residual, mas a estabilidade observada
indica que:

- `aws-iam-secrets` nao depende mais de naming de negocio explicito
- `aws-external-entry-data` ja se separa melhor por expressividade estrutural do
  path

## Implicacoes arquiteturais

- alvos locais compartilhados podem continuar sendo obfuscados sem quebrar o
  benchmark, desde que o suporte de alias cubra todos os fixture sets inferiveis
- o mixed benchmark segue servindo como régua real de generalizacao ofensiva,
  nao apenas como smoke test de estabilidade

## Ameacas a validade

- ainda e benchmark sintetico
- alias coverage continua sendo uma responsabilidade explicita do harness

## Conclusao

H1 confirmada.

H2 confirmada.

O bloco empurrou o produto para mais generalizacao ofensiva, reduzindo a
dependencia de naming favorecido tambem no secret local compartilhado.

## Proximos passos

1. reduzir o apoio lexical restante em secrets locais e deep targets sem
   aumentar curadoria manual
2. continuar pressionando o mixed benchmark contra naming desfavoravel
3. manter a separacao entre ganho estrutural real e ajuste localizado de harness
