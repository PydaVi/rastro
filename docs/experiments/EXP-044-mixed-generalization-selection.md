# EXP-044 — Mixed Generalization Selection

## Identificacao

- ID: EXP-044
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

Depois de fechar `foundation`, `serverless-business-app` e `compute-pivot-app`,
o proximo risco de drift era o Rastro continuar forte apenas como validador de
campaigns conhecidas por profile. O gap nao era mais do executor; era de
selecao e sintese:

- peso lexical ainda alto demais
- profile-first demais na escolha de campanhas
- pouca competicao entre caminhos concorrentes de naturezas diferentes

## Hipoteses

H1. Um ambiente misto com recursos foundation, advanced e enterprise no mesmo
inventario vai expor dependencia residual de heuristica lexical.

H2. `target selection` precisa carregar mais semantica estrutural explicita do
que texto cru de ARN para continuar priorizando o alvo certo.

H3. `campaign synthesis` deve conseguir escolher o profile mais expressivo para
o mesmo recurso quando ha sobreposicao entre:

- `aws-iam-secrets`
- `aws-external-entry-data`
- `aws-cross-account-data`
- `aws-multi-step-data`

## Desenho experimental

### Variavel independente

- introducao de um snapshot misto:
  - `fixtures/mixed_generalization_variant_a.discovery.json`
- aumento do peso estrutural:
  - `candidate_profiles`
  - `semantic_tags`
  - `chain_depth`
  - `score_components.lexical/structural`
- deduplicacao opcional em `campaign synthesis` por `resource_arn`

### Ambiente

Inventario misto com:

- compute publico
- Lambda
- KMS
- secret foundation
- secret external-entry
- secret cross-account / multi-step
- roles de runtime, broker, auditoria e cross-account

### Criterio

- o melhor alvo `aws-iam-secrets` deve continuar sendo o secret foundation
- o melhor alvo `aws-external-entry-data` deve subir por reachability
  estrutural, nao por nome mais chamativo
- o melhor alvo `aws-multi-step-data` deve superar o mesmo recurso sob
  `aws-cross-account-data` e `aws-iam-secrets`
- `campaign synthesis` com dedupe deve escolher o profile mais expressivo por
  recurso

## Resultados por etapa

### Etapa 1 — Selection

Confirmada.

Resultados observados:

- `aws-iam-secrets`
  - alvo topo: `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key`
- `aws-external-entry-data`
  - alvo topo: `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key`
- `aws-cross-account-data`
  - alvo topo: `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key`
- `aws-multi-step-data`
  - alvo topo: `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key`

Ponto importante:

- no candidato `aws-multi-step-data`, `score_components.structural` ficou
  maior que `score_components.lexical`

### Etapa 2 — Campaign synthesis dedupe

Confirmada.

Quando o mesmo recurso apareceu em multiplos profiles, o synthesis com
`dedupe_resource_targets=True` escolheu:

- `prod/payroll-api-key` -> `aws-external-entry-data`
- `prod/finance/warehouse-api-key` -> `aws-multi-step-data`

Isso reduziu profile-first rigido sem quebrar o fluxo atual do assessment.

## Erros, intervencoes e motivos

Nao houve falha experimental. O experimento foi desenhado para medir drift de
produto, nao para corrigir bug do executor.

Intervencoes aplicadas:

- `target selection` passou a aceitar `candidate_profiles`
- `target selection` passou a expor `score_components`
- `campaign synthesis` ganhou dedupe opcional por recurso

## Descoberta principal

O proximo passo de generalizacao ofensiva nao depende apenas de abrir novas
classes. Depende de fazer o sistema escolher melhor entre classes concorrentes
para o mesmo alvo.

## Interpretacao

Esse experimento mostrou um movimento importante:

- antes: `target -> profile` era quase fixo
- agora: o mesmo `target` pode ser reinterpretado pelo profile mais expressivo
  dado o contexto estrutural

Isso nao elimina bundles e profiles, mas reduz a dependencia deles como verdade
anterior ao raciocinio.

## Implicacoes arquiteturais

- `target selection` precisa continuar caminhando para score semantico
- `campaign synthesis` deve ganhar mais capacidade de escolher profile por
  expressividade estrutural, nao apenas por classe fixa
- mixed environments passam a ser benchmark obrigatorio para evitar regressao
  para heuristica lexical crua

## Ameacas a validade

- ainda e benchmark sintetico
- o dedupe opcional ainda nao substitui o fluxo padrao do assessment
- `candidate_profiles` ainda e metadata curada, nao inferencia completa

## Conclusao

Hipoteses H1, H2 e H3 confirmadas.

O bloco avancou o Rastro na direcao de:

- menos dependencia de profiles fixos
- menos dependencia de heuristica lexical simples
- mais generalizacao ofensiva sobre targets concorrentes

## Proximos experimentos

1. mixed environment end-to-end com synthesis menos profile-first no assessment
2. inferencia estrutural de profile sem `candidate_profiles` curado
3. competicao real entre compute/external entry e caminhos IAM-first para o
   mesmo recurso
