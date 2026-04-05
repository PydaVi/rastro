# EXP-035 — Abertura das Classes Advanced em Serverless Business App

## Identificação
- ID: EXP-035
- Fase: 3
- Status: confirmada

## Contexto
Depois de endurecer o `foundation` no arquétipo `serverless-business-app`, o próximo passo era abrir as primeiras classes `advanced` sem mudar o loop central do engine.

As classes abertas nesta etapa foram:
- `aws-iam-lambda-data`
- `aws-iam-kms-data`

## Hipóteses
- H1: o pipeline discovery-driven consegue incorporar `Lambda` como nova família de alvo.
- H2: o pipeline discovery-driven consegue incorporar `KMS` como nova família de alvo.
- H3: a abertura dessas classes pode ser feita com os tipos de ação atuais (`enumerate`, `assume_role`, `access_resource`), sem refactor do domain model.

## Resultados por etapa

### Etapa 1 — Variante A
- `aws-advanced` gerou `campaigns_total = 5`
- `campaigns_passed = 5`
- interpretação:
  - `Lambda` foi aberta com sucesso
  - `KMS` ainda não aparece porque a Variante A não possui esse recurso

### Etapa 2 — Variante B
- `aws-advanced` gerou `campaigns_total = 6`
- `campaigns_passed = 6`
- interpretação:
  - `Lambda` continua estável
  - `KMS` entra no pipeline sem quebrar as campanhas foundation

### Etapa 3 — Variante C
- `aws-advanced` gerou `campaigns_total = 6`
- `campaigns_passed = 6`
- interpretação:
  - `Lambda` e `KMS` permanecem estáveis mesmo com ruído público/admin adicional
  - o pipeline continua discovery-driven sem precisar de ajuste novo no loop central

## Implementação introduzida
- novas famílias no `target selection`:
  - `aws-iam-lambda-data`
  - `aws-iam-kms-data`
- seleção agora respeita `bundle_name`
- scoring usa também `metadata` dos recursos, não só ARN
- novos perfis sintéticos do `serverless-business-app`
- novos tools sintéticos:
  - `lambda_invoke`
  - `kms_decrypt`

## Descoberta principal
O engine já consegue abrir classes `advanced` usando o mesmo loop central, desde que a semântica do path seja representada por fixtures e tools consistentes. A Variante C mostrou que isso continua verdadeiro mesmo quando o inventário adiciona ruído de API pública, bridge/admin tokens e roles competidoras.

## Conclusão
- H1: confirmada
- H2: confirmada
- H3: confirmada
