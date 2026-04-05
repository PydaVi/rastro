# Compute Pivot App — Variante B

## Objetivo

Segunda variante do arquétipo `compute-pivot-app`.

Ela abre explicitamente o eixo `external entry -> IAM -> data`, saindo do
pivô compute puramente interno da Variante A.

## Características

- ruído baixo a médio
- endpoint público realista (`payroll-webhook-public`)
- bridge público alternativo via load balancer
- dados sensíveis anotados com relações estruturais de reachability
- inventário ainda controlado, mas menos pré-modelado do que a Variante A

## Recursos principais

### Network
- `payroll-webhook-public` (API Gateway pública)
- `public-webhook-bridge` (load balancer público)
- `reporting-internal-v2` (privado)

### Compute
- `payroll-web-prod-02`
- `legacy-reporting-02`

### IAM
- `PayrollAppInstanceRole`
- `LegacyReportInstanceRole`
- `PublicWebhookBridgeRole`
- `ComputeAuditRole`

### Dados
- `prod/payroll/backend-db-password`
- `/prod/payroll/api_key`
- `compute-payroll-dumps-prod/payroll/2026-03/payroll.csv`

## Papel arquitetural

Esta variante existe para abrir a primeira classe de `external entry` do
Produto 01 e forçar o target selection a usar sinais estruturais:
- superfície pública
- instância atingível
- role alcançável
- dado final ligado a essa role

Resultado observado:
- `aws-external-entry-data` entrou no `aws-advanced`
- assessment discovery-driven do arquétipo passou com `campaigns_passed = 6/6`
