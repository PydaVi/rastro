# EXP-027 — Backtracking em AWS Real (validacao)

## Identificacao
- ID: EXP-027
- Fase: 3
- Pre-requisito: EXP-026 concluido
- Status: concluida

## Contexto
Com backtracking validado em cenarios sinteticos (loop trap, sinais ambiguos,
3 pivots concorrentes), o proximo passo e validar em AWS real um cenario
representativo, mantendo controle de escopo e evidencia real.

## Hipoteses
H1: o engine realiza backtracking e acessa o objetivo em AWS real.
H2: o fluxo nao entra em loops ou revisitas inutiles.

## Falha e causa raiz
O run inicial convergiu direto para o pivô correto, sem abandonar um dead-end.
A hipotese central de backtracking real nao foi exercitada. O fixture foi
endurecido e o teste reexecutado.

### Classificacao de causas
- Infraestrutura (fixture): o cenário real nao forçou o dead-end como
  primeira escolha; o pivô correto ficou mais atrativo.
- Representacao de estado: nao aplicavel.
- Policy (action shaping / scoring): nao aplicavel.
- Framing do planner: nao aplicavel.
- Limitacao do modelo: nao aplicavel.

## Desenho experimental

### Variavel independente
- execucao real em AWS (RASTRO_ENABLE_AWS_REAL=1)
- planner OpenAI

### Ambiente
- fixture local real com pivots concorrentes e objeto sensivel
- conta autorizada via terraform_local_lab

### Criterio de sucesso
- objective_met true
- evidencia real de acesso ao alvo

## Resultados por etapa

### Etapa 1 — Execucao AWS real com OpenAIPlanner
- Status: executada
- Resultado: objective_met true em 3 passos
- Observacao: sem backtracking (pivô correto escolhido direto)

### Etapa 2 — Execucao AWS real com OpenAIPlanner (apos endurecimento)
- Status: confirmada
- Resultado: objective_met true em 5 passos
- Passos: enumerate roles -> assume dead-end -> enumerate decoy -> assume pivô correto -> access_resource
- Observacao: backtracking real ocorreu sem loops

## Erros, intervencoes e motivos
- Erro: fixture real nao forca dead-end antes do pivô correto.
  Intervencao: endurecer o cenário real para tornar o dead-end
  mais atrativo na primeira escolha e liberar o caminho correto depois.
  Motivo: validar backtracking real, nao apenas path scoring.

## Descoberta principal
- Backtracking real foi exercitado e convergiu apos um dead-end
  sem revisitas inutiles.

## Interpretacao
- O engine realizou backtracking real em AWS e manteve controle
  de loop e recuperacao.

## Implicacoes arquiteturais
- Se falhar, revisar branch memory e loop prevention no executor real.

## Ameacas a validade
- Apenas um ambiente real.

## Conclusao
- H1 confirmada. H2 confirmada.
