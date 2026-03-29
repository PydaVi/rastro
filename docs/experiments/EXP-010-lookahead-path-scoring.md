# EXP-010 — Lookahead-Aware Path Scoring

## Identificacao
- ID: EXP-010
- Fase: 3
- Pre-requisito: EXP-009 concluido
- Status: hipotese principal confirmada

## Contexto
O EXP-009 mostrou que o ranking por evidencia observada ajuda quando um branch
revela sinal forte cedo, mas nao resolve o pior caso:

- se o branch correto ainda nao foi explorado
- ele ainda nao gerou evidencia observada
- logo continua subpriorizado

Isso isolou a necessidade de um novo tipo de sinal:

- nao apenas o que o branch ja revelou
- mas o que o branch parece prometer no proximo passo

## Hipoteses
H1: se o `path_score` incorporar sinais de `lookahead`, o planner reduz a
dependencia de explorar pivots errados antes de chegar ao branch correto.

H2: `lookahead` resolve o pior caso do EXP-009, quando o branch correto era o
ultimo na permutacao.

H3: com `lookahead`, as tres variantes do benchmark convergem no caminho minimo
esperado.

## Desenho experimental

### Variavel independente
- `path_score` estrutural + evidencia observada do EXP-009
- `path_score` estrutural + evidencia observada + `lookahead`

### Ambiente
- mesmas tres variantes do benchmark:
  - `rolea_success`
  - `rolem_success`
  - `roleq_success`
- `dry_run`
- `OpenAIPlanner`
- `max_steps=8`

### Sinais de lookahead adicionados
- `access_resource` disponivel em acoes futuras do branch
- `object_key` em acoes futuras
- `prefix` em acoes futuras
- `discovered_objects` previstos na transicao seguinte do branch

### Criterio de sucesso
- reduzir `rolea_success`, `rolem_success` e `roleq_success` para o caminho
  minimo de 4 passos:
  1. `iam_list_roles`
  2. `assume_role`
  3. `s3_list_bucket`
  4. `s3_read_sensitive`

## Implementacao

### Estado
`CandidatePath` passou a expor:

- `lookahead_signals`

O `path_score` passou a incluir:

- score estrutural
- score por evidencia observada
- score por `lookahead`

O `lookahead` foi calculado a partir de:

- acoes futuras no branch
- sinais presentes na transicao de `assume_role`
- objetos previstos na transicao seguinte do branch

Arquivo:

- `src/core/state.py`

### Prompting
O prompt passou a expor:

- `lookahead_signals`

E a instruir o planner a usalos no ranking antes de explorar o branch.

Arquivo:

- `src/planner/prompting.py`

## Validacao offline
Foram adicionados testes garantindo:

- que um branch correto ainda nao testado pode ganhar score por `lookahead`
- que esse score supera um branch nao correto sem precisar de evidencia observada
- que as variantes do benchmark continuam passando

Resultado:

- os testes offline passaram

## Resultados com OpenAIPlanner

### Variante `rolea_success`
Resultado:

- `objective_met: True`
- passos: `4`

Caminho:

1. `iam_list_roles`
2. `assume_role -> RoleA`
3. `s3_list_bucket`
4. `s3_read_sensitive`

Comparacao:

- EXP-009: `4` passos
- sem regressao

### Variante `rolem_success`
Resultado:

- `objective_met: True`
- passos: `4`

Caminho:

1. `iam_list_roles`
2. `assume_role -> RoleM`
3. `s3_list_bucket`
4. `s3_read_sensitive`

Comparacao:

- EXP-009: `6` passos
- melhora clara

### Variante `roleq_success`
Resultado:

- `objective_met: True`
- passos: `4`

Caminho:

1. `iam_list_roles`
2. `assume_role -> RoleQ`
3. `s3_list_bucket`
4. `s3_read_sensitive`

Comparacao:

- EXP-009: `8` passos
- melhora decisiva no pior caso

## Problemas observados e como foram corrigidos

### Problema 1 — Branch correto nao produzia evidencia cedo
Sintoma:

- no EXP-009 o branch correto podia continuar sendo o ultimo explorado

Causa:

- o ranking usava apenas sinais do passado observacional do branch

Correcao:

- adicionar `lookahead_signals`
- permitir que o score use o potencial imediato do branch

### Problema 2 — Score observacional nao capturava potencial de `access_resource`
Sintoma:

- o planner ainda percorria pivots errados antes do correto no pior caso

Causa:

- a existencia de `access_resource` futuro e de `object_key` relevante nao
  entrava no ranking antes do branch ser testado

Correcao:

- incorporar `access_resource`, `object_key`, `prefix` e `discovered_objects`
  previstos no `lookahead`

## Descoberta principal
O EXP-010 confirmou que:

- `lookahead` era o sinal que faltava para resolver a order sensitivity no
  benchmark atual
- com ele, o planner passa a escolher diretamente o branch correto nas tres
  permutacoes

## Interpretacao
H1 foi confirmada:

- a dependencia de explorar pivots errados caiu drasticamente

H2 foi confirmada:

- o pior caso do EXP-009 (`roleq_success`) caiu de `8` para `4` passos

H3 foi confirmada:

- as tres variantes convergiram no caminho minimo esperado

## Implicacoes arquiteturais
- `candidate_paths` agora combinam:
  - memoria estrutural
  - memoria observacional
  - potencial futuro
- o ranking de pivots deixa de ser apenas reativo
- o engine ganha capacidade real de priorizacao preditiva

## Ameacas a validade
- o experimento continua em `dry_run`
- o `lookahead` usa informacao de fixture que pode ser mais rica do que a
  disponivel em ambientes reais sem modelagem adicional
- ainda nao foi testado em branches mais profundos que um unico passo de
  descoberta antes do acesso final

## Conclusao
O EXP-010 foi o primeiro experimento a fechar o benchmark de invariancia de
ordem de forma forte:

- tres permutacoes
- tres branches corretos diferentes
- todas convergindo em `4` passos

Esse foi o primeiro ponto em que o projeto saiu de:

- backtracking correto

para:

- priorizacao preditiva efetiva entre pivots concorrentes

## Proximos experimentos
- EXP-011: branches mais profundos — hipotese: o lookahead atual continua
  suficiente quando o branch correto exige mais de um passo antes de liberar
  `access_resource`
- EXP-012: nova familia de attack paths — hipotese: o mesmo mecanismo de score
  se transfere para caminhos fora de IAM->S3
