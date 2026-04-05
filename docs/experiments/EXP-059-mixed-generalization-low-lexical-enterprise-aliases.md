# EXP-059 — Mixed Generalization Low Lexical Enterprise Aliases

## Identificacao

- ID: EXP-059
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Depois de `EXP-058`, o proximo passo de maior leverage era reduzir naming
favorecido restante nos deep targets enterprise.

Objetivo:

- diminuir ainda mais o apoio lexical dos alvos de `cross-account` e
  `multi-step`
- medir se a separacao entre essas classes continuaria estrutural mesmo com
  aliases finais pouco expressivos

## Hipoteses

H1. `aws-cross-account-data` deveria continuar escolhendo o alvo correto com
base estrutural, mesmo com alias final pouco expressivo.

H2. `aws-multi-step-data` deveria continuar separado de `cross-account` pela
profundidade e estrutura da chain, nao por naming final do secret.

## Desenho experimental

### Variavel independente

Foi criada:

- `fixtures/mixed_generalization_variant_n.discovery.json`

Renomeacoes principais:

- `prod/ops/core-a` -> `prod/x/t1`
- `prod/ops/core-b` -> `prod/x/t2`

### Intervencoes de suporte

Fixture sets enterprise expandidos para os aliases novos:

- `fixtures/mixed_generalization_cross_account_lab.json`
- `fixtures/mixed_generalization_multi_step_lab.json`

## Resultados por etapa

### Etapa 1 — Selection

Confirmada.

Selecao observada:

- `aws-cross-account-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/x/t1`
- `aws-multi-step-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/x/t2`

Nos dois casos:

- `score_components.structural > score_components.lexical`

### Etapa 2 — Assessment discovery-driven

Confirmada.

Resultado observado:

- `outputs_mixed_generalization_variant_n_assessment/`
- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Nao houve falha experimental nova neste bloco.

As mudancas foram feitas diretamente nos fixture sets enterprise que sustentam
o benchmark misto.

## Descoberta principal

Os deep targets enterprise continuam estaveis no benchmark mesmo quando o nome
final do secret perde quase todo o valor semantico residual.

## Interpretacao

Esse bloco reforca que a separacao entre:

- `cross-account`
- `multi-step`

ja depende mais de:

- profundidade da chain
- fronteira de conta
- reachability estrutural

do que do nome final do recurso.

## Implicacoes arquiteturais

- aliases pouco expressivos ja sao suportados tambem para alvos enterprise
- o mixed benchmark continua servindo como régua de inferencia estrutural, nao
  so como teste de robustez lexical

## Ameacas a validade

- continua sendo benchmark sintetico
- os fixture sets enterprise ainda precisam de cobertura explicita de aliases

## Conclusao

H1 confirmada.

H2 confirmada.

O bloco empurrou o produto para mais generalizacao ofensiva ao reduzir mais um
apoio lexical residual nos alvos enterprise profundos.

## Proximos passos

1. continuar removendo naming favorecido onde ainda houver leverage real
2. reduzir curadoria manual remanescente de aliases nos fixture sets mistos
3. manter o mixed benchmark como régua primária contra drift para
   `campaign validator`
