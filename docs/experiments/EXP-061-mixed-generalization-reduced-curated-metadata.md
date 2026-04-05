# EXP-061 — Mixed Generalization Reduced Curated Metadata

## Identificacao

- ID: EXP-061
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Depois de `EXP-060`, o proximo gap mais relevante era metadata curada ainda
presente no benchmark misto.

Objetivo:

- reduzir metadata nao estrutural remanescente
- verificar se o benchmark enterprise continuaria estavel apoiado mais em:
  - relationships
  - routing estrutural
  - aliases genericos no `Fixture`

## Hipoteses

H1. O benchmark enterprise deveria permanecer estavel mesmo com metadata
curada bem mais magra.

H2. `external-entry`, `cross-account` e `multi-step` deveriam continuar
separados corretamente pelo contexto estrutural.

## Desenho experimental

### Intervencao estrutural

`src/operations/target_selection.py` foi ajustado para tratar
`network.api_gateway` e `network.load_balancer` como publicos por default,
exceto quando `metadata.exposure == "private"`.

Isso reduz dependencia de um campo curado explicito no benchmark sintetico.

### Variavel independente

Foi criada:

- `fixtures/mixed_generalization_variant_p.discovery.json`

Reducao principal de metadata:

- `identity.role`
  - metadata removida
- `compute.ec2_instance`
  - mantido apenas `instance_profile`
- `network.api_gateway`
  - mantido apenas `target_instance`
- `compute.lambda_function`
  - mantidos apenas `role` e `kms_key`
- `crypto.kms_key`
  - metadata removida
- `data_store.s3_object`
  - mantidos apenas `bucket` e `object_key`
- `secret.secrets_manager`
  - mantido apenas `name`
- `secret.ssm_parameter`
  - mantido apenas `name`

## Resultados por etapa

### Etapa 1 — Selection

Confirmada.

Selecao observada:

- `aws-iam-secrets`
  - `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/r/a1`
- `aws-external-entry-data`
  - `arn:aws:s3:::mixed-payroll-data-prod/data/2026-03/r1.bin`
- `aws-cross-account-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/r/e1`
- `aws-multi-step-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/r/e2`

### Etapa 2 — Assessment discovery-driven

Confirmada.

Resultado observado:

- `outputs_mixed_generalization_variant_p_assessment/`
- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Nao houve falha experimental nova neste bloco.

## Descoberta principal

O benchmark misto enterprise continua estavel mesmo com metadata curada bem
mais magra, desde que a estrutura relevante continue presente em:

- `relationships`
- `instance_profile`
- `target_instance`
- `role`
- aliases genericos do `Fixture`

## Interpretacao

Esse bloco reduz um atalho importante de benchmark:

- menos `classification`
- menos `tier/workload/service`
- menos `exposure`

sem perder separacao entre as classes mais ofensivamente expressivas.

## Implicacoes arquiteturais

- inferencia estrutural esta sustentando uma parcela maior do comportamento
- metadata curada pode continuar sendo reduzida sem custo imediato no benchmark
- o mixed benchmark ficou mais alinhado com a régua de `attacker-thinker`

## Ameacas a validade

- continua sendo benchmark sintetico
- alguns campos estruturais ainda permanecem explicitamente presentes

## Conclusao

H1 confirmada.

H2 confirmada.

O bloco empurrou o produto para mais generalizacao ofensiva ao reduzir metadata
curada remanescente sem quebrar o assessment enterprise discovery-driven.

## Proximos passos

1. continuar movendo inferencia para relationships quando houver leverage real
2. reduzir curadoria residual em fixture set routing e objective generation
3. priorizar proximos blocos que aumentem generalizacao ofensiva observavel, nao
   apenas estabilidade operacional
