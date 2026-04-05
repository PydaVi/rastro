# EXP-033 — Generalização do Foundation para Serverless Business App

## Identificação
- ID: EXP-033
- Fase: 3
- Status: confirmada

## Contexto
Depois de validar o `aws-foundation` em AWS real e no arquétipo `internal-data-platform`, ainda faltava provar se o pipeline discovery-driven do Produto 01 generaliza para um inventário com superfícies serverless. O objetivo aqui não foi validar classes `advanced`, mas verificar se o foundation continua operacional quando Lambda e API Gateway passam a coexistir com Secrets, SSM, S3 e IAM.

## Hipóteses
- H1: o `aws-foundation` continua executável em um ambiente com inventário serverless plausível.
- H2: discovery, target selection, campaign synthesis e assessment run não estão acoplados ao arquétipo `internal-data-platform`.
- H3: a presença de Lambda/API Gateway não degrada a seleção dos alvos foundation mais relevantes.

## Desenho experimental

### Variável independente
- snapshot `serverless_business_app_variant_a.discovery.json`

### Ambiente
- superfícies:
  - IAM
  - Lambda
  - API Gateway
  - Secrets Manager
  - SSM
  - S3
- execução:
  - assessment discovery-driven do bundle `aws-foundation`
  - profiles sintéticos do arquétipo `serverless-business-app`

### Critério de sucesso
- `campaigns_total = 4`
- `campaigns_passed = 4`
- zero `objective_not_met`
- zero `preflight_failed`
- zero `run_failed`

## Resultados

### Etapa 1 — Coerência do inventário
- Resultado: confirmada
- O snapshot inclui:
  - 5 roles
  - 4 funções Lambda
  - 2 APIs
  - 4 secrets
  - 3 parameters
  - 2 buckets
- O target selection foundation priorizou:
  - `prod/payroll-api-key` para Secrets
  - `/prod/payroll/api_key` para SSM

### Etapa 2 — Assessment discovery-driven
- Resultado: confirmada
- Saída:
  - `campaigns_total = 4`
  - `campaigns_passed = 4`
  - `assessment_ok = true`
- Artefatos gerados:
  - `outputs_serverless_business_app_variant_a_assessment/assessment.json`
  - `outputs_serverless_business_app_variant_a_assessment/assessment_findings.md`

## Descoberta principal
O pipeline discovery-driven do Produto 01 não está mais restrito ao arquétipo `internal-data-platform`. O `foundation` já generaliza para um ambiente com superfícies serverless sem perder coerência na seleção de alvos foundation.

## Interpretação
- O experimento não prova ainda classes `advanced`.
- Ele prova algo mais importante para o momento: o Produto 01 já mantém comportamento estável quando o inventário muda de perfil operacional.
- Isso reduz o risco de o discovery-driven ter sido calibrado apenas para ambientes “corporate data”.

## Implicações arquiteturais
- `target selection` foundation tolera recursos extras fora do escopo imediato (Lambda/API Gateway) sem perder o alvo principal.
- a camada discovery-driven já suporta arquétipos heterogêneos sem precisar de refactor estrutural.
- o próximo passo pode avançar com segurança para as classes `advanced` do `serverless-business-app`.

## Ameaças à validade
- apenas a Variante A foi validada
- não houve KMS nesta etapa
- o experimento ainda não executa classes `6` e `7`

## Conclusão
- H1: confirmada
- H2: confirmada
- H3: confirmada

O `aws-foundation` generaliza para o arquétipo `serverless-business-app` Variante A. O próximo bloco correto é avançar para as classes `advanced` nesse mesmo ambiente.
