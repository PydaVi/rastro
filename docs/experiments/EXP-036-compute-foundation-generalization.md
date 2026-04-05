# EXP-036 — Compute Pivot Foundation Generalization

## Identificação
- ID: EXP-036
- Fase: 3
- Status: confirmada

## Contexto
Depois de validar o `foundation` em `internal-data-platform` e `serverless-business-app`, o próximo passo era provar que o pipeline discovery-driven também generaliza para um arquétipo com superfícies de compute.

O objetivo desta etapa não foi abrir `IAM -> Compute -> IAM` ainda. Foi validar que o `foundation` continua funcionando quando o inventário passa a conter:
- EC2
- instance profiles
- load balancers
- ruído de logs, bastion e state buckets

## Hipóteses
- H1: o discovery-driven `foundation` continua funcional em um arquétipo com compute como superfície predominante.
- H2: a presença de EC2, instance profiles e load balancers não degrada a seleção dos alvos foundation.
- H3: este arquétipo pode servir de base para a próxima abertura da classe `IAM -> Compute -> IAM`.

## Resultados por etapa

### Etapa 1 — Coerência do inventário
- snapshot criado em `fixtures/compute_pivot_app_variant_a.discovery.json`
- recursos principais presentes:
  - `compute.instance_profile`
  - `compute.ec2_instance`
  - `network.load_balancer`
- interpretação:
  - o arquétipo já representa um ambiente de compute plausível, sem ainda depender de external entry

### Etapa 2 — Target selection foundation
- melhores alvos observados:
  - S3: `arn:aws:s3:::compute-payroll-dumps-prod/payroll/2026-03/payroll.csv`
  - Secrets: `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll/backend-db-password`
  - SSM: `arn:aws:ssm:us-east-1:123456789012:parameter/prod/payroll/api_key`
- interpretação:
  - o ranking foundation permaneceu estável mesmo com superfícies compute no inventário

### Etapa 3 — Assessment discovery-driven foundation
- output gerado em `outputs_compute_pivot_app_variant_a_assessment/assessment.json`
- resultado:
  - `campaigns_total = 4`
  - `campaigns_passed = 4`
  - `assessment_ok = true`
- interpretação:
  - o `foundation` generaliza para um arquétipo compute-heavy sem mudanças no loop central

## Descoberta principal
O pipeline discovery-driven do `foundation` já generaliza para inventários com compute sem ficar preso a ambientes IAM-first ou serverless. Isso reduz risco de drift do Produto 01 para campaigns excessivamente pré-estruturadas e prepara a abertura correta da classe `IAM -> Compute -> IAM`.

## Conclusão
- H1: confirmada
- H2: confirmada
- H3: confirmada
