# EXP-026 — Backtracking com 3 Pivos Concorrentes e Branch Profundo

## Identificacao
- ID: EXP-026
- Fase: 3
- Pre-requisito: EXP-025 concluido
- Status: concluida

## Contexto
Backtracking completo precisa suportar mais de dois pivots competitivos
antes do caminho correto, com branch mais profundo no pivô certo.

## Falha e causa raiz
O experimento inicial nao forçou duas escolhas erradas antes do pivô correto,
portanto a hipotese central nao foi exercitada. O fixture foi endurecido
e o teste reexecutado.

### Classificacao de causas
- Infraestrutura (fixture): a fixture permitiu que RoleQ fosse escolhido de
  primeira, entao nao validou backtracking.
- Representacao de estado: nao aplicavel (estado atual suficiente).
- Policy (action shaping / scoring): nao aplicavel, pois a falha nao foi
  causada por heuristica insuficiente, e sim por fixture permissiva.
- Framing do planner: nao aplicavel.
- Limitacao do modelo: nao aplicavel.

## Hipoteses
H1: o engine recupera apos duas escolhas erradas e converge no pivô correto.
H2: branch profundo no pivô correto nao causa abandono prematuro.

## Desenho experimental

### Variavel independente
- fixture com tres pivots concorrentes (RoleA, RoleM, RoleQ)
- branch profundo no pivô correto
- planner OpenAI

### Ambiente
- RoleA e RoleM: buckets decoy
- RoleQ: bucket sensivel com enumerate + access_resource

### Criterio de sucesso
- objective_met true
- recuperacao apos duas escolhas erradas

## Resultados por etapa

### Etapa 1 — Execucao dry-run com OpenAIPlanner (antes do endurecimento)
- Status: executada
- Resultado: objective_met true em 3 passos
- Observacao: o planner convergiu direto para RoleQ, sem testar pivots errados

### Etapa 2 — Execucao dry-run com OpenAIPlanner (apos endurecimento)
- Status: confirmada
- Resultado: objective_met true em 7 passos
- Passos: enumerate roles -> RoleA -> enumerate decoy -> RoleM -> enumerate decoy -> RoleQ -> access_resource
- Observacao: backtracking ocorreu apos duas escolhas erradas

## Erros, intervencoes e motivos
- Erro: o fixture inicial nao forcava duas escolhas erradas antes do pivô correto.
  Intervencao: endurecer o cenário para tornar RoleA/RoleM mais atraentes no
  primeiro momento e liberar RoleQ apenas apos os decoys.
  Motivo: garantir que a hipotese de backtracking apos duas escolhas erradas
  fosse exercitada.

## Descoberta principal
- Backtracking completo sustentou duas escolhas erradas antes do pivô correto
  sem entrar em loops ou abandonar o caminho.

## Interpretacao
- O engine recuperou corretamente apos dois pivots errados e convergiu
  para o branch correto com profundidade adicional.

## Implicacoes arquiteturais
- Se falhar, revisar memoria de branch e penalidade de repeticao
  com multiplos pivots.

## Ameacas a validade
- Fixture sintetico unico.

## Conclusao
- H1 confirmada. H2 confirmada.

## Proximos experimentos
- EXP-027: validacao AWS real de backtracking
