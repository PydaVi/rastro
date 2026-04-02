# EXP-025 — Backtracking com Sinais Ambiguos e Analyze No-op

## Identificacao
- ID: EXP-025
- Fase: 3
- Pre-requisito: EXP-024 concluido
- Status: concluida

## Contexto
Depois do loop trap, o proximo risco e o branch correto ser abandonado
por sinais ambiguos combinados com passos de analyze que nao desbloqueiam
novas acoes (no-op). Este experimento verifica se o engine se recupera
sem entrar em repeticao ou desistir cedo.

## Hipoteses
H1: o engine evita loops e converge para o objetivo mesmo com analyze no-op.
H2: sinais ambiguos nao levam a abandono definitivo do branch correto.

## Desenho experimental

### Variavel independente
- fixture com dois pivots, sinais ambiguos e analyze no-op
- planner OpenAI

### Ambiente
- branch correto requer manter pivot apesar de analyze no-op
- branch decoy tem sinais proximos ao objetivo

### Criterio de sucesso
- objective_met true
- nenhuma repeticao infinita de analyze/enumerate

## Resultados por etapa

### Etapa 1 — Execucao dry-run com OpenAIPlanner
- Status: confirmada
- Resultado: objective_met true em 3 passos
- Passos: enumerate roles -> assume RoleQ -> access_resource
- Observacao: sinais ambiguos nao desviaram o pivot correto

## Erros, intervencoes e motivos
- Nenhum.

## Descoberta principal
- O engine manteve o pivot correto mesmo com analyze no-op
  e sinais ambiguos no branch decoy.

## Interpretacao
- Backtracking permanece estavel quando analyze nao desbloqueia novas
  acoes e o scoring favorece o branch correto.

## Implicacoes arquiteturais
- Se falhar, revisar heuristica de explore_current_branch vs. pivot
  quando analyze e no-op.

## Ameacas a validade
- Fixture sintetico unico.

## Conclusao
- H1 confirmada. H2 confirmada.
