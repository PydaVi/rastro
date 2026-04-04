# EXP-063 — Target-Based Generated Objectives Reveal Synthetic Coupling

## Identificacao

- ID: EXP-063
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

O bloco atual tenta reduzir acoplamento `profile-first` na synthesis.

A mudanca foi:

- parar de herdar `success_criteria.flag` do objetivo base do profile
- gerar objetivo derivado do candidato final

Isso era necessario para aproximar o produto de:

- `target selection -> objetivo derivado`

em vez de:

- `profile fixo -> objetivo canonico do harness`

## Hipoteses

H1. Objetivos gerados a partir do candidato final reduziriam dependência de
`profiles` fixos e revelariam acoplamentos remanescentes do harness sintético.

H2. Se o benchmark misto quebrasse, a causa mais provável estaria em:

- infraestrutura/harness sintético
- ou semântica incompleta de `target observed`

e não em regressão do scorer.

## Desenho experimental

### Intervencao

`campaign_synthesis` passou a gerar:

- `objective.target = candidate.resource_arn`
- `success_criteria.mode = target_observed`

sem herdar `flag` do profile base.

### Critério

Reexecutar:

- teste unitário da synthesis
- mixed benchmark `variant_p`

e observar se o assessment continua `9/9`.

## Resultados por etapa

### Etapa 1 — Teste unitario da synthesis

Falhou inicialmente.

Causa:

- o teste ainda usava `authorization` restrita ao `foundation`
- `aws-external-entry-data` foi bloqueado por policy de autorizacao do fixture

Classificacao:

- falha de infraestrutura de teste

### Etapa 2 — Mixed benchmark `variant_p`

Falhou inicialmente com `7/9`.

Campanhas afetadas:

- `aws-external-entry-data`
- `aws-iam-compute-iam`

Achado principal:

- o scorer continuou selecionando candidatos corretos
- a quebra apareceu depois, na prova do objetivo gerado

### Etapa 3 — Causa raiz isolada

Foram revelados dois acoplamentos reais:

1. `target_observed` ainda era estreito demais

- sucesso so ocorria quando `action.target == objective.target`
- isso nao cobria casos em que o objetivo correto aparece em:
  - `reached_role`
  - `granted_role`
  - evidência observada

2. alguns fixture sets sintéticos ainda assumiam targets canônicos

- `aws-external-entry-data` continuava emitindo apenas o alvo canônico do fixture
- `aws-iam-compute-iam` provava o pivô por `reached_role`, nao por `action.target`

Classificacao:

- falha de representação de estado / critério de sucesso
- falha residual de harness sintético

Nao foi:

- regressão de scoring
- regressão do planner

## Erros, intervencoes e motivos

Antes de corrigir o código, ficou explícito:

- o experimento foi valioso
- ele mostrou que ainda havia acoplamento entre:
  - objetivo gerado
  - semântica de sucesso
  - targets canônicos do harness

## Descoberta principal

Gerar objetivos a partir do candidato final foi a decisão certa.

O que quebrou foi o que ainda estava escondido:

- a semântica de `target observed` não era geral o suficiente
- o harness misto ainda dependia de alguns targets canônicos

## Interpretacao

Esse bloco empurra o produto para `mais generalização ofensiva`.

Ele força o sistema a provar o alvo realmente selecionado, não o alvo implícito
do profile.

## Implicacoes arquiteturais

- `target_observed` precisa aceitar prova por:
  - alvo acessado diretamente
  - identidade alcançada observada
  - evidência observada canonicalizada
- aliases do harness devem servir à generalização, não esconder alvo canônico

## Ameacas a validade

- a correção ainda não elimina todos os fixture sets sintéticos por família
- mixed benchmark continua dependendo de resolver sintético, embora menos

## Conclusao

H1 confirmada.

H2 confirmada.

O bloco revelou acoplamento residual entre objetivo gerado, critério de sucesso
e harness sintético. Corrigir isso é avanço estrutural do produto, não remendo
local de experimento.

## Proximos passos

1. ampliar `target_observed` para observar evidência canonicalizada
2. adicionar aliases mínimos nos fixture sets afetados
3. revalidar `variant_p` e voltar ao trilho de generalização ofensiva
