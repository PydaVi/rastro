# EXP-005 — Backtracking Estruturado com Candidate Path Tracking

## Identificação
- ID: EXP-005
- Fase: 3
- Pré-requisito: EXP-003 concluído
- Status: primeiro corte implementado; validado offline, em Path 4 dry-run com OpenAIPlanner, e em Path 4 AWS real como convergência end-to-end

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

H3: em um cenário dedicado com um dead-end plausível, o `OpenAIPlanner`
consegue abrir o branch errado, explorar o dead-end, pivotar para o caminho
alternativo e alcançar o objetivo final.

## Desenho experimental

### Variável independente
- engine antes de `candidate_paths`
- engine após `candidate_paths` + `action shaping` com backtracking básico
- Path 4 original
- Path 4 endurecido para tornar o pivô errado mais atraente no primeiro momento

### Ambiente
- testes unitários offline
- rerun do Path 3 real com `OpenAIPlanner`
- Path 4 dry-run com `MockPlanner`
- Path 4 dry-run com `OpenAIPlanner`
- Path 4 AWS real com `OpenAIPlanner`

### Critério de sucesso
- o estado expõe caminhos candidatos com status explícito
- o shaping prioriza pivô `untested` quando não há branch ativo com progresso
- o `MockPlanner` prefere pivô `untested` e evita pivô `failed`
- o Path 3 continua convergindo sem regressão
- o Path 4 força retorno a um pivô alternativo após esgotar um dead-end

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
- alinhamento entre fixture e scope OpenAI do Path 4 para preservar ações `assume_role`

### Não regressão no Path 3
O rerun do Path 3 real com `OpenAIPlanner` continuou convergindo:

1. `iam_list_roles`
2. `iam_passrole`
3. `s3_list_bucket`
4. `s3_read_sensitive`

Resultado:

- `objective_met: True`
- sem regressão do comportamento já validado

### Path 4 com MockPlanner
O Path 4 dry-run passou a fechar o objetivo de ponta a ponta:

1. `iam_list_roles`
2. `assume_role -> dead-end`
3. `s3_list_bucket -> dead-end`
4. `assume_role -> role correta`
5. `s3_read_sensitive -> payroll.csv`

Isso confirmou que o cenário dedicado realmente exercita retorno a um pivô
alternativo.

### Path 4 endurecido com OpenAIPlanner
O Path 4 endurecido passou a usar:

- `A-FinanceAuditRole` como branch inicialmente atraente, mas morto
- `Z-DataOpsRole` como branch correto menos óbvio pelo nome
- bucket sensível compartilhado entre os dois pivôs
- objeto irrelevante (`budget-summary.csv`) no branch morto
- objeto sensível (`payroll.csv`) no branch correto

Houve um falso negativo intermediário:

- o `OpenAIPlanner` ficou preso em `enumerate -> root`
- a causa não foi o planner em si, e sim um desencontro entre `fixtures/aws_backtracking_lab.json` e `examples/scope_aws_backtracking_openai.json`
- o scope ainda referenciava os nomes antigos das roles e recursos
- isso filtrava as ações `assume_role` no dry-run e deixava o planner sem espaço de decisão real

Após corrigir o scope, o `OpenAIPlanner` executou o comportamento esperado:

1. `iam_list_roles`
2. `assume_role -> A-FinanceAuditRole`
3. `s3_list_bucket -> sensitive-finance-data`
4. `assume_role -> Z-DataOpsRole`
5. `s3_read_sensitive -> payroll.csv`

Resultado:

- `objective_met: True`
- o planner entrou primeiro no branch errado
- explorou o dead-end
- pivotou para o candidate path alternativo
- alcançou o objetivo final

### Path 4 AWS real com OpenAIPlanner
O Path 4 real foi então executado com `OpenAIPlanner`.

Houve um falso negativo inicial no ambiente real:

- o run ficou preso em `assume_role`
- a causa não foi o planner em si, e sim o `ToolRegistry`
- as tools `s3_list_bucket` e `s3_read_sensitive` exigiam o flag `audit_role_assumed`
- o fixture real do Path 4 adicionava apenas `finance_audit_role_assumed` e `data_ops_role_assumed`
- isso fazia com que as ações de progresso do branch ativo fossem filtradas, apesar de existirem no estado

