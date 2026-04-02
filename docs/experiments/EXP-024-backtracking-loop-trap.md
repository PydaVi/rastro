# EXP-024 — Loop Trap Sintetico para Backtracking

## Identificacao
- ID: EXP-024
- Fase: 3
- Pre-requisito: EXP-023 concluido
- Status: concluida

## Contexto
Prioridade 2 do curto prazo (backtracking completo) exige provar que o engine
nao entra em ciclos quando o branch ativo oferece a mesma enumeracao repetida
sem progresso. Este experimento introduz um role dead-end que permite
enumerar o mesmo bucket indefinidamente.

## Hipoteses
H1: o engine evita repetir a mesma enumeracao no branch dead-end e
    realiza backtracking para o role correto.
H2: o loop trap nao gera desgaste de steps a ponto de impedir o objetivo.

## Desenho experimental

### Variavel independente
- fixture com loop de enumeracao no RoleA (dead-end)
- planner OpenAI

### Ambiente
- fixture sintetico com dois pivots: RoleA (dead-end com loop) e RoleQ (correto)
- bucket decoy: finance-archives
- bucket alvo: sensitive-finance-data

### Artefatos
- `fixtures/aws_backtracking_loop_trap_lab.json`
- `examples/objective_aws_backtracking_loop_trap.json`
- `examples/scope_aws_backtracking_loop_trap_openai.json`

### Criterio de sucesso
- objective_met true
- backtracking ocorre sem repetir o mesmo enumerate indefinidamente

## Resultados por etapa

### Etapa 1 — Execucao dry-run com OpenAIPlanner
- Status: confirmada
- Resultado: objective_met true em 3 passos
- Passos: enumerate roles -> assume RoleQ -> access_resource
- Observacao: enumeracao repetida foi evitada e o loop trap nao ocorreu

## Erros, intervencoes e motivos
- Erro: loop de assume_role repetido e enumeracao reciclada.
  Intervencao: filtro de assume_role repetido e memoria de enumeracao
  por (actor, target).
  Motivo: evitar ciclos sem progresso e forcar backtracking real.

- Erro: s3_list_bucket/s3_read_sensitive filtrados no tool registry.
  Intervencao: adicionar flag audit_role_assumed no fixture.
  Motivo: precondicao obrigatoria dos tools no simulador.

## Descoberta principal
- Backtracking completo exige memoria explicita de enumeracao repetida.
- Loop prevention deve ser generalizado (nao especifico do fixture).

## Interpretacao
- O engine evitou ciclos e convergiu para o objetivo com
  branch correto sem regressao no path scoring.

## Implicacoes arquiteturais
- Se falhar, adicionar memoria de repeticao por (actor, action_type, target)
  para marcar branch como exaurido.

## Ameacas a validade
- Ambiente sintetico unico.
- Apenas um loop trap (enumerate).

## Conclusao
- H1 confirmada. H2 confirmada.

## Proximos experimentos
- EXP-025: backtracking com sinais ambiguos + analyze no-op
