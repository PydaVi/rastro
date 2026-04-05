# EXP-053 — Mixed Generalization Obfuscated Target Harness Mismatch

## Identificacao

- ID: EXP-053
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

Depois de `EXP-052`, o proximo passo foi reduzir ainda mais `naming` favorecido
no benchmark misto, obfuscando:

- principals
- pivots compute
- entry surfaces
- e tambem alguns recursos que eram alvo de campanhas sinteticas

A expectativa era manter o benchmark enterprise estavel apenas com estrutura e
nomes finais dos dados mais relevantes.

## Hipoteses

H1. Obfuscar nomes de pivots e entry surfaces nao deveria quebrar o benchmark
enterprise.

H2. Se houvesse falha, ela deveria revelar um gap de harness sintetico e nao do
engine ofensivo.

## Desenho experimental

### Variavel independente

Foi criada:

- `fixtures/mixed_generalization_variant_h.discovery.json`

Mudanca principal:

- obfuscacao de nomes de roles, instance profiles, instances, API Gateway,
  Lambda e KMS

## Resultados por etapa

### Etapa 1 — Selection

Confirmada.

A selecao continuou correta para:

- `aws-external-entry-data`
- `aws-cross-account-data`
- `aws-multi-step-data`

### Etapa 2 — Assessment discovery-driven inicial

Falhou.

Resumo observado:

- `campaigns_total = 9`
- `campaigns_passed = 6`
- `campaigns_objective_not_met = 3`

Campanhas afetadas:

- `aws-iam-role-chaining`
- `aws-iam-kms-data`
- `aws-iam-lambda-data`

### Etapa 3 — Correcao de benchmark e rerun

Confirmada.

Correcao aplicada:

- a variante H passou a preservar nomes canonicos dos recursos alvo direto de:
  - `aws-iam-role-chaining`
  - `aws-iam-kms-data`
  - `aws-iam-lambda-data`
- pivots compute e entry surfaces permaneceram obfuscados

Output gerado:

- `outputs_mixed_generalization_variant_h_assessment/`

Resumo observado:

- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

### Causa raiz

- falha de infraestrutura/harness sintetico: sim
- falha de representacao de estado: nao
- falha de policy do engine: nao
- falha do planner: nao

Diagnostico:

- os fixtures sinteticos dessas classes validam `objective.target` por ARN
  exato
- a variante H obfuscou tambem os identificadores de recursos que sao alvo
  direto dessas campanhas
- o assessment continuou gerando campanhas coerentes, mas com targets que os
  fixtures sinteticos nao reconheciam

Isso nao revelou uma regressao do engine. Revelou acoplamento entre:

- nome observado no discovery
- nome canonico esperado pelo fixture sintetico

## Descoberta principal

O benchmark pode obfuscar pivots e entry surfaces sem problema, mas nao pode
obfuscar indiscriminadamente recursos que funcionam como alvo direto de fixtures
sinteticos que dependem de correspondencia exata de ARN.

## Interpretacao

Esse bloco mostrou um limite real do harness:

- nem toda reducao de naming favorecido pode ser feita no mesmo eixo de uma vez

Para esse benchmark, a reducao correta e:

- obfuscar intermediarios e entry surfaces
- preservar os alvos diretos das classes cujo fixture depende do ARN exato

## Implicacoes arquiteturais

- o failure nao invalida o ganho de generalizacao do benchmark
- ele delimita melhor onde o harness sintetico ainda e sensivel a naming
- reforca que correcoes aqui devem ser tratadas como infraestrutura de
  benchmark, nao como mudanca no loop ofensivo

## Ameacas a validade

- esse resultado vale para o harness sintetico atual
- nao informa diretamente sobre o comportamento do executor real

## Conclusao

H1 confirmada apos a correcao de benchmark.

H2 confirmada: a falha foi de harness sintetico, nao do engine.

O bloco agora fica consolidado assim:

- naming de pivots e entry surfaces menos favorecido
- targets diretos de classes com fixture ARN-exato preservados
- benchmark enterprise volta a fechar `9/9`

## Proximos passos

1. continuar reduzindo naming favorecido nos pivots e intermediarios
2. evitar obfuscar indiscriminadamente alvos diretos de fixtures ARN-exatos
3. seguir para aliases e nomes de negocio menos evidentes nos recursos finais
