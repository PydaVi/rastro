# EXP-019 — Path Scoring com Evidencia Ambigua e Decoy Access

## Identificacao
- ID: EXP-019
- Fase: 3
- Pre-requisito: EXP-018 concluido
- Status: em andamento

## Contexto
EXP-018 confirmou que o scoring se mantem estavel sob ruido leve quando o
lookahead sinaliza o alvo de forma clara. EXP-019 aumenta a ambiguidade ao
introduzir caminhos de acesso falsos (decoy) que expõem um `payroll.csv`
fora do bucket alvo, forçando o scoring a lidar com sinais de nome iguais
mas contexto errado.

## Hipoteses
H1: o scoring deve preferir o pivot cujo access_resource aponta exatamente para
    o alvo (bucket correto), mesmo que os outros pivots exponham um `payroll.csv`
    em bucket decoy.

H2: o backtracking continua convergindo com `max_steps=8` mesmo se o scoring
    escolher um decoy primeiro.

## Desenho experimental

### Variavel independente
- introducao de access_resource decoy (`public-reports/payroll.csv`) nos pivots errados
- permutacao de ordem das `assume_role`
- branch correto alternando entre `RoleA`, `RoleM` e `RoleQ`

### Ambiente
- `dry_run`
- bucket alvo: `sensitive-finance-data`
- bucket decoy: `public-reports`
- roles neutras: `RoleA`, `RoleM`, `RoleQ`
- todas as roles listam objetos com tokens semelhantes ao alvo
- apenas uma role por variante possui `access_resource` para o bucket alvo
- as outras duas possuem `access_resource` para o bucket decoy

### Variantes
- `ambiguous_rolea_success`
  - ordem inicial: `RoleQ -> RoleM -> RoleA`
  - branch correto: `RoleA`
- `ambiguous_rolem_success`
  - ordem inicial: `RoleA -> RoleQ -> RoleM`
  - branch correto: `RoleM`
- `ambiguous_roleq_success`
  - ordem inicial: `RoleM -> RoleA -> RoleQ`
  - branch correto: `RoleQ`

Artefatos:
- `fixtures/aws_permuted_branching_ambiguous_rolea_success_lab.json`
- `fixtures/aws_permuted_branching_ambiguous_rolem_success_lab.json`
- `fixtures/aws_permuted_branching_ambiguous_roleq_success_lab.json`
- `examples/objective_aws_permuted_branching_ambiguous.json`
- `examples/scope_aws_permuted_branching_ambiguous.json`
- `examples/scope_aws_permuted_branching_ambiguous_openai.json`

### Criterio de sucesso
- convergir nas tres variantes com `max_steps=8`
- scoring prioriza o bucket correto (ou backtracking corrige quando escolhe decoy)

## Resultados por etapa

### Etapa 1 — Execucao dry_run com OpenAIPlanner
- Resultado: passou nas tres variantes com 4 passos cada.
- Comportamento observado: o planner escolheu diretamente o pivot correto em
  todas as permutacoes (`RoleA`, `RoleM`, `RoleQ`) apesar dos decoys.
- Observacao: nenhum backtracking foi necessario porque o scoring convergiu
  no primeiro pivot em todos os casos.

## Erros, intervencoes e motivos
- Nenhum.

## Descoberta principal
O scoring atual diferencia o bucket alvo mesmo com access_resource decoy,
priorizando o pivot correto sem precisar de backtracking.

## Interpretacao
- Provado: sinais de lookahead com ARN completo superam ambiguidade de nome.
- Ainda aberto: cenarios onde o lookahead nao inclui o ARN completo do alvo.

## Implicacoes arquiteturais
- Se H1 falhar, adicionar scoring por contexto de bucket/ARN, nao apenas nome.

## Ameacas a validade
- Apenas dry_run.
- Decoys sao sinteticos.

## Conclusao
H1 confirmada. H2 confirmada (por convergencia direta). O scoring ignorou
decoys e convergiu em 4 passos nas tres variantes.

## Proximos experimentos
- EXP-020: scoring em branch profundo com ruido.
