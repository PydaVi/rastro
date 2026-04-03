# Ambientes Sinteticos AWS — Arquitetura de Labs

## Objetivo

Criar ambientes sinteticos maiores, plausiveis e reutilizaveis para validar:
- discovery
- target selection
- campaign synthesis
- engine de run

Esses ambientes nao devem ser aleatorios.
Devem ser arquétipos realistas de conta AWS, com:
- ruido operacional
- nomes plausiveis
- recursos irrelevantes
- 1 ou mais paths validos
- decoys suficientes para testar selecao e execucao

## Principios

- ambientes versionados, nao gerados de forma opaca
- semantica plausivel de naming
- cada ambiente cobre multiplas classes do portfolio
- cada ambiente pode existir em variantes A/B/C para reduzir overfitting
- o mesmo ambiente deve servir para Produto 01 e, no futuro, para Produto 02

## Base de inspiracao

Os ambientes devem se inspirar em:
- cenarios ofensivos realistas como CloudGoat
- topologias operacionais comuns em AWS
- nomes e superficies de workloads reais:
  - dados internos
  - serverless business apps
  - compute-backed applications

Nao copiar laboratorios ofensivos literalmente.
O objetivo e capturar topologias, nao reproduzir desafios CTF.

## Ambiente 1 — Internal Data Platform

### Nome logico
`internal-data-platform`

### Objetivo do ambiente
Ser o lab base para `foundation`, discovery e target selection sob ruido realista.

### Superficies
- IAM / STS
- S3
- Secrets Manager
- SSM Parameter Store

### Recursos esperados
- bucket sensivel principal
- bucket de relatórios publicos/decoy
- bucket de state/backup com muito ruido
- secrets `prod/`, `finance/`, `archive/`, `reports/`
- parameters `prod/`, `finance/`, `shared/`
- roles:
  - `AuditRole`
  - `DataAccessRole`
  - `BrokerRole`
  - `DecoyBrokerRole`
  - `FinanceAuditRole`
  - `BucketReaderRole`

### Ruido esperado
- terraform state
- objetos de backup
- relatorios trimestrais
- nomes parecidos mas irrelevantes

### Classes cobertas
- 1. IAM -> S3
- 2. IAM -> Secrets
- 3. IAM -> SSM
- 4. IAM -> Role chaining

### Variantes
- A: ruido baixo
- B: ruido medio
- C: ruido alto + nomes ambíguos

### Status atual
- target selection validado nas variantes A/B/C
- assessment discovery-driven end-to-end validado nas variantes A/B/C
- descoberta arquitetural registrada em `docs/experiments/EXP-032-internal-data-platform-discovery-driven.md`

## Ambiente 2 — Serverless Business App

### Nome logico
`serverless-business-app`

### Objetivo do ambiente
Preparar `advanced` com superficies serverless e segredos distribuidos.

### Superficies
- IAM / STS
- Lambda
- API Gateway
- Secrets Manager
- SSM Parameter Store
- KMS
- S3

### Recursos esperados
- funcoes Lambda:
  - `billing-worker`
  - `payroll-handler`
  - `orders-export`
  - `internal-admin-sync`
- API publica e privada
- segredos:
  - `prod/payroll-api-key`
  - `prod/billing-db-password`
  - `internal/admin-token`
- parametros:
  - `/prod/payroll/api_key`
  - `/prod/orders/export_token`
- KMS keys para decriptacao de parte dos segredos
- buckets de export e ingest

### Ruido esperado
- lambdas com nomes parecidos
- segredos expirados
- parametros antigos
- buckets de logs e artefatos

### Classes cobertas
- 2. IAM -> Secrets
- 3. IAM -> SSM
- 6. IAM -> Lambda -> data
- 7. IAM -> KMS -> data
- 8. External entry -> IAM -> data (via API Gateway)

### Variantes
- A: sem KMS
- B: com KMS
- C: com API publica e ruído maior

### Status atual
- Variante A implementada em `fixtures/serverless_business_app_variant_a.discovery.json`
- inventario inicial documentado em `docs/environments/serverless-business-app-variant-a.md`
- foundation revalidado discovery-driven na Variante A
- descoberta registrada em `docs/experiments/EXP-033-serverless-foundation-generalization.md`
- Variante B implementada em `fixtures/serverless_business_app_variant_b.discovery.json`
- KMS introduzido no arquétipo para preparar classes `advanced`
- Variante C implementada em `fixtures/serverless_business_app_variant_c.discovery.json`
- foundation revalidado discovery-driven nas variantes B e C
- descoberta registrada em `docs/experiments/EXP-034-serverless-foundation-hardening.md`
- classes `advanced` abertas:
  - Variante A: `aws-iam-lambda-data`
  - Variante B: `aws-iam-kms-data`
  - Variante C: `aws-iam-lambda-data` + `aws-iam-kms-data` estaveis sob ruido maior
- descoberta registrada em `docs/experiments/EXP-035-serverless-advanced-opening.md`

## Ambiente 3 — Compute Pivot App

### Nome logico
`compute-pivot-app`

### Objetivo do ambiente
Validar pivôs via compute e preparar external entry / enterprise.

### Superficies
- IAM / STS
- EC2
- instance profiles
- S3
- Secrets Manager
- SSM
- ALB / app endpoint

### Recursos esperados
- instancias EC2 com instance profiles distintos
- role de aplicacao
- role de administracao interna
- secret de backend
- parameter de integracao
- bucket de aplicacao
- bucket de dumps/logs

