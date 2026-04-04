# EXP-068 — Mixed Benchmark Without Profile Resolver

## Identificacao

- ID: EXP-068
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Depois de embutir:

- `fixture_path`
- `scope_template_path`

nos artefatos do pipeline, o proximo passo natural era verificar se o benchmark
misto enterprise ainda dependeria de `profile_resolver`.

## Hipoteses

H1. O benchmark `mixed_generalization_variant_p` pode executar ponta a ponta sem
`profile_resolver`.

H2. Se isso passar, o resolver sintético deixa de ser infraestrutura central e
passa a ser apenas fallback excepcional.

## Desenho experimental

### Intervencao

Foram feitos dois ajustes:

1. `run_discovery_driven_assessment()` deixou de injetar `get_profile` como
default.
2. `campaign_synthesis` e `run_generated_campaign` passaram a falhar so quando
realmente precisarem resolver um profile sem caminhos embutidos.

### Critério

Executar:

- `mixed_generalization_variant_p`

sem passar `profile_resolver`.

## Resultados por etapa

### Etapa 1 — Teste unitario sem resolver

Confirmada.

Foi adicionado teste end-to-end do benchmark misto sem `profile_resolver`.

Resultado:

- `campaigns_total = 9`
- `campaigns_passed = 9`

### Etapa 2 — Reexecucao do output persistido

Confirmada.

Resultado:

- `outputs_mixed_generalization_variant_p_assessment/`
- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Nao houve falha experimental neste bloco.

O foco foi provar remocao de dependencia arquitetural, nao corrigir bug novo.

## Descoberta principal

O benchmark misto enterprise ja nao precisa de `profile_resolver` para operar.

Isso significa que o pipeline discovery-driven passou a carregar, nos proprios
artefatos, o contrato necessario de synthesis e execucao.

## Interpretacao

Esse bloco foi `mais generalização ofensiva`.

Ele removeu uma camada residual de conhecimento oculto fora do pipeline gerado.

## Implicacoes arquiteturais

- `profile_resolver` deixa de ser obrigatorio no benchmark misto
- fallback continua existindo para compatibilidade
- a proxima reducao de acoplamento deve mirar os fixture sets por familia

## Ameacas a validade

- isso ainda vale para benchmark sintético
- fixtures continuam agrupados por familia de path

## Conclusao

H1 confirmada.

H2 confirmada.

O benchmark enterprise misto passou a operar sem `profile_resolver`,
aproximando mais o pipeline do polo generalista.

## Proximos passos

1. reduzir dependencia residual de fixture sets por familia
2. decidir se o proximo leverage esta em benchmark ainda menos curado ou em
   promoção real seletiva
