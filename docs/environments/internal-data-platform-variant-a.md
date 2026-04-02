# Internal Data Platform — Variant A

## Objetivo

Primeiro ambiente sintetico maior para o `aws-foundation`.

Ele existe para validar:
- target selection sob mais ruido
- campaign synthesis sobre um inventario mais proximo de conta real
- discovery-driven pipeline sem depender de um lab minimo

## Caracteristicas

- naming plausivel de plataforma interna
- buckets de dado, relatorio, backup e terraform state
- roles de auditoria, broker e acesso a dado
- secrets e parameters com namespaces mistos
- ruido suficiente para forcar priorizacao

## Artefato atual

- `fixtures/internal_data_platform_variant_a.discovery.json`

Esse artefato representa o snapshot de discovery do ambiente.
Ele e a primeira implementacao concreta do arquétipo `internal-data-platform`.

Resumo atual do snapshot:
- 7 roles
- 5 buckets
- 7 objetos
- 4 secrets
- 3 parameters

## Sinais intencionais

### Alvos fortes
- `arn:aws:s3:::idp-prod-payroll-data/payroll/2026-03.csv`
- `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key`
- `arn:aws:ssm:us-east-1:123456789012:parameter/prod/payroll/api_key`
- `arn:aws:iam::123456789012:role/PayrollDataAccessRole`

### Ruido controlado
- `idp-public-reports`
- `idp-tf-state`
- `idp-backups`
- `reports/quarterly-slack-webhook`
- `BillingReadRole`
- `QuarterlyAuditRole`

## Papel na estrategia

Variant A e o primeiro degrau de escala.

Ela deve ser usada para:
1. validar target selection fora do ambiente minimo
2. validar campaign synthesis com nomes e superficies mais realistas
3. preparar variantes B e C com mais ruido e ambiguidade

## Proximos passos esperados

- Variant B: mesmo ambiente com mais ruido e colisao semantica
- Variant C: nomes mais ambiguos e mais recursos irrelevantes
- depois disso, conectar esses snapshots a um pipeline sintetico maior

## Resultado atual

O autorun de `target-selection run` sobre a variante A gerou:
- `17` candidatos
- top S3, Secret e SSM coerentes com o alvo de payroll/prod
- `PayrollDataAccessRole` no topo de role chaining
