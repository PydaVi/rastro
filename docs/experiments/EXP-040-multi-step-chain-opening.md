# EXP-040 — Abertura de Multi-Step Chain Menos Pré-Modelada

## Identificação
- ID: EXP-040
- Fase: 3
- Status: confirmada

## Contexto
Depois de abrir compute pivot, external entry e cross-account, o próximo passo era validar uma chain mais profunda e menos pré-modelada no mesmo arquétipo.

## Hipóteses
- H1: o target selection consegue distinguir alvos que exigem chain mais profunda.
- H2: o loop central continua suficiente para uma chain com 3 pivôs lógicos.

## Resultados por etapa

### Etapa 1 — Seleção multi-step
- melhor candidato de `aws-multi-step-data`:
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key`
- sinais observados:
  - `multi_step_chain`
  - `pivot_chain`
  - `cross_account_depth_bonus`

### Etapa 2 — Assessment enterprise
- output:
  - `outputs_compute_pivot_app_enterprise_variant_c_assessment/assessment.json`
- resultado:
  - campanha `aws-multi-step-data` passou
  - bundle enterprise do arquétipo fechou com `campaigns_passed = 7/7`

## Implementação introduzida
- novo profile `aws-multi-step-data`
- scoring baseado em:
  - profundidade de `pivot_chain`
  - bonus por profundidade cross-account
- redução adicional de dependência lexical:
  - metadados de cadeia não entram mais como texto bruto no ranking lexical

## Descoberta principal
O target selection começou a sair de sinais nominais para sinais de estrutura de path. Isso é um passo direto na direção de menor pré-modelagem e maior generalização ofensiva.

## Conclusão
- H1: confirmada
- H2: confirmada
