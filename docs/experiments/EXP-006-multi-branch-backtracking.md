# EXP-006 — Backtracking com Tres Pivos Concorrentes

## Identificacao
- ID: EXP-006
- Fase: 3
- Pre-requisito: EXP-005 concluido
- Status: hipotese principal confirmada apos endurecimento iterativo do Path 5

## Contexto
O EXP-005 mostrou que o engine ja conseguia:

- manter `candidate_paths`
- explorar um branch ativo antes de trocar de pivo
- abandonar um dead-end e tentar o proximo candidate path

Mas isso ainda estava provado principalmente num caso binario:

- 2 roles concorrentes
- 1 dead-end
- 1 branch correto

O proximo passo natural foi testar se o mesmo mecanismo continuava valido quando o espaco de decisao crescia.

O Path 5 foi desenhado para responder a pergunta certa:

- o engine consegue atravessar mais de um dead-end consecutivo sem revisitar branches ja esgotados e ainda convergir no ultimo pivo valido?

## Hipoteses
H1: com `candidate_paths` + `failed_assume_roles` + `action_shaping`, o engine consegue navegar tres pivots concorrentes sem entrar em loop.

H2: o `OpenAIPlanner` consegue abandonar dois dead-ends consecutivos e convergir no terceiro pivo quando o cenario realmente exige exploracao de branch.

H3: se o planner continuar acertando de primeira, o problema deixa de ser backtracking e passa a ser desenho experimental facil demais, com excesso de sinal semantico no cenario.

## Desenho experimental

### Variavel independente
- versao inicial do Path 5 com tres roles semanticamente legiveis
- versao endurecida 1, com nomes menos obvios mas ainda semanticos
- versao endurecida 2, com nomes neutros (`RoleA`, `RoleM`, `RoleQ`) e branches mais simetricos
- orcamento de passos: `max_steps=5` e depois `max_steps=8`

### Ambiente
- `dry_run`
- tres roles assumiveis a partir do usuario inicial
- dois branches mortos
- um branch correto
- mesmo bucket final, para reduzir pistas artificiais de infraestrutura

### Criterio de sucesso
- o planner nao revisita branches mortos ja esgotados
- o planner consegue abrir um branch, explorar, abandonar, abrir o proximo, explorar, abandonar, e seguir para o ultimo branch valido
- o run final chega ao objeto sensivel depois de mais de um backtracking real

## Linha do tempo experimental

### Etapa 1 — Path 5 inicial com tres roles semanticamente legiveis
Artefatos criados:

- `fixtures/aws_multi_branch_backtracking_lab.json`
- `examples/objective_aws_multi_branch_backtracking.json`
- `examples/scope_aws_multi_branch_backtracking.json`
- `examples/scope_aws_multi_branch_backtracking_openai.json`

Desenho inicial:

- `A-FinanceAuditRole` -> dead-end 1
- `M-LogsReviewRole` -> dead-end 2
- `Z-DataOpsRole` -> branch correto

Resultado com `OpenAIPlanner`:

1. `iam_list_roles`
2. `assume_role -> Z-DataOpsRole`
3. `s3_read_sensitive -> payroll.csv`

Leitura:

- o run passou
- nao houve backtracking
- o planner escolheu o pivo correto de primeira

Causa isolada:

- o cenario ainda estava semantica e estruturalmente legivel demais
- nomes como `DataOpsRole` e `StorageBrokerRole` carregavam sinal excessivo sobre qual branch levava a S3 e ao objeto final

### Etapa 2 — Endurecimento 1: reduzir a obviedade do branch correto
O Path 5 foi endurecido para:

- tornar os dois dead-ends mais plausiveis
- tornar o branch correto menos obvio pelo nome
- exigir enumeracao antes do acesso final no branch correto

Resultado com `OpenAIPlanner`:

1. `iam_list_roles`
2. `assume_role -> Q-StorageBrokerRole`
3. `s3_list_bucket -> payroll.csv`
4. `s3_read_sensitive -> payroll.csv`

Leitura:

- o planner ainda escolheu o branch correto de primeira
- o endurecimento foi insuficiente

Causa isolada:

- ainda havia sinal semantico forte nos nomes
- ainda havia assimetria no branch correto, que revelava `payroll.csv` de forma relativamente direta

### Etapa 3 — Endurecimento 2: neutralizacao semantica e simetria de branch
O Path 5 foi redesenhado para:

- neutralizar os nomes das roles:
  - `RoleA`
  - `RoleM`
  - `RoleQ`
- fazer os tres branches parecerem estruturalmente parecidos
- fazer cada role ganhar `s3:ListBucket` no mesmo bucket
- fazer cada branch listar um objeto plausivel
- deixar `s3_read_sensitive` disponivel apenas apos exploracao do branch correto

Mapeamento final do Path 5:

- `RoleA` -> lista `records-archive.csv` -> dead-end
- `RoleM` -> lista `reports-summary.csv` -> dead-end
- `RoleQ` -> lista `payroll.csv` -> branch correto

### Etapa 4 — Path 5 endurecido com `max_steps=5`
Resultado com `OpenAIPlanner`:

1. `iam_list_roles`
2. `assume_role -> RoleA`
3. `s3_list_bucket -> records-archive.csv`
4. `assume_role -> RoleM`
5. `s3_list_bucket -> reports-summary.csv`

Resultado:

- `objective_met: False`

