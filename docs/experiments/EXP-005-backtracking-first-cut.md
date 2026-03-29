# EXP-005 — Backtracking Estruturado com Candidate Path Tracking

## Identificação
- ID: EXP-005
- Fase: 3
- Pré-requisito: EXP-003 concluído
- Status: primeiro corte implementado e validado offline; validação em cenário dedicado pendente

## Contexto
O EXP-003 mostrou que memória mínima e `action shaping` foram suficientes para
destravar convergência no Path 3, mas não provaram backtracking forte.

O ponto que ficou em aberto foi:

- representar explicitamente caminhos candidatos no estado
- distinguir entre pivôs `untested`, `tested`, `active` e `failed`
- voltar a um caminho ainda não testado quando um branch se esgota

Sem isso, o engine ainda dependia mais de heurísticas de exploração do branch
ativo do que de backtracking explícito entre pontos de decisão.

## Hipótese
H1: com `candidate path tracking` explícito no estado, o engine evita revisitar
branches falhos e prioriza pivôs ainda não testados.

H2: o primeiro corte de backtracking não degrada o comportamento já validado no
Path 3.

## Desenho experimental

### Variável independente
- engine antes de `candidate_paths`
- engine após `candidate_paths` + `action shaping` com backtracking básico

### Ambiente
- testes unitários offline
- rerun do Path 3 real com `OpenAIPlanner`

### Critério de sucesso
- o estado expõe caminhos candidatos com status explícito
- o shaping prioriza pivô `untested` quando não há branch ativo com progresso
- o `MockPlanner` prefere pivô `untested` e evita pivô `failed`
- o Path 3 continua convergindo sem regressão

## Resultado observado

### Estado
O snapshot passou a expor `candidate_paths` com:

- `target`
- `status`
- `times_tested`
- `has_progress_actions`

### Policy layer
O `action shaping` passou a:

- priorizar ações do branch ativo quando existem
- priorizar `assume_role` de candidate paths `untested` quando não há progresso
- evitar revisitar candidate paths `failed`

### Planner heurístico
O `MockPlanner` passou a:

- penalizar pivôs em `failed_assume_roles`
- preferir candidate paths `untested`

### Validação offline
Os testes passaram cobrindo:

- candidate path com status `failed`
- backtracking para pivô `untested`
- preferência do `MockPlanner` por pivô `untested`

### Não regressão no Path 3
O rerun do Path 3 real com `OpenAIPlanner` continuou convergindo:

1. `iam_list_roles`
2. `iam_passrole`
3. `s3_list_bucket`
4. `s3_read_sensitive`

Resultado:

- `objective_met: True`
- sem regressão do comportamento já validado

## Interpretação
O primeiro corte confirmou H1 apenas parcialmente.

O que foi provado:

- o engine agora representa explicitamente caminhos candidatos
- existe um mecanismo geral de retorno para pivô `untested`
- o comportamento é validável offline

O que ainda não foi provado:

- backtracking profundo em cenário desenhado especificamente para forçar erro e retorno
- comportamento em árvores de decisão mais profundas
- recuperação em múltiplos níveis

H2 foi confirmada no Path 3:

- a nova capacidade não degradou o caminho já estabilizado

## Implicações arquiteturais
- `candidate path tracking` deixa de ser apenas requisito de roadmap e vira estrutura do estado
- backtracking começa a sair do prompt e entrar na policy do engine
- o próximo passo lógico é um cenário dedicado que force branch errado antes da convergência

## Ameaças à validade
- a validação principal ainda foi offline
- o Path 3 de rerun prova estabilidade, não prova backtracking profundo
- o mecanismo atual ainda é heurístico, não um planejador de árvore completo

## Conclusão
O EXP-005 primeiro corte foi suficiente para introduzir backtracking básico e
preservar a estabilidade do Path 3. Ainda falta um cenário dedicado para provar
backtracking real sob erro forçado.

## Próximo passo
- validar o primeiro corte em um Path 4 específico para exigir backtracking explícito após dead-end

## Artefatos criados para a próxima validação
- `fixtures/aws_backtracking_lab.json`
- `examples/objective_aws_backtracking.json`
- `examples/scope_aws_backtracking.json`

Esses artefatos foram desenhados para:

- abrir primeiro um branch morto
- esgotar esse branch
- forçar retorno para um candidate path ainda `untested`
- só então permitir convergência ao objeto final
