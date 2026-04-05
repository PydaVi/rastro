# EXP-051 — Mixed Generalization Relationship Derived Structure

## Identificacao

- ID: EXP-051
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

Depois de `EXP-050`, o benchmark misto ainda dependia de metadata estrutural
curada diretamente nos recursos sensiveis:

- `reachable_roles`
- `pivot_chain`
- `chain_depth`

Isso era util para abrir rapidamente as classes enterprise, mas mantinha uma
curadoria residual forte demais no snapshot de discovery. O proximo passo
correto era mover essa informacao para uma forma mais proxima de inventario:

- relacoes explicitas entre principals e recursos
- relacoes explicitas de `assume_role`

## Hipoteses

H1. O `target selection` poderia inferir `reachable_roles`, `pivot_chain` e
`chain_depth` a partir de `relationships` sem perder estabilidade no benchmark
enterprise.

H2. O benchmark misto continuaria separando corretamente:

- `aws-external-entry-data`
- `aws-cross-account-data`
- `aws-multi-step-data`

mesmo com menos metadata curada por recurso.

H3. Esse bloco reduziria uma dependencia relevante de benchmark sem exigir
mudanca no loop principal nem no planner.

## Desenho experimental

### Variavel independente

Foi criada:

- `fixtures/mixed_generalization_variant_f.discovery.json`

Diferencas para a Variante E:

- remocao de:
  - `reachable_roles`
  - `pivot_chain`
  - `chain_depth`
  dos recursos sensiveis
- introducao de `relationships` explicitas:
  - `role -> resource` com `type=can_access`
  - `role -> role` com `type=can_assume`

### Mudancas de implementacao

Em `src/operations/target_selection.py`:

- `structural_index` passa a indexar:
  - `resource_to_roles`
  - `role_to_assumable_roles`
  - `public_root_roles`
- o selection agora resolve:
  - `reachable_roles`
  - `pivot_chain`
  - `chain_depth`
  por inferencia estrutural quando o metadata nao traz esses campos
- a inferencia de profile e de `execution_fixture_set` passa a usar esses
  valores resolvidos, nao apenas o metadata cru

## Resultados por etapa

### Etapa 1 — Selecao estrutural sem metadata curada

Confirmada.

Selecao observada:

- `aws-external-entry-data`
  - `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key`
- `aws-cross-account-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key`
- `aws-multi-step-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-master-api-key`

Sinais derivados corretamente:

- `aws-cross-account-data`
  - `pivot_chain = [PayrollAppInstanceRole, AnalyticsBrokerRole, FinanceWarehouseDeepRole]`
- `aws-multi-step-data`
  - `chain_depth = 4`
  - `reachable_roles = [FinanceWarehouseRelayRole]`

### Etapa 2 — Assessment discovery-driven ponta a ponta

Confirmada.

Output gerado:

- `outputs_mixed_generalization_variant_f_assessment/`

Resumo observado:

- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

### Causa raiz

Nao houve falha experimental do engine.

O bloco atacou uma limitacao de benchmark:

- metadata estrutural demais embutida no recurso

### Intervencoes

- derivacao estrutural por `relationships`
- busca do menor path entre roles publicamente alcancaveis e roles que levam ao
  recurso
- fallback para metadata apenas quando a relacao nao existir

## Descoberta principal

O benchmark misto enterprise continua estavel mesmo quando a estrutura ofensiva
relevante deixa de vir pre-anotada no recurso e passa a ser derivada de
relacoes do inventario.

## Interpretacao

Esse e um passo importante na direcao correta do produto:

- menos snapshot “explicando a resposta”
- mais selection inferindo contexto ofensivo a partir do inventario

Ainda nao e discovery completamente autonomo, mas reduz um dos atalhos mais
fortes do benchmark sintetico.

## Implicacoes arquiteturais

- `relationships` passam a ter valor real no pipeline, nao so existencia de
  schema
- `target selection` fica mais proximo de uma inferencia ofensiva baseada em
  grafo
- o benchmark misto agora pressiona melhor regressao para `profile-first` e
  para excesso de metadata curada

## Ameacas a validade

- ainda existe metadata lexical e semantica curada
- o grafo de relacoes continua sendo sintetico
- `cross-account` real continua bloqueado por pre-requisito operacional

## Conclusao

H1, H2 e H3 confirmadas.

O benchmark misto enterprise passou a derivar mais estrutura a partir de
`relationships` sem perder estabilidade ponta a ponta.

## Proximos passos

1. reduzir o uso de `semantic_tags` curado nos benchmarks mistos
2. continuar deslocando sinais ofensivos de metadata manual para relacoes e
   evidencia de inventario
3. usar esse benchmark como pressao recorrente contra regressao estrutural no
   selection
