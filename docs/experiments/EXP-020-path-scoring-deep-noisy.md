# EXP-020 — Path Scoring com Branch Profundo e Ruido

## Identificacao
- ID: EXP-020
- Fase: 3
- Pre-requisito: EXP-019 concluido
- Status: concluido

## Contexto
EXP-019 mostrou que o scoring prioriza o bucket correto mesmo com decoys.
EXP-020 adiciona profundidade: o branch correto requer `enumerate -> analyze -> access_resource`.
O objetivo e verificar se o scoring e o shaping mantem a preferencia correta
quando o caminho exige um passo adicional de `analyze`.

## Hipoteses
H1: o scoring continua priorizando o branch correto mesmo quando o acesso
    depende de `analyze` para liberar o recurso final.

H2: o backtracking permanece estavel com `max_steps=9` e nao converge para
    decoys quando o branch correto exige profundidade extra.

## Desenho experimental

### Variavel independente
- branch correto exige `enumerate -> analyze -> access_resource`
- pivots errados mantem `access_resource` decoy imediato
- permutacao de ordem das `assume_role`
- branch correto alternando entre `RoleA`, `RoleM` e `RoleQ`

### Ambiente
- `dry_run`
- bucket alvo: `sensitive-finance-data`
- bucket decoy: `public-reports`
- roles neutras: `RoleA`, `RoleM`, `RoleQ`
- apenas uma role por variante possui acesso ao bucket alvo, mas exige `analyze`

### Variantes
- `deep_noisy_rolea_success`
  - ordem inicial: `RoleQ -> RoleM -> RoleA`
  - branch correto: `RoleA`
- `deep_noisy_rolem_success`
  - ordem inicial: `RoleA -> RoleQ -> RoleM`
  - branch correto: `RoleM`
- `deep_noisy_roleq_success`
  - ordem inicial: `RoleM -> RoleA -> RoleQ`
  - branch correto: `RoleQ`

Artefatos:
- `fixtures/aws_permuted_branching_deep_noisy_rolea_success_lab.json`
- `fixtures/aws_permuted_branching_deep_noisy_rolem_success_lab.json`
- `fixtures/aws_permuted_branching_deep_noisy_roleq_success_lab.json`
- `examples/objective_aws_permuted_branching_deep_noisy.json`
- `examples/scope_aws_permuted_branching_deep_noisy.json`
- `examples/scope_aws_permuted_branching_deep_noisy_openai.json`

### Criterio de sucesso
- convergir nas tres variantes com `max_steps=9`
- scoring prioriza o branch correto ou backtracking corrige rapidamente

## Resultados por etapa

### Etapa 1 — Execucao dry_run com OpenAIPlanner
- Resultado: falhou nas tres variantes.
- Comportamento observado: alternou `assume_role` entre RoleA/RoleM/RoleQ,
  executou `enumerate` e caiu no decoy `public-reports/payroll.csv`.
- Sintoma: nenhum `analyze` foi executado; o branch correto foi abandonado
  antes de desbloquear o `access_resource` real.
- Passos: convergiu em 9 passos, mas sempre no decoy.

### Etapa 2 — Execucao dry_run com OpenAIPlanner apos ajuste no engine
- Resultado: sucesso nas tres variantes.
- Comportamento observado: `enumerate -> analyze -> access_resource` no
  role correto, objetivo atingido em 5 passos em todas as variacoes.

## Erros, intervencoes e motivos
- Erro: branch ativo era descartado quando a unica acao disponivel era
  `analyze`, levando o planner a reiniciar pivots.
- Intervencao: `analyze` passou a contar como acao de progresso no estado
  (branch ativo, contagem e candidate paths).
- Motivo: `analyze` e um passo obrigatorio para desbloquear o recurso final;
  sem isso o engine quebra a sequencia correta mesmo com scoring valido.

## Descoberta principal
- O problema nao era scoring nem modelo. Era a definicao de "progresso"
  do branch. Sem reconhecer `analyze` como progresso, o engine abandona
  caminhos corretos que exigem profundidade adicional.

## Interpretacao
- H1 confirmada: o scoring manteve preferencia correta apos o ajuste
  estrutural de progresso.
- H2 confirmada: backtracking permaneceu estavel e convergiu em 5 passos.

## Implicacoes arquiteturais
- Se H1 falhar, reforcar scoring por sinais estruturais de profundidade
  (ex.: preferir pivots com `analyze` que desbloqueia target real).

## Ameacas a validade
- Apenas dry_run.
- Ruido sintetico.

## Conclusao
- H1 confirmada.
- H2 confirmada.
