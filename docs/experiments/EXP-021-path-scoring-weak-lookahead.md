# EXP-021 — Path Scoring Adversarial sem Lookahead Forte

## Identificacao
- ID: EXP-021
- Fase: 3
- Pre-requisito: EXP-020 concluido
- Status: concluida

## Contexto
EXP-020 confirmou convergencia com branch profundo quando o lookahead
traz o ARN completo do alvo. EXP-021 remove esse sinal forte: o target
em `access_resource` passa a ser apenas `payroll.csv` (sem bucket),
forcando o scoring a operar com sinais identicos no lookahead.

## Hipoteses
H1: o scoring ainda converge para o branch correto quando o lookahead
    nao diferencia pivots (alvos identicos), usando sinais de branch e `analyze`.

H2: o backtracking permanece estavel com `max_steps=9` sem colapsar em decoys.

## Desenho experimental

### Variavel independente
- targets de `access_resource` iguais ao objetivo para todos os pivots
- branch correto exige `enumerate -> analyze -> access_resource`
- pivots errados mantem `access_resource` decoy imediato
- permutacao de ordem das `assume_role`
- branch correto alternando entre `RoleA`, `RoleM` e `RoleQ`

### Ambiente
- `dry_run`
- bucket alvo: `sensitive-finance-data`
- bucket decoy: `public-reports`
- roles neutras: `RoleA`, `RoleM`, `RoleQ`
- acesso real so desbloqueado apos `analyze`
- lookahead deixa de diferenciar pivots (alvos identicos em access_resource)

### Variantes
- `weak_signal_rolea_success`
  - ordem inicial: `RoleQ -> RoleM -> RoleA`
  - branch correto: `RoleA`
- `weak_signal_rolem_success`
  - ordem inicial: `RoleA -> RoleQ -> RoleM`
  - branch correto: `RoleM`
- `weak_signal_roleq_success`
  - ordem inicial: `RoleM -> RoleA -> RoleQ`
  - branch correto: `RoleQ`

Artefatos:
- `fixtures/aws_permuted_branching_deep_noisy_weak_signal_rolea_success_lab.json`
- `fixtures/aws_permuted_branching_deep_noisy_weak_signal_rolem_success_lab.json`
- `fixtures/aws_permuted_branching_deep_noisy_weak_signal_roleq_success_lab.json`
- `examples/objective_aws_permuted_branching_weak_signal.json`
- `examples/scope_aws_permuted_branching_weak_signal.json`
- `examples/scope_aws_permuted_branching_weak_signal_openai.json`

### Criterio de sucesso
- convergir nas tres variantes com `max_steps=9`
- scoring nao fica preso em decoys mesmo sem lookahead forte

## Resultados por etapa

### Etapa 1 — Execucao dry_run com OpenAIPlanner
- Resultado: falhou nas tres variantes
- Comportamento observado: assumiu pivots e acessou o decoy sem executar `analyze`.
- Sintoma: o branch correto era abandonado quando o acesso rapido via decoy
  aparecia como opcao de progresso.

### Etapa 2 — Execucao dry_run com OpenAIPlanner apos ajuste no engine
- Resultado: sucesso nas tres variantes
- Comportamento observado: convergencia em 5-7 passos, executando
  `enumerate -> analyze -> access_resource` no pivot correto.

## Erros, intervencoes e motivos
- Erro: o engine aceitava access_resource com bucket divergente do objetivo.
- Intervencao: action shaping passou a filtrar access_resource com bucket
  diferente do objetivo e o scoring passou a penalizar mismatch de bucket
  e bonificar analyze que desbloqueia o bucket correto.
- Motivo: sem sinal forte de lookahead, o decoy era tratado como progresso
  valido e desviava o planner do branch correto.

## Descoberta principal
O engine precisa tratar consistencia de bucket como sinal estrutural
forte quando o lookahead e ambiguo. Sem isso, o scoring colapsa para
atalhos falsos.

## Interpretacao
- H1 confirmada apos ajuste estrutural.
- H2 confirmada: backtracking permaneceu estavel e convergiu.

## Implicacoes arquiteturais
- Se H1 falhar, o scoring precisa considerar sinais estruturais extras
  (ex.: peso para bucket do objective mesmo quando target do action
  nao inclui ARN completo).

## Ameacas a validade
- Apenas dry_run.
- Ruido sintetico.

## Conclusao
H1 confirmada. H2 confirmada. O engine agora diferencia decoys pelo
bucket real mesmo quando o target do access_resource e identico.