Leitura:

- o endurecimento finalmente funcionou
- o planner deixou de acertar de primeira
- houve backtracking real entre multiplos branches
- o run falhou apenas por falta de orcamento de passos

Causa isolada da falha:

- `max_steps=5` era insuficiente para:
  - enumerar
  - explorar dead-end 1
  - explorar dead-end 2
  - abrir branch 3
  - enumerar branch 3
  - acessar o objeto final

### Etapa 5 — Path 5 endurecido com `max_steps=8`
Resultado com `OpenAIPlanner`:

1. `iam_list_roles`
2. `assume_role -> RoleA`
3. `s3_list_bucket -> records-archive.csv`
4. `assume_role -> RoleM`
5. `s3_list_bucket -> reports-summary.csv`
6. `assume_role -> RoleQ`
7. `s3_list_bucket -> payroll.csv`
8. `s3_read_sensitive -> payroll.csv`

Resultado:

- `objective_met: True`

Isso confirmou:

- dois dead-ends consecutivos
- abandono de branch esgotado sem revisita inutil
- escolha do ultimo pivo ainda nao testado
- convergencia final apos multiplos backtrackings

## Problemas observados e como foram corrigidos

### Problema 1 — Cenario facil demais por semantica de nomes
Sintoma:

- o planner escolhia o branch correto de primeira no Path 5 inicial

Causa:

- nomes das roles carregavam sinal excessivo sobre o branch correto

Correcao:

- reduzir sinal semantico no endurecimento 1
- depois neutralizar completamente os nomes no endurecimento 2

### Problema 2 — Assimetria estrutural do branch correto
Sintoma:

- mesmo com nomes menos obvios, o planner ainda acertava cedo demais

Causa:

- o branch correto continuava estruturalmente mais informativo que os dead-ends

Correcao:

- tornar os tres branches mais simetricos
- exigir `s3_list_bucket` antes de `s3_read_sensitive` tambem no branch correto
- fazer todos os branches listarem objetos plausiveis antes da diferenciacao final

### Problema 3 — Orcamento de passos insuficiente
Sintoma:

- o planner demonstrava backtracking correto, mas o run terminava sem objetivo met

Causa:

- `max_steps=5` nao cobria toda a profundidade do cenario endurecido

Correcao:

- rerun com `--max-steps 8`

## Descoberta principal
A descoberta principal do EXP-006 foi dupla:

1. o mecanismo de backtracking introduzido no EXP-005 continua valido quando o espaco de decisao cresce de 2 para 3 pivots concorrentes
2. a qualidade do experimento depende fortemente de neutralizar pistas semanticas e assimetrias estruturais do branch correto

Ou seja:

- se o cenario tiver sinal semantico demais, o planner pode acertar sem precisar backtrackear
- quando o sinal e removido e o branch correcto so se torna evidente apos exploracao, o comportamento de backtracking aparece de forma observavel

## Interpretacao
H1 foi confirmada:

- o engine conseguiu navegar tres pivots concorrentes sem colapsar em loop

H2 foi confirmada no run final com `max_steps=8`:

- houve abandono de dois dead-ends consecutivos antes da convergencia no terceiro branch

H3 tambem foi confirmada:

- os primeiros passes sem backtracking nao significavam ausencia de capacidade
- significavam desenho experimental facil demais

Esse ponto e metodologicamente importante:

- um planner forte pode mascarar a ausencia de dificuldade experimental
- por isso, parte do trabalho cientifico aqui passa a ser desenhar cenarios que removam pistas acidentais demais

## Implicacoes arquiteturais
- `candidate_paths` e `failed_assume_roles` escalam para mais de dois pivots
- `action_shaping` continua valido em cenarios de branching mais amplos
- a avaliacao do planner precisa separar claramente:
  - convergencia facil
  - backtracking real
- nomes, ordem e simetria dos branches passam a ser parte explicita do desenho experimental

## Ameacas a validade
- o EXP-006 ainda foi validado apenas em `dry_run`
- o `OpenAIPlanner` pode responder a pequenos detalhes de wording no objetivo e no prompt
- o cenario continua sendo uma arvore rasa; ainda nao ha profundidade grande nem branching irregular
- nao foi medido ainda comportamento estatistico em varias seeds/reruns com embaralhamento de ordem de acoes

## Conclusao
O EXP-006 confirmou que o engine atual consegue suportar backtracking com mais de dois pivots concorrentes, desde que o cenario realmente force exploracao e reduza pistas semanticas acidentais.

A versao final do Path 5 mostrou o comportamento que o projeto precisava provar:

- explorar um primeiro dead-end
- abandonar
- explorar um segundo dead-end
- abandonar
- convergir no terceiro branch valido

Esse foi o primeiro experimento a demonstrar backtracking repetido de forma clara no planner LLM.

## Proximos experimentos
- EXP-007: embaralhar ordem das acoes e nomes de roles para medir robustez contra vies de apresentacao
- EXP-008: aumentar profundidade de um dead-end para mais de um nivel antes do retorno
- EXP-009: levar um cenario multi-branch equivalente para AWS real quando o custo operacional justificar

## Artefatos
- `fixtures/aws_multi_branch_backtracking_lab.json`
- `examples/objective_aws_multi_branch_backtracking.json`
- `examples/scope_aws_multi_branch_backtracking.json`
- `examples/scope_aws_multi_branch_backtracking_openai.json`
