# EXP-096 — Role-Chaining Planner Progress Gating

- ID: EXP-096
- Fase: Blind real IAM-heavy
- Data: 2026-04-05
- Status: concluido

## Contexto

O focused run `aws-iam-role-chaining-only` mostrou que o produto nao estava falhando no executor AWS. O gargalo estava no loop de decisao: depois de uma enumeracao util, as campaigns caiam em `analyze` repetido e nunca chegavam a `assume_role`.

Isso mantinha `aws-iam-role-chaining` vivo no plano, mas morto no runtime.

## Hipoteses

1. O `action shaping` ainda estava tratando o ramo ativo como progresso local sem considerar `ASSUME_ROLE` como acao de progresso para `assume_role_proved`.
2. Mesmo quando havia `ASSUME_ROLE` disponivel, `ANALYZE` continuava competindo e consumindo o budget.
3. O problema era de policy do engine, nao de descoberta nem de executor real.

## Desenho experimental

Variavel independente:
- mudar o shaping para que, em `assume_role_proved`, o ramo ativo considere `ASSUME_ROLE` como acao de progresso e remova `ANALYZE` quando ja houver pivot disponivel.

Ambiente:
- suite offline focada em `action_shaping`
- rerun AWS real focado em `aws-iam-role-chaining-only`

Criterio:
- se houver `ASSUME_ROLE` coerente com o objetivo no ramo ativo, o shaping deve prioriza-lo em vez de `ANALYZE`.

## Resultados por etapa

### Etapa 1 — Diagnostico do loop

O estado anterior tratava o ramo ativo com `progress_types = {ENUMERATE, ACCESS_RESOURCE, ANALYZE}`.

Consequencia:
- `ASSUME_ROLE` nem entrava no conjunto preferencial do ramo ativo
- `ANALYZE` virava o default competitivo
- o planner caia em analise esteril mesmo com pivot disponivel

### Etapa 2 — Correcao aplicada

Mudancas:
- `ASSUME_ROLE` passa a ser acao de progresso no ramo ativo para `assume_role_proved`
- quando houver `ASSUME_ROLE` disponivel nesse modo, `ANALYZE` deixa de competir no mesmo corte

### Etapa 3 — Validacao offline

Testes focados passaram cobrindo:
- preferencia por `ASSUME_ROLE` em vez de `ANALYZE`
- preservacao do comportamento de `access_proved`
- ausencia de restauracao de acesso direto para `assume_role_proved`

## Erros, intervencoes e motivos

Nao houve erro de infraestrutura novo.

A descoberta principal foi arquitetural:
- o problema nao era o executor real
- o problema era o policy loop do engine para compromisso com pivot

## Descoberta principal

`aws-iam-role-chaining` estava fracassando porque o engine ainda tratava `ANALYZE` como progresso suficiente no ponto em que deveria se comprometer com `ASSUME_ROLE`.

## Interpretacao

Esse e um problema de framing/policy do engine.

Enquanto o loop aceitar analise esteril como progresso em classes de pivot, o produto continuara parecendo mais reflexivo do que realmente ofensivo.

## Implicacoes arquiteturais

1. `ASSUME_ROLE` precisa ser tratado como acao de progresso de primeira classe para campanhas de chain.
2. `ANALYZE` nao pode competir indefinidamente com pivots ja disponiveis.
3. O engine precisa de regras de compromisso com pivot por classe ofensiva, nao apenas filtros genericos.

## Ameacas a validade

- o rerun real focado ainda precisa confirmar ganho de coverage
- esta correcao elimina um gargalo claro, mas pode nao ser suficiente para tornar `role-chaining` util no lab

## Conclusao

A falha de `aws-iam-role-chaining` era parcialmente autoimposta pelo engine: o ramo ativo excluia `ASSUME_ROLE` do conjunto de progresso e deixava `ANALYZE` consumir o budget.

A correcao reduz esse erro de policy.

## Proximos experimentos

1. concluir o rerun focado `aws-iam-role-chaining-only`
2. medir se `assume_role` aparece de fato nos reports
3. se ainda colapsar, endurecer compromisso com pivot apos enumeracao suficiente
