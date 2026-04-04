# EXP-066 — Embedded Fixture Paths Reduce Mixed Resolver Dependence

## Identificacao

- ID: EXP-066
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Mesmo com roteamento mais estrutural, a execucao sintetica ainda dependia de:

- `profile_resolver`

para reobter `fixture_path` na hora de executar cada campanha gerada.

Isso mantinha uma camada residual de conhecimento externo ao plano:

- o plano sabia qual fixture set usar
- mas a execucao ainda precisava consultar um resolver separado

## Hipoteses

H1. O `CampaignPlan` pode carregar `fixture_path` explicita, reduzindo a
dependencia do resolver sintético misto.

H2. `run_generated_campaign()` deve conseguir executar apenas com o plano,
sem consultar `profile_resolver`, quando `fixture_path` estiver embutida.

## Desenho experimental

### Intervencao

1. `campaign_synthesis` passou a embutir:
   - `fixture_path`

2. `run_generated_campaign()` passou a:
   - usar `plan.fixture_path` diretamente
   - recorrer ao `profile_resolver` apenas como fallback

### Critério

1. teste unitario sem `profile_resolver`
2. rerun do benchmark:
   - `mixed_generalization_variant_p`

## Resultados por etapa

### Etapa 1 — Execucao sem profile_resolver

Confirmada.

Foi adicionado teste onde:

- o plano possui `fixture_path`
- o `profile_resolver` falharia se chamado

Resultado:

- a campanha executou normalmente

### Etapa 2 — Revalidacao do benchmark misto

Confirmada.

Resultado:

- `outputs_mixed_generalization_variant_p_assessment/`
- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

Tambem foi observado:

- todos os planos do `campaign_plan.json` passaram a carregar `fixture_path`

## Erros, intervencoes e motivos

Nao houve falha experimental nova.

O bloco foi uma reducao dirigida de acoplamento residual.

## Descoberta principal

O `CampaignPlan` ja consegue carregar mais do contrato de execucao do que
carregava antes.

Isso reduz o papel do resolver misto de:

- dependencia obrigatoria

para:

- compatibilidade / fallback

## Interpretacao

Esse bloco foi `mais generalização ofensiva`.

O ganho nao esta em novo path, mas em remover conhecimento escondido fora do
plano sintetizado.

## Implicacoes arquiteturais

- `campaign_plan.json` ficou mais auto-suficiente
- a execucao passou a depender menos de mapping externo por familia
- o proximo alvo natural e:
  - reduzir ainda mais o papel do resolver sintético como camada separada

## Ameacas a validade

- o resolver ainda existe como fallback
- fixture sets sinteticos continuam separados por familia

## Conclusao

H1 confirmada.

H2 confirmada.

O bloco reduziu a dependencia do resolver sintético misto sem degradar o
benchmark enterprise.

## Proximos passos

1. reduzir o papel do resolver sintético para casos realmente excepcionais
2. continuar removendo conhecimento de family routing fora do plano
