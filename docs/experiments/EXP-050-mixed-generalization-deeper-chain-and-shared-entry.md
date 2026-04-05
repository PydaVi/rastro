# EXP-050 — Mixed Generalization Deeper Chain And Shared Entry

## Identificacao

- ID: EXP-050
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

Depois de `EXP-049`, o benchmark misto ainda favorecia casos onde havia um
melhor alvo claro por surface. Faltava pressionar o selection e o synthesis
com dois fatores ao mesmo tempo:

- mais profundidade de chain
- mais de um alvo forte compartilhando a mesma entry surface

O risco era o Rastro continuar bom em separar classes, mas ainda fraco em
decidir entre caminhos realmente concorrentes quando a mesma entrada publica
poderia levar a mais de um objetivo forte.

## Hipoteses

H1. O benchmark podia crescer para um caso com chain mais profunda sem quebrar
o assessment discovery-driven ponta a ponta.

H2. `aws-cross-account-data` deveria continuar preferindo o caminho direto mais
forte, enquanto `aws-multi-step-data` deveria preferir o alvo semanticamente
mais profundo e estruturalmente mais rico.

H3. O bloco revelaria se ainda havia dependencia excessiva de campos curados no
roteamento misto ou no scoring estrutural.

## Desenho experimental

### Variavel independente

Foi introduzida a variante:

- `fixtures/mixed_generalization_variant_e.discovery.json`

Mudancas principais:

- mais de um alvo forte por entry surface publica
- secret cross-account direto e secret cross-account mais profundo coexistindo
- path multi-step mais profundo para o mesmo dominio de negocio
- expansao dos fixtures sinteticos mistos para suportar os novos alvos:
  - `fixtures/mixed_generalization_cross_account_lab.json`
  - `fixtures/mixed_generalization_multi_step_lab.json`

### Contratos atualizados

- `target selection` passa a inferir `execution_fixture_set` tambem para:
  - `aws-cross-account-data`
  - `aws-multi-step-data`
- `mixed_generalization_cross_account` e `mixed_generalization_multi_step`
  passam a usar scopes dedicados:
  - `examples/scope_mixed_generalization_cross_account.json`
  - `examples/scope_mixed_generalization_multi_step.json`
- o scoring de `aws-cross-account-data` penaliza mais chains profundas, para
  preservar a preferencia por cross-account direto quando isso e a classe mais
  expressiva

## Resultados por etapa

### Etapa 1 — Ajuste estrutural do benchmark

Confirmada.

Os novos targets foram incorporados sem quebrar os benchmarks anteriores:

- variants A/B/C/D seguiram com `campaigns_total = 8`
- variant E passou a gerar `campaigns_total = 9`

Isso mostrou que o benchmark novo ampliou a cobertura sem substituir os casos
anteriores.

### Etapa 2 — Selecao no benchmark E

Confirmada.

Selecao observada:

- `aws-external-entry-data`
  - `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key`
- `aws-cross-account-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key`
- `aws-multi-step-data`
  - `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-master-api-key`

Sinal estrutural relevante:

- `aws-multi-step-data` fechou com `chain_depth = 4`

### Etapa 3 — Rerun ponta a ponta

Confirmada.

Output gerado:

- `outputs_mixed_generalization_variant_e_assessment/`

Resumo observado:

- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

### Causa raiz

- falha de infraestrutura/catalogo sintetico: sim
- falha de representacao de estado: nao
- falha de policy do engine: nao
- falha do planner: nao

O gap revelado foi de benchmark e contrato sintetico:

- os fixtures mistos ainda nao suportavam todos os novos targets profundos
- o roteamento precisava explicitar melhor os scopes de `cross-account` e
  `multi-step`

### Intervencoes

- expansao dos fixtures mistos para os novos alvos
- scopes mistos dedicados para `cross-account` e `multi-step`
- endurecimento da penalidade estrutural em `aws-cross-account-data` para chain
  profunda

## Descoberta principal

O benchmark misto agora diferencia melhor:

- caminho cross-account direto
- caminho multi-step mais profundo

mesmo quando ambos coexistem na mesma regiao semantica e compartilham sinais de
negocio muito parecidos.

## Interpretacao

Esse bloco nao eliminou toda a heuristica, mas empurrou o sistema para uma
separacao mais coerente entre:

- classe que privilegia fronteira de conta e caminho direto
- classe que privilegia chain profunda e composicao ofensiva

Isso reduz um tipo importante de drift:

- confundir caminho mais profundo com melhor caminho para qualquer classe

## Implicacoes arquiteturais

- `aws-cross-account-data` e `aws-multi-step-data` ficaram mais separados por
  estrutura, nao apenas por naming
- o benchmark misto ganhou mais poder para testar competicao entre paths fortes
  sob a mesma superficie
- o contrato entre selection, synthesis e resolver misto ficou mais robusto
  para cenarios enterprise

## Ameacas a validade

- continua sendo benchmark sintetico
- ainda existe curadoria residual em metadata estrutural
- o bloco nao substitui validacao real futura de `cross-account`

## Conclusao

H1, H2 e H3 confirmadas.

O benchmark misto ganhou profundidade e competicao real adicional sem quebrar o
assessment discovery-driven ponta a ponta.

## Proximos passos

1. continuar reduzindo curadoria residual de metadata estrutural no benchmark
   misto
2. usar o benchmark misto como pressao recorrente contra regressao profile-first
3. preparar promocao real seletiva apenas onde houver pre-requisito
   operacional verdadeiro