Após corrigir o fixture real para também adicionar `audit_role_assumed`, o Path 4 real convergiu:

1. `iam_list_roles`
2. `assume_role -> Z-DataOpsRole`
3. `s3_read_sensitive -> payroll.csv`

Resultado:

- `objective_met: True`
- `real_api_called: True`

Interpretação específica do run real:

- o ambiente real ficou consistente de ponta a ponta
- o executor real, o fixture local de suporte, o `ToolRegistry` e o `action shaping` passaram a operar sem conflito
- esse run validou a convergência real do cenário
- esse run não validou backtracking real, porque o planner escolheu a role correta de primeira

## Interpretação
H1 foi confirmada no primeiro corte:

- o engine agora representa explicitamente caminhos candidatos
- existe um mecanismo geral de retorno para pivô `untested`
- o comportamento é validável offline

H2 também foi confirmada:

- o Path 3 continuou convergindo depois da introdução de `candidate_paths`
- não houve regressão do caminho já estabilizado

H3 foi confirmada no Path 4 dry-run com `OpenAIPlanner`:

- o planner não apenas resolveu o cenário
- ele resolveu pelo comportamento desejado de backtracking, e não por escolha direta do pivô correto

O falso negativo intermediário também foi útil:

- provou que desalinhamento entre fixture e scope pode simular uma falha de planner
- reforçou que parte da metodologia experimental precisa validar o espaço de ações disponível, não apenas o output do LLM

O falso negativo do ambiente real adicionou uma segunda lição metodológica:

- além de fixture e scope, o conjunto de flags esperado pelo `ToolRegistry` também faz parte da validade experimental
- uma falha de alinhamento entre transições do fixture e precondições das tools pode se manifestar como erro aparente de planner

## Implicações arquiteturais
- `candidate path tracking` deixa de ser apenas requisito de roadmap e vira estrutura do estado
- backtracking sai do prompt e entra na policy do engine
- cenários de branch concorrente agora podem ser projetados e auditados com causa isolável
- alinhamento entre fixture e scope vira requisito explícito de validade experimental
- alinhamento entre flags do fixture e precondições do `ToolRegistry` vira requisito explícito de validade experimental

## Ameaças à validade
- a validação principal de backtracking forte ainda foi em `dry_run`, não em AWS real
- o mecanismo atual continua heurístico; não é um planejador de árvore completo
- o Path 4 foi desenhado para induzir um tipo específico de dead-end, não uma família ampla de dead-ends
- o run real do Path 4 validou convergência end-to-end, mas não exigiu erro inicial de pivô

## Conclusão
O EXP-005 primeiro corte foi suficiente para introduzir backtracking básico,
preservar a estabilidade do Path 3, demonstrar backtracking explícito em um
cenário dedicado do Path 4 com `OpenAIPlanner` em `dry_run`, e validar a
consistência end-to-end do mesmo cenário em AWS real.

O problema central desta etapa deixou de ser apenas "o planner escolhe certo?"
e passou a ser "o engine mantém estado suficiente para retornar a um ponto de
decisão com alternativas ainda válidas?". Nesta formulação, o resultado foi
positivo.

Ao mesmo tempo, a evidência final ficou separada em duas camadas:

- `dry_run`: prova forte de backtracking
- AWS real: prova de consistência end-to-end do cenário, sem backtracking obrigatório no run observado

## Próximos passos
- repetir a ideia de Path 4 em cenários com mais de dois pivôs
- testar dead-ends com profundidade maior que um único passo de exploração
- se necessário, endurecer um cenário AWS real futuro para aumentar a chance de erro inicial de pivô sem transformar o teste em script

## Artefatos
- `fixtures/aws_backtracking_lab.json`
- `examples/objective_aws_backtracking.json`
- `examples/scope_aws_backtracking.json`
- `examples/scope_aws_backtracking_openai.json`
- `terraform_local_lab/rastro_local/aws_backtracking_lab.local.json`
- `terraform_local_lab/rastro_local/objective_aws_backtracking.local.json`
- `terraform_local_lab/rastro_local/scope_aws_backtracking_real.local.json`
- `terraform_local_lab/rastro_local/scope_aws_backtracking_openai.local.json`
