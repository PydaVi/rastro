# Serverless Business App — Variante B

## Objetivo

Segunda variante do arquétipo `serverless-business-app`.

Ela preserva as superfícies da Variante A, mas adiciona KMS e mais ambiguidade
operacional em torno de segredos protegidos por chave.

## Diferenças para a Variante A

- adiciona `PayrollDecryptRole`
- adiciona KMS keys explícitas para runtime
- adiciona associação entre secrets/Lambda e KMS
- aumenta o ruído semântico em torno de payroll e billing

## Papel arquitetural

Esta variante prepara o terreno para:
- classe 7: `IAM -> KMS -> data`
- classes serverless avançadas
- seleção de alvo em ambiente com criptografia explícita
