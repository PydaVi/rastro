# EXP-047 — Mixed Generalization Same-Surface Competition

## Identificacao

- ID: EXP-047
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

Depois de `EXP-046`, o benchmark misto ainda precisava de uma pressao extra:
mais de um alvo forte na mesma superficie.

Sem isso, o sistema ainda podia parecer robusto apenas porque cada superficie
tinha um alvo claramente dominante.

## Hipoteses

H1. Com mais de um alvo plausivel por mesma superficie, o Rastro manteria o alvo
mais relevante no topo.

H2. O selection ainda tinha uma fragilidade residual:
- `api-key` com hifen nao era tratado tao bem quanto `api_key`
- `external-entry` precisava evitar capturar alvos cross-account, que sao mais
  expressivos sob `multi-step` ou `cross-account`

## Desenho experimental

### Variavel independente

Novo benchmark:
- `fixtures/mixed_generalization_variant_c.discovery.json`

Competicao adicionada:
- S3:
  - `payroll.csv`
  - `payroll-summary.csv`
- Secrets locais:
  - `prod/payroll-api-key`
  - `prod/payroll-webhook-password`
  - `prod/payroll-admin-bridge-token`
- SSM:
  - `/prod/payroll/api_key`
  - `/prod/payroll/runtime_token`
- Secrets cross-account:
  - `prod/finance/warehouse-api-key`
  - `prod/finance/warehouse-session-token`

## Resultados por etapa

### Etapa 1 — Falha inicial

Parcial.

O benchmark revelou dois problemas:

1. `aws-iam-secrets` subiu `prod/payroll-webhook-password` acima de
   `prod/payroll-api-key`
2. `aws-external-entry-data` ainda aceitava alvo cross-account como se fosse
   classe primaria de external entry

### Etapa 2 — Correcao geral

Correcao aplicada em `target selection`:

- normalizacao lexical:
  - `-` e `/` passam a ser tratados tambem como `_`
  - isso corrige `api-key` vs `api_key`
- `aws-external-entry-data` agora rejeita recurso fora da conta primaria
  quando ha classificacao mais expressiva disponivel (`cross-account` /
  `multi-step`)

### Etapa 3 — Selection rerun

Confirmada.

Melhores alvos observados:

- `aws-iam-s3`
  - `arn:aws:s3:::mixed-payroll-data-prod/payroll/2026-03/payroll.csv`
- `aws-iam-secrets`
  - `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key`
- `aws-iam-ssm`
  - `arn:aws:ssm:us-east-1:123456789012:parameter/prod/payroll/api_key`
- `aws-external-entry-data`
  - `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key`
- `aws-multi-step-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key`

### Etapa 4 — Assessment discovery-driven

Confirmada.

Resultado observado em:

- `outputs_mixed_generalization_variant_c_assessment/assessment.json`

Resumo:

- `campaigns_total = 8`
- `campaigns_passed = 8`
- `assessment_ok = true`

## Erros, intervencoes e motivos

### Causa raiz

- falha de policy/scoring: sim
- falha de representacao de estado: nao
- falha de infraestrutura: nao
- falha do planner: nao

O experimento revelou que o scorer ainda tratava delimitadores lexicais de forma
inconsistente e permitia bleed entre external-entry e cross-account.

## Descoberta principal

Quando a competicao acontece dentro da mesma superficie, o Rastro precisa:

- normalizar melhor o sinal lexical
- separar melhor classes concorrentes por estrutura

## Interpretacao

Esse bloco foi relevante porque mediu uma forma mais realista de escolha:

- nao apenas qual classe vence
- mas qual alvo vence dentro da mesma classe e da mesma superficie

## Implicacoes arquiteturais

- score lexical precisa continuar sendo tratado como apoio, nao como lider
- classes expressivas precisam bloquear captura indevida de targets que
  pertencem melhor a outra classe
- mixed benchmarks agora devem incluir competicao intra-superficie por padrao

## Ameacas a validade

- ainda e benchmark sintetico
- a separacao entre classes continua hand-written

## Conclusao

H1 e H2 confirmadas.

O bloco aumentou a generalizacao ofensiva porque:

- elevou a dificuldade de decisao dentro da mesma superficie
- reduziu ambiguidade entre classes concorrentes
- manteve o assessment discovery-driven estavel ponta a ponta

## Proximos passos

1. introduzir mixed benchmark com multiplos entry surfaces publicos concorrentes
2. reduzir ainda mais o papel do resolver sintetico curado
3. transferir as heuristicas boas do mixed benchmark para discovery real
