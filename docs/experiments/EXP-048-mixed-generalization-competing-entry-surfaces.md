# EXP-048 — Mixed Generalization Competing Entry Surfaces

## Identificacao

- ID: EXP-048
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

Depois de competir alvos na mesma superficie (`EXP-047`), ainda faltava um
tipo de pressao importante: multiplos entry surfaces publicos concorrentes.

Sem isso, `external-entry` ainda podia parecer robusto apenas porque havia uma
unica superficie publica plausivel.

## Hipoteses

H1. Com duas superficies publicas concorrentes, o Rastro deveria preferir o
entry path ligado ao role mais valioso.

H2. O selection de `aws-external-entry-data` precisava considerar qualidade do
role publico alcançavel, nao apenas existencia de reachability publica.

## Desenho experimental

### Variavel independente

Novo benchmark:
- `fixtures/mixed_generalization_variant_d.discovery.json`

Competicao adicionada:
- API publica 1 -> `PayrollAppInstanceRole`
- API publica 2 -> `LegacyWebhookBridgeRole`

Alvos concorrentes:
- `prod/payroll-api-key`
- `prod/payroll-webhook-password`

## Resultados por etapa

### Etapa 1 — Correcao estrutural

Foi introduzido um novo sinal no selection:

- `public_role_quality_signal`

Derivado de:
- metadados do role alcançavel
- sinais de runtime/compute/prod
- penalidades para `legacy`, `audit`, `bridge`

### Etapa 2 — Selection

Confirmada.

Resultado observado:

- `aws-external-entry-data`
  - alvo topo: `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key`
- o alvo concorrente:
  - `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-webhook-password`
  - permaneceu abaixo

O benchmark registrou:

- `signals.public_role_score`

e o role score do caminho correto ficou acima do caminho legado.

### Etapa 3 — Assessment discovery-driven

Confirmada.

Resultado observado em:

- `outputs_mixed_generalization_variant_d_assessment/assessment.json`

Resumo:

- `campaigns_total = 8`
- `campaigns_passed = 8`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Nao houve falha experimental apos o desenho do benchmark.

Intervencao aplicada:

- `target selection` passou a considerar qualidade do role publico de entrada

## Descoberta principal

Escolher bem um path de `external-entry` nao depende apenas de:

- recurso sensivel
- reachability publica

Depende tambem de:

- qualidade estrutural do role alcançado pela superficie publica

## Interpretacao

Esse passo aproxima o Rastro de um raciocinio mais ofensivo, porque a decisao
passa a considerar:

- qual entrada publica e melhor

e nao apenas:

- qual alvo final parece melhor

## Implicacoes arquiteturais

- entry-surface scoring deve continuar crescendo
- mixed benchmarks devem incluir competicao entre entradas, nao apenas entre
  alvos
- sinais de qualidade de pivô tendem a ser tao importantes quanto sinais do
  recurso final

## Ameacas a validade

- ainda e benchmark sintetico
- qualidade do role publico ainda e definida por heuristica hand-written

## Conclusao

H1 e H2 confirmadas.

O bloco avancou a generalizacao ofensiva porque passou a selecionar melhor entre
paths de entrada concorrentes antes mesmo da fase de execucao.

## Proximos passos

1. combinar competicao entre entry surface e competicao entre targets no mesmo
   benchmark com mais profundidade
2. transferir sinais de qualidade de pivô para discovery real
3. preparar o proximo salto: menos curadoria do resolver sintetico misto
