# EXP-046 — Mixed Generalization With Inferred Profiles

## Identificacao

- ID: EXP-046
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

`EXP-044` e `EXP-045` melhoraram selecao e synthesis no benchmark misto, mas
ainda havia um apoio manual importante: `candidate_profiles` curado no
discovery snapshot.

Isso ainda deixava o sistema perto demais de:

- alvo semi-anotado
- profile sugerido pelo fixture

em vez de:

- profile inferido a partir da estrutura observada

## Hipoteses

H1. O Rastro conseguiria manter a mesma escolha principal no benchmark misto
mesmo sem `candidate_profiles` curado.

H2. Regras simples de inferencia estrutural seriam suficientes para:

- external entry
- cross-account
- multi-step
- compute pivot

sem regressao no assessment discovery-driven.

## Desenho experimental

### Variavel independente

- snapshot novo:
  - `fixtures/mixed_generalization_variant_b.discovery.json`
- remocao de `candidate_profiles`
- inferencia estrutural no `target selection` a partir de:
  - `resource_type`
  - `reachable_roles`
  - `pivot_chain`
  - `role_to_public_surfaces`
  - `role_to_instance_profiles`
  - `chain_depth`

### Criterio

- manter os melhores alvos do benchmark misto
- registrar `inferred_profile_mapping`
- assessment discovery-driven continuar passando ponta a ponta

## Resultados por etapa

### Etapa 1 — Selection sem `candidate_profiles`

Confirmada.

Resultados observados:

- `aws-external-entry-data`
  - alvo topo: `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key`
- `aws-cross-account-data`
  - alvo topo: `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key`
- `aws-multi-step-data`
  - alvo topo: `arn:aws:secretsmanager:us-east-1:210987654321:secret:prod/finance/warehouse-api-key`

O candidato `aws-external-entry-data` passou a registrar:

- `inferred_profile_mapping`
- `signals.inferred_profiles`

### Etapa 2 — Assessment discovery-driven

Confirmada.

Resultado observado em:

- `outputs_mixed_generalization_variant_b_assessment/assessment.json`

Resumo:

- `campaigns_total = 8`
- `campaigns_passed = 8`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Nao houve falha experimental. O bloco foi uma reducao deliberada de apoio
manual no benchmark.

Intervencao aplicada:

- `target selection` ganhou `_infer_candidate_profiles(...)`

## Descoberta principal

O benchmark misto ja nao depende de `candidate_profiles` curado para manter a
classe de path mais expressiva nos casos mais importantes do bloco.

## Interpretacao

Esse passo nao elimina toda a curadoria do ambiente, mas troca:

- anotacao direta de profile

por

- inferencia baseada em estrutura observada

Isso aproxima o sistema de um selecionador de campanhas mais autonomo.

## Implicacoes arquiteturais

- a inferencia estrutural deve crescer antes de qualquer tentativa de remover
  bundles e profiles do produto
- o proximo passo e reduzir tambem a dependencia de resolvers sinteticos curados
- mixed environments continuam sendo o benchmark certo para medir esse avanço

## Ameacas a validade

- ainda e benchmark sintetico
- as regras de inferencia ainda sao hand-written
- o resolver sintetico misto continua curado

## Conclusao

H1 e H2 confirmadas.

O Rastro avancou mais um passo de:

- profiles sugeridos pelo ambiente

para:

- profiles inferidos a partir da estrutura

## Proximos passos

1. mixed benchmark com mais de um alvo forte por mesma superficie
2. reduzir curadoria no resolver sintetico misto
3. transferir mais sinais do benchmark misto para discovery real