### Ruido esperado
- instancias antigas
- perfis ociosos
- logs e dumps
- endpoints internos/externos com naming parecido

### Classes cobertas
- 5. IAM -> Compute -> IAM
- 8. External entry -> IAM -> data
- 10. Multi-step chain

### Variantes
- A: pivot via instance profile
- B: pivot via endpoint exposto
- C: pivot com 2 compute surfaces concorrentes

### Status atual
- Variante A implementada em `fixtures/compute_pivot_app_variant_a.discovery.json`
- inventario inicial documentado em `docs/environments/compute-pivot-app-variant-a.md`
- teste inicial de coerencia do inventario compute adicionado
- foundation target selection validado no arquétipo:
  - S3: `compute-payroll-dumps-prod/payroll/2026-03/payroll.csv`
  - Secrets: `prod/payroll/backend-db-password`
  - SSM: `/prod/payroll/api_key`
- foundation revalidado discovery-driven na Variante A
- descoberta registrada em `docs/experiments/EXP-036-compute-foundation-generalization.md`
- `aws-iam-compute-iam` aberto na Variante A
- descoberta registrada em `docs/experiments/EXP-037-compute-pivot-opening.md`
- Variante B implementada em `fixtures/compute_pivot_app_variant_b.discovery.json`
- `aws-external-entry-data` aberto na Variante B
- descoberta registrada em `docs/experiments/EXP-038-external-entry-opening.md`
- Variante C implementada em `fixtures/compute_pivot_app_variant_c.discovery.json`
- `aws-cross-account-data` e `aws-multi-step-data` abertos na Variante C
- discoveries registradas em:
  - `docs/experiments/EXP-039-cross-account-opening.md`
  - `docs/experiments/EXP-040-multi-step-chain-opening.md`

## Ambiente 4 — Mixed Generalization

### Nome logico
`mixed-generalization`

### Objetivo do ambiente

Medir se o Rastro continua preso a profile-first e heuristica lexical quando
foundation, advanced e enterprise coexistem no mesmo inventario.

### Superficies

- compute publico
- Lambda
- KMS
- S3
- Secrets Manager
- SSM
- cross-account

### Uso

- benchmark de `target selection`
- benchmark de `campaign synthesis`
- competicao entre multiplos profiles para o mesmo alvo

### Status atual

- Variante A implementada em `fixtures/mixed_generalization_variant_a.discovery.json`
- descoberta registrada em `docs/experiments/EXP-044-mixed-generalization-selection.md`
- usada para validar:
  - `score_components.lexical/structural`
  - dedupe opcional por `resource_arn`
  - escolha do profile mais expressivo para o mesmo target
- assessment discovery-driven ponta a ponta validado em:
  - `outputs_mixed_generalization_variant_a_assessment/`
- descoberta complementar registrada em:
  - `docs/experiments/EXP-045-mixed-generalization-end-to-end.md`
- Variante B implementada em `fixtures/mixed_generalization_variant_b.discovery.json`
- `candidate_profiles` curado removido do benchmark
- inferencia estrutural de profile validada em:
  - `outputs_mixed_generalization_variant_b_assessment/`
- descoberta complementar registrada em:
  - `docs/experiments/EXP-046-mixed-generalization-inferred-profiles.md`
- Variante C implementada em `fixtures/mixed_generalization_variant_c.discovery.json`
- competicao intra-superficie adicionada:
  - multiplos secrets fortes
  - multiplos parameters fortes
  - multiplos objetos S3 plausiveis
  - multiplos secrets cross-account plausiveis
- assessment discovery-driven validado em:
  - `outputs_mixed_generalization_variant_c_assessment/`
- descoberta complementar registrada em:
  - `docs/experiments/EXP-047-mixed-generalization-same-surface-competition.md`
- Variante D implementada em `fixtures/mixed_generalization_variant_d.discovery.json`
- competicao entre multiplas entry surfaces publicas adicionada
- assessment discovery-driven validado em:
  - `outputs_mixed_generalization_variant_d_assessment/`
- descoberta complementar registrada em:
  - `docs/experiments/EXP-048-mixed-generalization-competing-entry-surfaces.md`

## Estrategia de variacao

Cada ambiente deve variar em tres eixos:

### 1. Naming
- trocar nomes de roles, buckets, secrets e parameters
- evitar overfitting do engine a tokens fixos

### 2. Noise
- baixo / medio / alto
- controlar quantidade de recursos irrelevantes por service

### 3. Decoy topology
- decoy direto
- decoy profundo
- multiplos decoys com semantica parecida

## Regras de implementacao

- cada ambiente deve ter:
  - fixture sintetico
  - objetivo(s) associados quando necessario
  - scopes por classe
  - documentacao propria
- quando um ambiente tiver versao AWS real, ela deve ser separada do repo
  se essa continuar sendo a regra operacional adotada

## Uso estrategico

### Foundation
Usar `internal-data-platform` como base principal.

### Advanced
Adicionar `serverless-business-app` e `compute-pivot-app`.

### Enterprise
Compor cenarios mistos ou cross-account a partir desses arquétipos.

## Backlog recomendado

### Etapa 1
- implementar `internal-data-platform` variantes A/B/C
- conectar ao pipeline discovery-driven

### Etapa 2
- implementar `serverless-business-app` variantes A/B/C
- usar para classes 6 e 7

### Etapa 3
- implementar `compute-pivot-app` variantes A/B/C
- usar para classes 5 e 8

### Etapa 4
- derivar cenarios enterprise a partir da combinacao desses ambientes
