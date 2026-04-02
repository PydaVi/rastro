# EXP-022 — Path Scoring com Limite de Steps Apertado

## Identificacao
- ID: EXP-022
- Fase: 3
- Pre-requisito: EXP-021 concluido
- Status: concluida

## Contexto
EXP-021 confirmou convergencia sob lookahead ambiguo quando o engine
filtra decoys por bucket e prioriza analyze. EXP-022 valida robustez
sob limite estrito de passos (max_steps=7), onde desvios custam o run.

## Hipoteses
H1: o engine converge nas tres variantes com max_steps=7.
H2: o action shaping evita desvios para decoy mesmo sob limite apertado.

## Desenho experimental

### Variavel independente
- max_steps reduzido para 7
- mesmas variantes e sinais de EXP-021 (weak lookahead)

### Ambiente
- `dry_run`
- bucket alvo: `sensitive-finance-data`
- bucket decoy: `public-reports`
- roles neutras: `RoleA`, `RoleM`, `RoleQ`
- alvo exige `enumerate -> analyze -> access_resource`

### Variantes
- `weak_signal_rolea_success`
- `weak_signal_rolem_success`
- `weak_signal_roleq_success`

Artefatos:
- `fixtures/aws_permuted_branching_deep_noisy_weak_signal_rolea_success_lab.json`
- `fixtures/aws_permuted_branching_deep_noisy_weak_signal_rolem_success_lab.json`
- `fixtures/aws_permuted_branching_deep_noisy_weak_signal_roleq_success_lab.json`
- `examples/objective_aws_permuted_branching_weak_signal_tight.json`
- `examples/scope_aws_permuted_branching_weak_signal_tight.json`
- `examples/scope_aws_permuted_branching_weak_signal_tight_openai.json`

### Criterio de sucesso
- convergir nas tres variantes com `max_steps=7`

## Resultados por etapa

### Etapa 1 — Execucao dry_run com OpenAIPlanner
- Resultado: passou nas tres variantes
- Comportamento observado: convergencia em 5-7 passos, mantendo o branch
  correto mesmo com limite apertado.

## Erros, intervencoes e motivos
- Ajuste necessario: priorizacao de access_resource que atinge o objetivo
  quando disponivel, para evitar desperdicio de steps.

## Descoberta principal
Com max_steps=7, a priorizacao de branch ativo + preferencia por access_resource
do objetivo garante convergencia sem depender de sorte.

## Interpretacao
- H1 confirmada.
- H2 confirmada.

## Implicacoes arquiteturais
- Se H1 falhar, priorizacao de branch ativo precisa ser ainda mais agressiva
  sob limite de steps (ex.: hard lock ate concluir analyze).

## Ameacas a validade
- Apenas dry_run.

## Conclusao
H1 confirmada. H2 confirmada. O engine manteve robustez sob limite apertado.
