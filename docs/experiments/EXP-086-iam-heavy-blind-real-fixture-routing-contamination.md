# EXP-086 - IAM-Heavy Blind Real Fixture Routing Contamination

- ID: EXP-086
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-04
- Status: concluida

## Contexto

Depois do `EXP-085`, foi iniciado o bloco de correcao
`IAM-Heavy Blind Real Coverage And Evidence Hygiene`.

As primeiras correcoes implementadas foram:
- isolamento de output por plano
- deduplicacao de findings
- classificacao minima de evidencia
- binding explicito da `entry role` no report/findings
- discovery IAM estrutural inicial:
  - trust principals
  - policy attachments
  - inline policy names
- ranking IAM com primeiros sinais de privilege escalation

Em seguida, o mesmo ambiente AWS real IAM-privesc-heavy foi rerodado com maior
cobertura:
- `max_candidates_per_profile = 20`
- `max_plans_per_profile = 10`

## Hipoteses

- H1: as correcoes de findings e o ranking IAM inicial melhorariam a qualidade do
  reteste, mas ainda poderiam existir bloqueios anteriores ao action space.
- H2: o produto ainda pode estar misturando `blind real` com fixture routing
  sintetico em parte do pipeline discovery-driven.
- H3: se isso estiver ocorrendo, o reteste nao medira corretamente o gap de
  coverage IAM; medira apenas contaminacao do harness.

## Desenho experimental

- Variavel independente:
  - mesmo ambiente AWS real IAM-privesc-heavy
  - mesmo `bundle = aws-foundation`
  - maior largura de selection/synthesis
- Ambiente:
  - conta AWS real autorizada
  - entry role:
    - `arn:aws:iam::550192603632:role/privesc-AssumeRole-starting-role`
- Criterio:
  - observar se o assessment:
    - continua discovery-driven ate a execucao real
    - ou volta a colapsar para fixture sintetico por archetype/family

## Resultados observados

### Qualidade do plano

O `campaign_plan.json` gerou:
- `19` plans
- `9` de `aws-iam-s3`
- `10` de `aws-iam-role-chaining`

Os candidatos de `role-chaining` melhoraram qualitativamente:
- apareceram roles `privesc-*` relevantes, por exemplo:
  - `privesc-CodeBuildCreateProjectPassRole-role`
  - `privesc-CloudFormationUpdateStack-role`
  - `privesc10-PutUserPolicy-role`
  - `privesc12-PutRolePolicy-role`
  - `privesc13-AddUserToGroup-role`

Isso confirma que:
- a primeira camada de ranking IAM estrutural ajudou
- o selection deixou de ficar preso apenas a roles genericas de baixo valor

### Resultado do assessment

O reteste amplo terminou com:
- `campaigns_total = 19`
- `campaigns_passed = 0`
- `campaigns_objective_not_met = 19`

Isso foi pior do que o reteste anterior em taxa de sucesso, mas mais honesto
para diagnostico.

### Evidencia de contaminacao do harness

Ao inspecionar os campaigns de `aws-iam-role-chaining`, apareceu um problema
arquitetural claro:

- os planos IAM-heavy estavam embutindo:
  - `fixture_path = fixtures/serverless_business_app_unified_lab.json`
- os reports dessas campaigns mostraram:
  - `execution_mode = dry_run`
  - `real_api_called = False`
- os steps executados eram do fixture serverless sintetico, por exemplo:
  - `Listed unified serverless roles.`
  - `Assumed BillingWorkerRole.`
  - `Assumed PayrollHandlerRole.`

Ou seja:
- discovery e selection foram reais
- mas a execucao de parte relevante do assessment voltou a um fixture sintetico
  completamente desalinhado com o ambiente AWS real analisado

## Erros, intervenções e classificação das causas

### Causa 1 - higiene de findings

Classificacao:
- corrigida parcialmente

O que melhorou:
- output por plano
- deduplicacao de findings
- `role-chaining` sem prova minima deixou de ser `validated`
- `entry point` deixou de apontar para o usuario admin

### Causa 2 - ranking IAM

Classificacao:
- corrigida parcialmente

O que melhorou:
- os alvos IAM selecionados ficaram mais alinhados ao lab privesc

O que ainda nao prova:
- que o engine consegue explorar essas classes

### Causa 3 - routing de fixture sintetico em `blind real`

Classificacao:
- causa raiz nova
- bloqueio arquitetural forte

Descricao:
- `target_selection` continua inferindo `execution_fixture_set`
- `campaign_synthesis` continua embutindo `fixture_path`
- `run_generated_campaign()` ainda aceita esse contrato
- no IAM-heavy blind real, isso fez plans reais herdarem
  `serverless_business_app_unified_lab.json`

Consequencia:
- o reteste nao mediu coverage IAM real
- mediu contaminacao do harness na fase de execucao

## Descoberta principal

O primeiro bloco de correcao melhorou a higiene epistemica do assessment e o
ranking inicial de alvos IAM.

Mas o rerun revelou um bloqueio mais fundamental:

o `Blind Real Assessment` ainda nao esta suficientemente blind quando o
selection/synthesis embutem `fixture_path` derivado de archetype sintetico.

Em outras palavras:
- o problema atual nao e apenas `falta de mais coverage IAM`
- antes disso, ainda existe acoplamento residual entre:
  - selection/synthesis
  - fixture routing sintetico
  - execucao supostamente real

## Interpretação

Esse resultado e valioso porque separa dois problemas diferentes:

1. **problema de coverage IAM-heavy**
- classes reais de privilege escalation ainda faltam

2. **problema de pureza do modo blind real**
- o pipeline ainda pode recair em fixture sintetico fora do ambiente avaliado

Sem corrigir o segundo, o primeiro fica mal medido.

## Implicações arquiteturais

Antes de abrir novas classes IAM privesc no runtime real, o produto precisa
fechar um sub-bloco anterior:

- impedir que `Blind Real Assessment` discovery-driven use `fixture_path`
  sintetico quando o ambiente e real e o alvo nao e um fixture lab conhecido
- tornar o runtime blind real o caminho obrigatorio para campaigns geradas em
  AWS real, salvo override muito explicito de laboratorio

Tambem fica claro que:
- hygiene de findings e ranking IAM foram passos corretos
- mas ainda nao sao suficientes para um reteste honesto

## Ameaças à validade

- o reteste ainda usou `aws-foundation`, portanto continua havendo limite real
  de portfolio
- parte dos failures tambem pode vir de action space IAM insuficiente
- porem, a contaminacao por fixture sintetico e forte o suficiente para
  invalidar qualquer leitura mais ambiciosa de coverage nesta rodada

## Conclusão

O rerun IAM-heavy nao deve ser interpretado como:
- `o ranking novo falhou`

Ele deve ser interpretado como:
- `o primeiro corte de hygiene + ranking funcionou parcialmente`
- `mas o blind real ainda nao esta isolado do harness sintetico`

O proximo passo de maior leverage nao e abrir mais profile ainda.
E fechar a pureza de execucao do modo blind real para campanhas IAM-heavy.

## Próximos experimentos

1. bloquear `fixture_path` sintetico em `Blind Real Assessment` quando o target
   for AWS real e a campanha for gerada por discovery
2. rerodar o mesmo ambiente IAM-heavy com o mesmo width de selection/synthesis
3. so depois disso abrir:
   - novas classes IAM privilege escalation
   - runtime real alem de `AssumeRole`
