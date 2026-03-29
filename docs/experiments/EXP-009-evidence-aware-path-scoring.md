# EXP-009 — Evidence-Aware Path Scoring

## Identificacao
- ID: EXP-009
- Fase: 3
- Pre-requisito: EXP-008 concluido
- Status: melhora parcial confirmada; gargalo restante isolado

## Contexto
O EXP-008 mostrou que `path_score` estrutural melhorava a eficiencia em parte
das permutacoes do EXP-007, mas ainda falhava no pior caso:

- quando o branch correto era o ultimo a ser explorado
- e nenhuma evidencia util aparecia antes dele

O problema passou a ser:

- como ranquear melhor candidate paths usando sinais observados no branch
- sem hardcode de cenario

## Hipoteses
H1: se o `path_score` incorporar evidencia observada no branch, a ordem de exploracao melhora.

H2: a melhora sera mais forte quando um branch revelar sinal relevante cedo.

H3: isso ainda nao sera suficiente quando o branch correto nao revelar evidencia antes de ser testado.

## Desenho experimental

### Variavel independente
- `path_score` estrutural do EXP-008
- `path_score` estrutural + evidência observada do branch

### Ambiente
- mesmas tres variantes do EXP-007:
  - `rolea_success`
  - `rolem_success`
  - `roleq_success`
- `dry_run`
- `OpenAIPlanner`
- `max_steps=8`

### Sinais de evidencia adicionados
- `discovered_objects`
- `evidence.object_key`
- match exato com o nome final do alvo
- overlap lexical entre objetos observados e `objective.target`

### Criterio de sucesso
- reduzir o numero de passos em pelo menos uma variante alem do obtido no EXP-008
- manter convergencia nas tres variantes
- isolar claramente quando a evidencia observada basta e quando nao basta

## Implementacao

### Estado
`CandidatePath` passou a expor:

- `observed_resources`

O `path_score` passou a incluir:

- score estrutural
- score por recursos observados no branch

Arquivo:

- `src/core/state.py`

### Prompting
O prompt passou a incluir:

- `observed_resources`

E a instruir o planner a tratar recursos observados proximos do alvo como
evidencia forte.

Arquivo:

- `src/planner/prompting.py`

## Validacao offline
Foram adicionados testes garantindo:

- que um branch que revela `payroll.csv` ganha score maior que um branch sem
  esse sinal
- que o score estrutural anterior continua valido
- que as variantes parametrizadas do EXP-007 continuam convergindo em dry-run

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

- EXP-008: `6` passos
- EXP-009: `4` passos

Leitura:

- o score por evidencia ajudou porque o branch correto passou a ficar mais
  valorizado quando seu potencial ficou claro

### Variante `rolem_success`
Resultado:

- `objective_met: True`
- passos: `6`

Caminho:

1. `iam_list_roles`
2. `assume_role -> RoleA`
3. `s3_list_bucket`
4. `assume_role -> RoleM`
5. `s3_list_bucket`
6. `s3_read_sensitive`

Comparacao:

- EXP-008: `6` passos
- EXP-009: `6` passos

Leitura:

- nao houve regressao
- tambem nao houve ganho adicional

### Variante `roleq_success`
Resultado:

- `objective_met: True`
- passos: `8`

Caminho:

1. `iam_list_roles`
2. `assume_role -> RoleA`
3. `s3_list_bucket`
4. `assume_role -> RoleM`
5. `s3_list_bucket`
6. `assume_role -> RoleQ`
7. `s3_list_bucket`
8. `s3_read_sensitive`

Comparacao:

- EXP-008: `8` passos
- EXP-009: `8` passos

Leitura:

- o pior caso continuou sem melhora

## Problemas observados e como foram corrigidos

### Problema 1 — Score estrutural insuficiente
Sintoma:

- o EXP-008 ainda exigia explorar pivots errados em parte dos casos

Causa:

- o ranking usava apenas status, `times_tested` e progresso estrutural

Correcao:

- adicionar `observed_resources`
- incorporar match com o alvo ao `path_score`

### Problema 2 — Ausencia de evidencia antes do branch correto
Sintoma:

- `roleq_success` continuou em `8` passos

Causa:

- o branch correto nao gerava evidencia observada antes de ser testado
- logo, o score observacional nao tinha como promovê-lo cedo

Correcao:

- nao resolvida no EXP-009
- o problema ficou isolado para o proximo corte

## Descoberta principal
O EXP-009 revelou dois regimes:

1. `evidence-friendly`
   - quando um branch revela sinal util cedo, o ranking melhora bastante
2. `evidence-starved`
   - quando o branch correto so revela informacao util depois de ser testado,
     o score observacional nao basta

## Interpretacao
H1 foi confirmada parcialmente:

- houve melhora clara em `rolea_success`

H2 foi confirmada:

- a melhora foi mais forte exatamente onde o branch correto ficou evidence-friendly

H3 foi confirmada:

- o pior caso nao melhorou

## Implicacoes arquiteturais
- `candidate_paths` passou a carregar memoria observacional real
- o engine ficou capaz de aprender com o que um branch revelou
- o proximo passo precisaria olhar nao apenas para o passado do branch, mas
  tambem para seu potencial futuro

## Ameacas a validade
- experimento em `dry_run`
- o score observacional depende de nomes de objetos presentes no fixture
- a ausencia de melhora em `roleq_success` pode depender do quao tarde o sinal
  do branch correto aparece no cenario

## Conclusao
O EXP-009 foi util, mas insuficiente como solucao geral:

- melhorou um caso de forma significativa
- nao regrediu os demais
- deixou claro que o gargalo restante era falta de `lookahead`

## Proximos experimentos
- EXP-010: lookahead-aware path scoring — hipotese: sinais do proximo passo do
  branch resolvem o pior caso evidence-starved
