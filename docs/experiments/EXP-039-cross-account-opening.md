# EXP-039 — Abertura de Cross-Account Pivot -> Data

## Identificação
- ID: EXP-039
- Fase: 3
- Status: confirmada

## Contexto
Depois de abrir compute pivot e external entry no `compute-pivot-app`, o próximo passo era provar um primeiro caminho discovery-driven com boundary de conta.

## Hipóteses
- H1: o target selection consegue reconhecer alvo cross-account sem depender só de nome.
- H2: o pipeline discovery-driven consegue executar um salto de conta no mesmo loop central.

## Resultados por etapa

### Etapa 1 — Seleção cross-account
- melhor candidato de `aws-cross-account-data`:
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key`
- sinais estruturais observados:
  - `cross_account_target`
  - `cross_account_reachability`
  - `cross_account_roles`

### Etapa 2 — Assessment enterprise
- output:
  - `outputs_compute_pivot_app_enterprise_variant_c_assessment/assessment.json`
- resultado:
  - campanha `aws-cross-account-data` passou
  - bundle enterprise do arquétipo fechou com `campaigns_passed = 7/7`

## Implementação introduzida
- novo profile `aws-cross-account-data`
- scoring com:
  - boundary de conta
  - roles alcançáveis em conta diferente
  - distinção entre chain cross-account direta e chain profunda

## Descoberta principal
O engine já consegue representar e validar um salto cross-account discovery-driven sem criar um loop especial para esse caso. O ganho real veio da combinação entre selection estrutural e fixtures menos IAM-first.

## Conclusão
- H1: confirmada
- H2: confirmada
