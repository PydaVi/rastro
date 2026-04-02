# Internal Data Platform — Variant C

## Objetivo

Terceira variante do arquétipo `internal-data-platform`.

Ela eleva a ambiguidade:
- muitos nomes com `prod`, `payroll` e `finance`
- múltiplos buckets e secrets de aparência crítica
- ruído alto em objetos e roles

## Artefato

- `fixtures/internal_data_platform_variant_c.discovery.json`

## Características

- candidatos fortes concorrentes em S3, Secrets e SSM
- role chain com mistura de `DataAccess`, `Broker` e `Audit`
- buckets públicos e privados com naming parecido

## Expectativa de teste

O target selection ainda deve:
- manter `PayrollDataAccessRole` acima de roles de auditoria
- continuar produzindo candidatos fortes mesmo sob ruído alto
- preparar o ambiente para o futuro teste end-to-end discovery-driven

## Resultado atual

O autorun de `target-selection run` sobre a variante C gerou:
- `20` candidatos
- ruído alto com forte ambiguidade lexical em S3, Secrets e SSM
- `PayrollDataAccessRole` ainda no topo de role chaining
- superfícies de dados com muitos candidatos `high confidence`, como esperado
