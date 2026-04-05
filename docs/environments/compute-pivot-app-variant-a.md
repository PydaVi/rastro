# Compute Pivot App — Variante A

## Objetivo

Primeira variante do arquétipo `compute-pivot-app`.

Ela existe para abrir a próxima frente de generalização ofensiva do Produto 01:
- pivô via EC2
- instance profile como superfície intermediária
- aproximação do eixo `IAM -> Compute -> IAM`

Nesta variante, o foco ainda é coerência do inventário e qualidade dos
sinais de discovery/selection. External entry explícito fica para as próximas
variantes.

## Características

- ruído baixo
- uma superfície compute principal (`payroll-app-prod-01`)
- um broker natural via instance profile
- secrets, parameters e dumps de payroll convivendo com logs e state buckets
- load balancer público presente, mas ainda sem exploração de entrypoint

## Recursos principais

### IAM roles
- `PayrollAppInstanceRole`
- `LegacyReportInstanceRole`
- `SupportBastionRole`
- `ComputeAuditRole`

### Instance profiles
- `PayrollAppProfile`
- `LegacyReportProfile`
- `SupportBastionProfile`

### EC2
- `payroll-app-prod-01`
- `legacy-reporting-01`
- `support-bastion-01`

### Network
- `payroll-web` (público)
- `reporting-internal` (privado)

### Secrets
- `prod/payroll/backend-db-password`
- `prod/reporting/export-token`
- `shared/support-session-token`

### Parameters
- `/prod/payroll/api_key`
- `/prod/reporting/export_token`
- `/shared/bastion/session_policy`

### S3
- `compute-payroll-dumps-prod`
- `compute-app-logs-prod`
- `terraform-state-shared`

## Papel arquitetural

Esta variante existe para provar que o pipeline discovery-driven começa a
generalizar além de ambientes IAM-first e serverless.

Ela prepara o terreno para:
- `aws-iam-compute-iam`
- `external entry`
- chains multi-step com compute como pivô intermediário
