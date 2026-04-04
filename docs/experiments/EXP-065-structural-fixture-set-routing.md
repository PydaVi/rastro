# EXP-065 — Structural Fixture-Set Routing

## Identificacao

- ID: EXP-065
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Mesmo com `target selection` e `objective generation` menos `profile-first`,
o benchmark misto ainda dependia de roteamento por familia:

- `execution_fixture_set`

Esse roteamento ainda tinha trechos excessivamente ancorados em:

- nome do profile

em vez de:

- tipo de recurso
- fronteira de conta
- profundidade de chain
- vínculo com compute publico
- vínculo com runtime serverless

## Hipoteses

H1. O `execution_fixture_set` poderia ser inferido mais por estrutura do que por
listas fixas de profiles.

H2. Essa troca manteria o benchmark enterprise estavel em `9/9`.

## Desenho experimental

### Intervencao

`target_selection._infer_execution_fixture_set(...)` passou a priorizar:

- `resource_type`
- `resource_account != caller_account`
- `chain_depth`
- `role_to_public_surfaces`
- `role_to_instance_profiles`
- `role_to_instances`
- `role_to_lambda_functions`

antes de depender de mapeamento explícito por profile.

### Critério

1. teste unitario do roteamento na `variant_p`
2. reexecucao do benchmark misto enterprise

## Resultados por etapa

### Etapa 1 — Inferencia estrutural do fixture set

Confirmada.

Na `mixed_generalization_variant_p`:

- `aws-external-entry-data` -> `compute-pivot-app`
- `aws-iam-compute-iam` -> `compute-pivot-app`
- `aws-iam-lambda-data` -> `serverless-business-app`
- `aws-iam-kms-data` -> `serverless-business-app`
- `aws-cross-account-data` -> `mixed-generalization`
- `aws-multi-step-data` -> `mixed-generalization`

### Etapa 2 — Revalidacao end-to-end

Confirmada.

Resultado:

- `outputs_mixed_generalization_variant_p_assessment/`
- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Nao houve nova falha experimental neste bloco.

O objetivo foi remover um atalho arquitetural residual antes que ele virasse
drift estrutural.

## Descoberta principal

O roteamento do harness pode depender menos de nome do profile e mais de
evidencia estrutural do proprio candidato.

## Interpretacao

Esse bloco foi `mais generalização ofensiva`.

Ele nao elimina o resolver sintético, mas reduz a quantidade de conhecimento
escondido fora da selecao.

## Implicacoes arquiteturais

- `execution_fixture_set` ficou menos `profile-first`
- mixed benchmark passa a sustentar mais da propria inferencia estrutural
- o proximo gargalo remanescente continua sendo:
  - a existencia do resolver sintético como camada separada

## Ameacas a validade

- ainda existe fixture set routing, mesmo mais estrutural
- o benchmark sintetico continua dependendo de families de path

## Conclusao

H1 confirmada.

H2 confirmada.

O bloco reduziu curadoria residual no roteamento do harness sem degradar a
estabilidade do benchmark enterprise.

## Proximos passos

1. reduzir o papel do resolver sintético misto
2. continuar pressionando benchmark com menos fixture knowledge explícito
