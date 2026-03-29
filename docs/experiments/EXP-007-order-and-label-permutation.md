# EXP-007 — Permutacao de Ordem e Rotulos em Multi-Branch Backtracking

## Identificacao
- ID: EXP-007
- Fase: 3
- Pre-requisito: EXP-006 concluido
- Status: hipotese de convergencia confirmada com orcamento suficiente; fragilidade de order sensitivity confirmada

## Contexto
O EXP-006 confirmou que o engine conseguia:

- backtracking repetido com tres pivots concorrentes
- abandono de dois dead-ends consecutivos
- convergencia no terceiro branch correto

Mas o resultado ainda deixava uma pergunta em aberto:

- o comportamento observado dependia apenas da estrutura do estado e do `action shaping`
- ou ainda havia forte dependencia da ordem em que os pivots apareciam em `available_actions`

O EXP-007 foi desenhado para isolar essa pergunta.

## Hipoteses
H1: com nomes neutros e branches simetricos, o `OpenAIPlanner` continua convergindo quando o branch correto muda de role para role.

H2: mesmo com convergencia, o planner continua fortemente sensivel a ordem de apresentacao dos pivots.

H3: se o orcamento de passos for insuficiente, a falha principal sera de budget e nao de loop ou regressao do mecanismo de backtracking.

## Desenho experimental

### Variavel independente
- permutacao da ordem inicial das acoes `assume_role`
- permutacao de qual role e o branch correto
- `max_steps=5`
- `max_steps=8`

### Ambiente
- `dry_run`
- mesmas tres roles neutras em todas as variantes:
  - `RoleA`
  - `RoleM`
  - `RoleQ`
- mesmo bucket:
  - `arn:aws:s3:::sensitive-finance-data`
- somente uma role por variante leva a `payroll.csv`
- as outras duas sao dead-ends plausiveis

### Variantes
- `rolea_success`
  - ordem inicial: `RoleQ -> RoleM -> RoleA`
  - branch correto: `RoleA`
- `rolem_success`
  - ordem inicial: `RoleA -> RoleQ -> RoleM`
  - branch correto: `RoleM`
- `roleq_success`
  - ordem inicial: `RoleM -> RoleA -> RoleQ`
  - branch correto: `RoleQ`

### Criterio de sucesso
- o planner deve convergir nas tres permutacoes quando o orcamento permite
- o planner nao deve colapsar em loop
- o comportamento deve revelar se ha ou nao dependencia forte da ordem das acoes

## Resultados por etapa

### Etapa 1 — Criacao das variantes
Artefatos criados:

- `fixtures/aws_permuted_branching_rolea_success_lab.json`
- `fixtures/aws_permuted_branching_rolem_success_lab.json`
- `fixtures/aws_permuted_branching_roleq_success_lab.json`
- `examples/objective_aws_permuted_branching.json`
- `examples/scope_aws_permuted_branching.json`
- `examples/scope_aws_permuted_branching_openai.json`

Todas as variantes mantiveram:

- nomes neutros
- bucket unico
- um branch correto e dois dead-ends
- disponibilizacao de `s3_read_sensitive` apenas apos exploracao do branch correto

### Etapa 2 — Validacao offline
Foram adicionados testes offline parametrizados para as tres variantes.

Resultado:

- as tres variantes passaram com `MockPlanner`
- o desenho experimental estava consistente e reproduzivel sem dependencia externa

### Etapa 3 — OpenAIPlanner com `max_steps=5`
As tres variantes falharam.

Padrao observado:

- o planner enumerou
- assumiu o primeiro pivot na ordem apresentada
- explorou o branch com `s3_list_bucket`
- assumiu o segundo pivot ainda nao testado
- explorou o segundo branch
- terminou sem alcancar o terceiro pivot

Resultados:

- `rolea_success`: `RoleQ -> RoleM`
- `rolem_success`: `RoleA -> RoleQ`
- `roleq_success`: `RoleM -> RoleA`

Leitura:

- nao houve regressao para loop
- houve backtracking parcial
- a falha principal foi orcamento insuficiente

### Etapa 4 — OpenAIPlanner com `max_steps=8`
As tres variantes passaram.

#### Variante `rolea_success`
Caminho:

