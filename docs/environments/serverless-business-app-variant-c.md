# Serverless Business App — Variante C

## Objetivo

Terceira variante do arquétipo `serverless-business-app`.

Ela introduz:
- mais ruído semântico
- múltiplas APIs públicas
- colisão de naming em torno de `payroll`, `admin` e `bridge`

## Diferenças para a Variante B

- adiciona `PublicApiBridgeRole`
- adiciona API pública extra (`admin-public-bridge`)
- adiciona secret e parameter ambíguos ligados a `admin_bridge`

## Papel arquitetural

Esta variante existe para estressar o pipeline discovery-driven antes de
abrir de fato as classes `advanced`.
