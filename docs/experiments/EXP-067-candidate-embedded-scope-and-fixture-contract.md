# EXP-067 — Candidate-Embedded Scope And Fixture Contract

## Identificacao

- ID: EXP-067
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Mesmo apos embutir `fixture_path` no plano, a synthesis ainda dependia de
`profile_resolver` para recuperar:

- `scope_path`

Isso mantinha acoplamento residual entre:

- candidate
- campaign synthesis
- catalogo externo por familia

## Hipoteses

H1. O proprio candidato pode carregar o contrato minimo de synthesis:

- `fixture_path`
- `scope_template_path`

H2. Com isso, a synthesis deixa de depender do resolver sintético para gerar
campaigns nos benchmarks mistos.

## Desenho experimental

### Intervencao

`target_selection` passou a embutir, por candidato:

- `fixture_path`
- `scope_template_path`

`campaign_synthesis` passou a preferir esses caminhos embutidos. O resolver
permanece apenas como fallback.

### Critério

1. teste unitario sem `profile_resolver`
2. rerun de `mixed_generalization_variant_p`

## Resultados por etapa

### Etapa 1 — Synthesis sem resolver

Confirmada.

Foi adicionado teste em que:

- o candidato ja carrega `fixture_path`
- o candidato ja carrega `scope_template_path`
- o `profile_resolver` falharia se chamado

Resultado:

- a synthesis executou normalmente

### Etapa 2 — Revalidacao do benchmark enterprise

Confirmada.

Resultado:

- `outputs_mixed_generalization_variant_p_assessment/`
- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

Tambem foi observado:

- todos os candidatos passaram a carregar `scope_template_path`
- todos os planos passaram a carregar `fixture_path`

## Erros, intervencoes e motivos

Nao houve nova falha experimental.

O bloco foi dirigido por eliminacao de acoplamento residual.

## Descoberta principal

O contrato do candidato ficou mais auto-suficiente:

- selection agora entrega mais do que prioridade
- entrega tambem contrato minimo de synthesis/execucao

## Interpretacao

Esse bloco foi `mais generalização ofensiva`.

Ele reduz conhecimento escondido no resolver e desloca mais do contrato para
os artefatos gerados pelo proprio pipeline discovery-driven.

## Implicacoes arquiteturais

- o `target_candidates.json` ficou mais expressivo
- a synthesis passou a depender menos de catalogo externo
- o resolver sintético continua existindo, mas com papel menor

## Ameacas a validade

- ainda existe fallback para resolver
- fixture sets sinteticos por familia continuam existindo

## Conclusao

H1 confirmada.

H2 confirmada.

O bloco reduziu mais um acoplamento residual do benchmark misto sem degradar a
estabilidade do assessment enterprise.

## Proximos passos

1. reduzir o fallback do resolver para casos realmente excepcionais
2. continuar removendo family knowledge escondido fora do pipeline
