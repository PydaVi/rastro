# Internal Data Platform — Variant B

## Objetivo

Segunda variante do arquétipo `internal-data-platform`.

Ela aumenta:
- ruído semântico
- colisão entre nomes de payroll, archive e finance
- número de resources plausíveis mas secundários

## Artefato

- `fixtures/internal_data_platform_variant_b.discovery.json`

## Características

- secrets e objetos de archive com nomes fortes
- buckets e roles adicionais de reporting
- parameters extras em `prod/`

## Expectativa de teste

O target selection ainda deve:
- manter `PayrollDataAccessRole` no topo de role chaining
- continuar priorizando superfícies de payroll/prod
- tolerar colisão com `archive` e `reporting`

## Resultado atual

O autorun de `target-selection run` sobre a variante B gerou:
- `20` candidatos
- ruído semântico maior em S3, Secrets e SSM
- `PayrollDataAccessRole` preservada no topo de role chaining
