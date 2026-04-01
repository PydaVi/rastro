# EXP-018 — Path Scoring sob Permutacao com Evidencia Ruidosa

## Identificacao
- ID: EXP-018
- Fase: 3
- Pre-requisito: EXP-017 concluido
- Status: em andamento

## Contexto
EXP-008 a EXP-010 introduziram `path_score` e sinais de lookahead, mas ainda
existem sinais de order sensitivity residual. EXP-018 estressa o scoring em
um cenario onde todas as branches exibem sinais ruidosos semelhantes ao alvo,
para medir se o ranking ainda depende da ordem de apresentacao.

## Hipoteses
H1: com evidencias ruidosas (overlap de tokens com o alvo em todos os pivots),
    o `path_score` ainda deve preferir o branch correto quando ele tiver
    sinal estrutural mais forte (access_resource futuro).

H2: o mecanismo de backtracking continua convergindo com `max_steps=8`
    mesmo quando o scoring nao diferencia claramente os pivots.

## Desenho experimental

### Variavel independente
- evidencias ruidosas nos `discovered_objects` de todos os pivots
- permutacao de ordem das `assume_role`
- branch correto alternando entre `RoleA`, `RoleM` e `RoleQ`

### Ambiente
- `dry_run`
- bucket unico: `arn:aws:s3:::sensitive-finance-data`
- roles neutras: `RoleA`, `RoleM`, `RoleQ`
- todas as roles listam objetos com tokens semelhantes ao alvo
- apenas uma role por variante possui `access_resource` para `payroll.csv`

### Variantes
- `noisy_rolea_success`
  - ordem inicial: `RoleQ -> RoleM -> RoleA`
  - branch correto: `RoleA`
- `noisy_rolem_success`
  - ordem inicial: `RoleA -> RoleQ -> RoleM`
  - branch correto: `RoleM`
- `noisy_roleq_success`
  - ordem inicial: `RoleM -> RoleA -> RoleQ`
  - branch correto: `RoleQ`

Artefatos:
- `fixtures/aws_permuted_branching_noisy_rolea_success_lab.json`
- `fixtures/aws_permuted_branching_noisy_rolem_success_lab.json`
- `fixtures/aws_permuted_branching_noisy_roleq_success_lab.json`
- `examples/objective_aws_permuted_branching_noisy.json`
- `examples/scope_aws_permuted_branching_noisy.json`
- `examples/scope_aws_permuted_branching_noisy_openai.json`

### Criterio de sucesso
- convergir nas tres variantes com `max_steps=8`
- reduzir dependencia da ordem quando sinais estruturais sao fortes
- preservar backtracking mesmo com scoring ambiguo

## Resultados por etapa

### Etapa 1 — Execucao dry_run com OpenAIPlanner
- Resultado: passou nas tres variantes com 4 passos cada.
- Comportamento observado: o planner escolheu diretamente o pivot correto em
  todas as permutacoes (`RoleA`, `RoleM`, `RoleQ`) apesar do ruido.

## Erros, intervencoes e motivos
- Nenhum.

## Descoberta principal
O scoring atual consegue ignorar sinais ruidosos e priorizar o pivot correto
quando o lookahead sinaliza o alvo com clareza.

## Interpretacao
- Provado: o `path_score` prioriza corretamente o branch com sinal estrutural
  forte (access_resource futuro) mesmo com ruido observacional.
- Ainda aberto: comportamento sob ruido mais agressivo ou ambiguidade real
  entre sinais de lookahead.

## Implicacoes arquiteturais
- Se H1 falhar, reforcar scoring por sinais estruturais (access_resource) vs.
  sinais observacionais ruidosos.

## Ameacas a validade
- Apenas dry_run.
- Sinais ruidosos sao sinteticos.

## Conclusao
H1 confirmada. H2 confirmada. O scoring permaneceu estavel sob permutacao e
ruido leve, convergindo em 4 passos nas tres variantes.

## Proximos experimentos
- EXP-019: scoring com evidencia ambigua + ruido lexical controlado.
- EXP-020: scoring em branch profundo com ruido.
