# Serverless Business App — Variante A

## Objetivo

Primeira variante do arquétipo `serverless-business-app`.

Ela prepara a próxima etapa do Produto 01 em um ambiente com superfícies
serverless mais próximas de workloads reais:
- Lambda
- API Gateway
- Secrets Manager
- SSM Parameter Store
- S3 de export/artifacts

Nesta variante, o foco ainda é coerência do inventário e qualidade dos
sinais para discovery/selection. KMS fica para a Variante B.

## Características

- ruído baixo
- nomes claros e plausíveis
- secrets e parameters de produção convivendo com segredos internos/legados
- funções Lambda com papéis distintos por domínio de negócio
- API pública e privada

## Recursos principais

### IAM roles
- `PayrollHandlerRole`
- `BillingWorkerRole`
- `OrdersExportRole`
- `InternalAdminSyncRole`
- `ServerlessAuditRole`

### Lambda
- `payroll-handler`
- `billing-worker`
- `orders-export`
- `internal-admin-sync`

### API Gateway
- `payroll-public` (pública)
- `internal-admin` (privada)

### Secrets
- `prod/payroll-api-key`
- `prod/billing-db-password`
- `internal/admin-token`
- `archive/orders-export-token`

### Parameters
- `/prod/payroll/api_key`
- `/prod/orders/export_token`
- `/shared/feature_flags/admin_sync`

### S3
- `serverless-payroll-exports-prod`
- `lambda-artifacts-prod`

## Papel arquitetural

Esta variante existe para validar que o pipeline discovery-driven não está
preso a ambientes IAM-first do tipo `internal-data-platform`.

Ela abre o caminho para:
- classes `advanced`
- superfícies serverless
- target selection mais rico em contextos com Lambda e API Gateway
