# EXP-011 — Branch Profundo com Lookahead

## Identificacao
- ID: EXP-011
- Fase: 3
- Status: confirmado apos correcao do simulador

## Contexto
Os experimentos `EXP-008`, `EXP-009` e `EXP-010` melhoraram a priorizacao entre pivots concorrentes.
O benchmark anterior ainda tinha um limite: o branch correto liberava `access_resource` cedo demais.
Faltava validar se o `lookahead-aware path scoring` continuava funcionando quando o branch correto exigia multiplos passos de descoberta antes do acesso final.

## Hipotese
H1: o `lookahead-aware path scoring` generaliza para um branch correto que exige duas enumeracoes antes do acesso final.

H2: se o benchmark profundo falhar, a falha pode vir do simulador de fixture e nao necessariamente do planner.

## Desenho experimental

### Ambiente
Path sintetico AWS com tres roles concorrentes:
- `RoleA`: dead-end curto
- `RoleM`: dead-end curto
- `RoleQ`: branch correto profundo

Objetivo final:
- `arn:aws:s3:::sensitive-finance-data/finance/payroll.csv`

### Branches
- `RoleA`
  - `assume_role`
  - `s3_list_bucket` com artefato irrelevante
- `RoleM`
  - `assume_role`
  - `s3_list_bucket` com artefato irrelevante
- `RoleQ`
  - `assume_role`
  - `s3_list_bucket` com prefixo `finance/`
  - `s3_list_bucket` com prefixo `finance/payroll`
  - `s3_read_sensitive` em `finance/payroll.csv`

### Criterio de sucesso
- escolher `RoleQ`
- executar as duas etapas de descoberta do branch profundo
- acessar `finance/payroll.csv`
- registrar sucesso no report

## Falha inicial
O primeiro run do branch profundo falhou, mas a causa isolada nao foi o planner.

### Sintoma
No branch de `RoleQ`, o agente repetia `enumerate` no mesmo alvo e nao progredia para o estagio seguinte.

### Causa
`Fixture.execute()` distinguia transicoes apenas por:
- `action_type`
- `actor`
- `target`

No branch profundo, duas transicoes `enumerate` tinham:
- mesmo `action_type`
- mesmo `actor`
- mesmo `target`

A diferenca estava apenas em `parameters.prefix`, mas isso nao era considerado no matching.

### Interpretacao
Antes dessa correcao, o `EXP-011` nao podia ser interpretado como falha do `lookahead`.
Era uma limitacao do simulador para representar branches profundos com acoes estruturalmente semelhantes.

## Intervencao
Correcao aplicada em `src/core/fixture.py`:
- `Fixture.execute()` passou a considerar `parameters` quando a transicao os define
- foi adicionada a funcao `_parameters_match(expected, actual)`

Ajustes no fixture `fixtures/aws_deeper_branching_lab.json`:
- transicoes de `RoleQ` passaram a declarar `parameters` explicitos por estagio
- isso diferenciou `finance/` de `finance/payroll`

## Resultado final
Apos a correcao do simulador, o `OpenAIPlanner` convergiu com sucesso.

Caminho observado:
1. `iam_list_roles`
2. `assume_role -> RoleQ`
3. `s3_list_bucket` com prefixo `finance/`
4. `s3_list_bucket` com prefixo `finance/payroll`
5. `s3_read_sensitive -> finance/payroll.csv`

Resultado:
- `objective_met: True`
- `5` passos

## Descoberta principal
O `lookahead-aware path scoring` generaliza para um branch correto mais profundo, desde que o simulador represente corretamente transicoes multiestagio.

O experimento tambem revelou uma limitacao importante do engine de fixture:
- benchmarks mais profundos exigem matching de transicao sensivel a `parameters`
- matching apenas por `action_type`, `actor` e `target` nao basta

## O que foi provado
- o planner consegue priorizar o branch correto mesmo quando o acesso final exige duas etapas de descoberta
- o `lookahead` continua util fora do caso curto do `EXP-010`
- o simulador agora suporta branches profundos com enumeracoes sucessivas no mesmo alvo

## O que nao foi provado
- nao houve backtracking neste run especifico
- o experimento mediu profundidade de branch, nao recuperacao apos escolha errada

## Implicacoes arquiteturais
- `path scoring` com `lookahead` nao esta limitado a caminhos de um unico salto antes do objetivo
- o engine de fixture precisa evoluir junto com a dificuldade dos benchmarks
- profundidade de branch passa a ser um eixo experimental separado de order sensitivity

## Arquivos relevantes
- `src/core/fixture.py`
- `fixtures/aws_deeper_branching_lab.json`
- `examples/objective_aws_deeper_branching.json`
- `examples/scope_aws_deeper_branching.json`
- `examples/scope_aws_deeper_branching_openai.json`
- `tests/test_mvp.py`

## Conclusao
H1 foi confirmada.

H2 tambem foi confirmada: a falha inicial veio do simulador, nao do planner.

O `EXP-011` fecha a validacao de que o `lookahead-aware path scoring` funciona nao apenas para escolher entre pivots concorrentes, mas tambem para navegar um branch correto com descoberta em mais de um estagio.
