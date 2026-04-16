# EXP-097 — Role-Chaining Simulation Truthfulness

- ID: EXP-097
- Fase: Blind real IAM-heavy
- Data: 2026-04-09
- Status: concluido

## Contexto

O `rerun5` de `aws-iam-role-chaining-only` finalmente saiu do loop morto e passou a executar `iam_simulate_assume_role`.

Isso provou que o problema anterior de planner/control loop era real.

Mas o resultado tambem revelou um novo erro de verdade semantica:
- findings com `decision=implicitDeny` continuavam sendo promovidos para `reachable`
- `distinct_path_key` mantinha repeticoes esteriais da mesma acao simulada
- o output ainda descrevia oportunidade onde a simulacao nao provou permissao

## Hipoteses

1. `role-chaining` ainda herdava `reachable` de qualquer conjunto de `success_steps`, mesmo quando a simulacao negava o pivot.
2. a sintese de evidencia ainda tratava qualquer `simulated_policy_result` como oportunidade observada, sem diferenciar `allowed` de `implicitDeny`.
3. a chave de distinctness precisava colapsar repeticoes consecutivas do mesmo step para nao inflar diferencas cosmeticas.

## Desenho experimental

Variavel independente:
- endurecer classificacao de estado e evidencia para `role-chaining` e policy probes simulados.
- colapsar repeticoes consecutivas no `distinct_path_key`.

Ambiente:
- testes offline de findings
- reruns reais anteriores como referencia diagnostica

Criterio:
- `implicitDeny` nao pode virar `reachable`
- evidencia com simulacao negada nao pode ser descrita como oportunidade provada
- repeticoes consecutivas da mesma acao nao devem virar path distinto artificial

## Resultados por etapa

### Etapa 1 — Diagnostico

O `rerun5` produziu dois findings `aws-iam-role-chaining`:
- um com `decision=allowed`
- um com `decision=implicitDeny`

Ambos estavam em `finding_state = reachable`.

Isso estava errado.

### Etapa 2 — Correcao

Regras endurecidas:
- `role-chaining` com simulacao `allowed` pode chegar a `reachable`
- `role-chaining` com simulacao `implicitDeny` permanece `observed`
- policy probes IAM com simulacao negada permanecem `observed`
- `distinct_path_key` passa a colapsar repeticoes consecutivas do mesmo token normalizado
- `evidence_summary` passa a diferenciar simulacao que provou oportunidade de simulacao que negou o path

## Descoberta principal

Depois de destravar o pivot, o proximo gargalo passou a ser verdade semantica da simulacao.

O produto ja nao estava morto no planner, mas ainda estava frouxo no significado de `reachable`.

## Interpretacao

Esse ajuste nao aumenta coverage.
Ele melhora honestidade epistemologica.

Sem isso, o produto continua sugerindo que o runtime sabe mais do que sabe.

## Implicacoes arquiteturais

1. simulacao `allowed` e simulacao `implicitDeny` precisam viver em estados diferentes.
2. `distinct path` nao pode carregar repeticao esterial como diferenca ofensiva.
3. o proximo passo continua sendo abrir mais prova real, nao inflar leitura de simulacao.

## Ameacas a validade

- mesmo com essa correcao, `role-chaining` continua sem impacto validado
- o lab ainda segue amplamente subcoberto

## Conclusao

O `rerun5` confirmou que o loop de decisao foi corrigido, mas expôs um novo problema: a classificacao ainda promovia simulacao negada para `reachable`.

A correcao necessaria e de verdade semantica, nao de coverage.

## Proximos experimentos

1. rerodar `aws-iam-role-chaining-only` com a classificacao endurecida
2. medir se o output cai para um finding `reachable` e um `observed`
3. so depois voltar ao bundle IAM-heavy completo
