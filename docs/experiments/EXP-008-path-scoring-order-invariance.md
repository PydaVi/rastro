# EXP-008 — Path Scoring e Invariancia Parcial a Ordem

## Identificacao
- ID: EXP-008
- Fase: 3
- Pre-requisito: EXP-007 concluido
- Status: primeiro corte implementado; melhora parcial confirmada

## Contexto
O EXP-007 mostrou que o engine ja conseguia:

- convergir sob permutacao do branch correto
- convergir sob permutacao da ordem das `assume_role`
- evitar loop mesmo em cenarios multi-branch

Mas deixou uma lacuna clara:

- o planner ainda percorria os pivots basicamente na ordem apresentada em `available_actions`

O problema deixou de ser apenas backtracking.
Passou a ser:

- order sensitivity
- falta de priorizacao explicita entre candidate paths

## Hipoteses
H1: adicionar `path_score` ao estado e usar esse score no `action shaping` reduz dependencia da ordem de `available_actions`.

H2: mesmo um score simples, geral e nao hardcoded ao cenario, melhora a eficiencia de convergencia em parte das permutacoes do EXP-007.

H3: um primeiro corte de `path_score` ainda nao sera suficiente para eliminar completamente a dependencia de ordering.

## Desenho experimental

### Variavel independente
- engine anterior, sem `path_score`
- engine com `path_score` exposto em `candidate_paths`
- `action shaping` ordenando pivots por score em vez de apenas respeitar a ordem de apresentacao

### Ambiente
- mesmas tres variantes do EXP-007:
  - `rolea_success`
  - `rolem_success`
  - `roleq_success`
- `dry_run`
- `OpenAIPlanner`
- `max_steps=8`

### Heuristica de score
Primeiro corte implementado:

- `active`: bonus alto
- `untested`: bonus relevante
- `tested`: bonus leve
- `failed`: penalizacao forte
- `has_progress_actions`: bonus adicional
- `times_tested`: penalizacao incremental

### Criterio de sucesso
- reduzir o numero de passos em pelo menos parte das variantes
- alterar o comportamento de exploracao para nao seguir cegamente a ordem apresentada em todos os casos
- manter convergencia nas tres variantes

## Implementacao

### Estado
`CandidatePath` passou a expor:

- `path_score`

Arquivos:

- `src/core/state.py`

### Policy layer
`shape_available_actions()` passou a:

- ordenar candidate paths por `path_score` descendente
- usar `target` como desempate estavel
- retornar acoes `assume_role` nessa ordem ranqueada

Arquivos:

- `src/planner/action_shaping.py`

### Prompting
O prompt passou a expor:

- `candidate_paths[].path_score`

E a instruir:

- preferir o candidate path de maior score, e nao a ordem de apresentacao

Arquivos:

- `src/planner/prompting.py`

## Validacao offline
Foram adicionados testes para:

- exposicao de `path_score` no snapshot
- ordenacao estavel de pivots por score
- manutencao das variantes parametrizadas do EXP-007

Resultado:

- os testes offline passaram

## Resultados com OpenAIPlanner

### Variante `rolea_success`
Resultado:

- `objective_met: True`
- passos: `6`

Caminho observado:

1. `iam_list_roles`
2. `assume_role -> RoleM`
3. `s3_list_bucket`
4. `assume_role -> RoleA`
5. `s3_list_bucket`
6. `s3_read_sensitive`

Comparacao com EXP-007:

- antes: `8` passos
- agora: `6` passos

Leitura:

- o planner nao precisou consumir todos os pivots
- houve melhora real de eficiencia

### Variante `rolem_success`
Resultado:

- `objective_met: True`
- passos: `6`

Caminho observado:

1. `iam_list_roles`
2. `assume_role -> RoleA`
3. `s3_list_bucket`
4. `assume_role -> RoleM`
5. `s3_list_bucket`
6. `s3_read_sensitive`

Comparacao com EXP-007:

- antes: `8` passos
- agora: `6` passos

Leitura:

- novamente houve convergencia com menos exploracao inutil

### Variante `roleq_success`
Resultado:

- `objective_met: True`
- passos: `8`

Caminho observado:

1. `iam_list_roles`
2. `assume_role -> RoleA`
3. `s3_list_bucket`
4. `assume_role -> RoleM`
5. `s3_list_bucket`
6. `assume_role -> RoleQ`
7. `s3_list_bucket`
8. `s3_read_sensitive`

Comparacao com EXP-007:

- antes: `8` passos
- agora: `8` passos

Leitura:

- nao houve regressao
- mas tambem nao houve melhora

## Problemas observados e como foram corrigidos

### Problema 1 — Order sensitivity forte no EXP-007
Sintoma:

- o planner seguia os pivots basicamente na ordem exposta

Causa:

- ausencia de ranking explicito de candidate paths

Correcao:

- introducao de `path_score`
- ordenacao de pivots por score no shaping

### Problema 2 — Score ainda fraco para distinguir o branch correto tardio
Sintoma:

- a variante `roleq_success` continuou exigindo os `8` passos completos

Causa:

- o score do primeiro corte usa sinais estruturais gerais
- ainda nao incorpora evidencia observacional do branch, como:
  - proximidade entre `discovered_objects` e o alvo do objetivo
  - sinais lexicais entre objetos descobertos e `objective.target`
  - ranking por relevancia observada do branch

Correcao:

- nao implementada ainda
- o problema ficou isolado para o proximo corte

## Descoberta principal
O EXP-008 mostrou que:

- `path_score` melhora a politica de exploracao
- a order sensitivity foi reduzida, mas nao eliminada

Em termos praticos:

- o engine ja nao depende totalmente da ordem de `available_actions`
- mas ainda nao tem um mecanismo forte o suficiente para identificar cedo o branch correto quando ele esta no fim da permutacao

## Interpretacao
H1 foi parcialmente confirmada:

- houve reducao de dependencia de ordering em duas variantes

H2 foi confirmada:

- um score simples, geral e nao hardcoded ja melhorou eficiencia em parte dos casos

H3 foi confirmada:

- o primeiro corte nao resolveu completamente a order sensitivity

## Implicacoes arquiteturais
- `candidate_paths` agora nao sao apenas memoria; viraram base de ranking
- `action_shaping` deixou de ser apenas filtro e passou a incorporar priorizacao
- o proximo salto natural e um `path scoring` guiado por evidencia observacional

## Ameacas a validade
- o experimento continua em `dry_run`
- o score atual ainda e estrutural e pouco semantico
- o planner LLM ainda pode usar sinais proprios do prompt alem do ranking

## Conclusao
O primeiro corte de `path_score` foi valido e util:

- melhorou a eficiencia em duas das tres permutacoes
- manteve convergencia em todas
- reduziu, mas nao eliminou, a dependencia da ordem das acoes

## Proximos experimentos
- EXP-009: evidence-aware path scoring — hipotese: usar `discovered_objects` e proximidade com o alvo reduz ainda mais a order sensitivity
- EXP-010: deeper branch ranking — hipotese: o ranking continua util quando os branches tem profundidade maior que um unico `s3_list_bucket`
