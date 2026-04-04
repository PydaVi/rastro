# EXP-064 — Profile-Independent Objective Generation

## Identificacao

- ID: EXP-064
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Mesmo apos endurecer `target_observed`, a synthesis ainda dependia de:

- `profile.objective_path`

para criar o objetivo gerado.

Isso mantinha um acoplamento desnecessario entre:

- campaign synthesis
- familias fixas de path
- objetivos base do harness

## Hipoteses

H1. O objetivo gerado poderia ser construido apenas com:

- `description`
- `target`
- `success_criteria`

sem ler o objetivo base do profile.

H2. Remover essa leitura reduziria drift `profile-first` sem quebrar o
benchmark misto enterprise.

## Desenho experimental

### Intervencao

`campaign_synthesis` passou a instanciar `Objective(...)` diretamente, sem
carregar `profile.objective_path`.

### Critério

1. teste unitario com `objective_path` ausente
2. revalidacao do benchmark:
   - `mixed_generalization_variant_p`

## Resultados por etapa

### Etapa 1 — Objective generation sem arquivo base

Confirmada.

Foi adicionado teste que resolve um `ProfileDefinition` com:

- `objective_path` inexistente
- `scope_path` valido

e a synthesis continuou gerando:

- `target`
- `success_criteria.mode = target_observed`

sem depender do arquivo base.

### Etapa 2 — Revalidacao do benchmark misto

Confirmada.

Resultado:

- `outputs_mixed_generalization_variant_p_assessment/`
- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Nao houve nova falha experimental neste bloco.

O bloco foi uma remocao preventiva de acoplamento residual.

## Descoberta principal

O objetivo gerado ja nao precisa mais herdar nada do profile base.

Isso mostra que a synthesis pode evoluir mais perto de:

- `candidate-driven objective generation`

em vez de:

- `profile-templated objective generation`

## Interpretacao

Esse bloco foi `mais generalização ofensiva`.

O ganho principal foi tirar uma dependencia estrutural de campanhas conhecidas,
sem custo de estabilidade no benchmark misto.

## Implicacoes arquiteturais

- `objective generation` ficou menos acoplada ao harness
- `ProfileDefinition.objective_path` permanece por compatibilidade, mas deixou
  de ser dependencia obrigatoria da synthesis
- o proximo alvo natural continua sendo:
  - reduzir `fixture set routing`

## Ameacas a validade

- a execution ainda depende de fixture sets sinteticos por familia
- o resolver misto ainda existe como camada de compatibilidade

## Conclusao

H1 confirmada.

H2 confirmada.

O bloco removeu um acoplamento residual importante de `objective generation`
sem degradar o benchmark misto enterprise.

## Proximos passos

1. reduzir curadoria residual em `fixture set routing`
2. continuar mixed benchmarks com menos dependencias de families fixas
