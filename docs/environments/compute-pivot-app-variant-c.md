# Compute Pivot App — Variante C

## Objetivo

Terceira variante do arquétipo `compute-pivot-app`.

Ela abre os primeiros caminhos de:
- `cross-account`
- `multi-step chain`

no mesmo arquétipo em que já existem compute pivot e external entry.

## Características

- duas superfícies públicas convergindo para a mesma identidade local
- pivô local via compute
- role broker intermediária
- role final em outra conta
- alvo final em outra conta com cadeia de pivôs explícita no metadata

## Papel arquitetural

Esta variante força o Produto 01 a sair ainda mais de campaigns AWS
pré-estruturadas e validar:
- pivô local
- salto cross-account
- chain mais profunda
- target selection com sinais estruturais de profundidade e account boundary

Resultado observado:
- bundle `aws-enterprise` do arquétipo passou com `campaigns_passed = 7/7`
- classes abertas:
  - `aws-cross-account-data`
  - `aws-multi-step-data`