1. `iam_list_roles`
2. `assume_role -> RoleQ`
3. `s3_list_bucket`
4. `assume_role -> RoleM`
5. `s3_list_bucket`
6. `assume_role -> RoleA`
7. `s3_list_bucket`
8. `s3_read_sensitive`

Resultado:

- `objective_met: True`
- branch correto final: `RoleA`

#### Variante `rolem_success`
Caminho:

1. `iam_list_roles`
2. `assume_role -> RoleA`
3. `s3_list_bucket`
4. `assume_role -> RoleQ`
5. `s3_list_bucket`
6. `assume_role -> RoleM`
7. `s3_list_bucket`
8. `s3_read_sensitive`

Resultado:

- `objective_met: True`
- branch correto final: `RoleM`

#### Variante `roleq_success`
Caminho:

1. `iam_list_roles`
2. `assume_role -> RoleM`
3. `s3_list_bucket`
4. `assume_role -> RoleA`
5. `s3_list_bucket`
6. `assume_role -> RoleQ`
7. `s3_list_bucket`
8. `s3_read_sensitive`

Resultado:

- `objective_met: True`
- branch correto final: `RoleQ`

## Problemas observados e como foram corrigidos

### Problema 1 — Falso negativo por budget curto
Sintoma:

- todas as tres variantes falharam com `max_steps=5`

Causa:

- o budget era suficiente apenas para:
  - enumerar
  - explorar branch 1
  - explorar branch 2

Nao sobravam passos para:

- assumir branch 3
- enumerar branch 3
- acessar `payroll.csv`

Correcao:

- rerun das tres variantes com `--max-steps 8`

### Problema 2 — Dependencia forte da ordem das acoes
Sintoma:

- em todas as variantes, o planner consumiu os pivots exatamente na ordem apresentada

Causa:

- `candidate_paths` + `action_shaping` garantem backtracking e evitam revisita inutil
- mas ainda nao existe `path scoring` forte o bastante para reordenar pivots por valor esperado

Correcao:

- nenhuma correcao arquitetural foi aplicada ainda
- o problema foi isolado como descoberta principal do experimento

## Descoberta principal
O EXP-007 mostrou duas coisas ao mesmo tempo:

1. o engine e o `OpenAIPlanner` sao robustos o bastante para convergir sob permutacao de rotulos e de branch correto, desde que o budget seja suficiente
2. a politica efetiva continua fortemente sensivel a ordem de apresentacao das acoes `assume_role`

Em termos praticos:

- ha backtracking real
- ha memoria de branch
- ha convergencia
- mas a escolha entre pivots ainda e pouco invariavel a ordenacao

## Interpretacao
H1 foi confirmada:

- o planner convergiu nas tres permutacoes quando o budget foi elevado para `max_steps=8`

H2 foi confirmada:

- o planner percorreu os pivots exatamente na ordem apresentada em todas as variantes

H3 foi confirmada:

- a falha inicial com `max_steps=5` foi de budget, nao de colapso de busca

Isso e importante metodologicamente:

- o engine ja nao depende de um unico ordering para convergir
- mas a estrategia de busca ainda nao e order-invariant

## Implicacoes arquiteturais
- `candidate_paths` continua escalando para multiplas permutacoes do mesmo problema
- `failed_assume_roles` e `action_shaping` evitam revisita inutil e preservam progresso
- a proxima lacuna clara e `path scoring`
- order sensitivity virou tema proprio de experimento, e nao apenas detalhe incidental

## Ameacas a validade
- o experimento foi feito em `dry_run`
- os branches continuam simetricos apenas ate certo ponto; a diferenca do branch correto aparece quando `s3_read_sensitive` e liberado
- o planner pode continuar influenciado por detalhes sutis de apresentacao alem da ordem

## Conclusao
O EXP-007 confirmou que:

- o engine converge nas tres permutacoes relevantes do Path 5 quando o budget permite
- a arquitetura atual suporta variacao de rotulo e do branch correto
- a order sensitivity continua forte e precisa de tratamento proprio se o objetivo for prioridade inteligente entre pivots

## Proximos experimentos
- EXP-008: `path scoring` e order invariance — hipotese: adicionar ranking explicito de pivots reduz dependencia da ordem de `available_actions`
- EXP-009: deeper branches — hipotese: com maior profundidade de branch, o sistema continua convergindo sem revisitar dead-ends
