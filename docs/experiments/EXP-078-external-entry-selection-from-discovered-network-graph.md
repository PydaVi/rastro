# EXP-078 — External Entry Selection From Discovered Network Graph

## Identificacao

- ID: EXP-078
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

O `EXP-077` fez o discovery AWS registrar um primeiro grafo de:

- `load balancer -> listener -> target group`
- `api gateway -> integration -> backend`

Faltava transformar esse grafo em valor de produto imediato:

- usar essas relações no `target selection` de `aws-external-entry-data`

Sem isso, o discovery ficava mais rico, mas o selection ainda dependia
principalmente de metadados locais da superfície.

## Hipoteses

H1. O `target selection` deveria usar o grafo recém-descoberto para inferir
melhor:

- `network_reachable_from_internet`
- `backend_reachable`

H2. Esse ganho deveria acontecer mesmo quando a informação viesse do grafo
descoberto, e não apenas de metadata isolada do recurso.

## Desenho experimental

### Intervencao estrutural

O índice estrutural do `target selection` passou a incorporar:

- `load_balancer_to_listeners`
- `listener_to_target_groups`
- `api_gateway_to_integrations`
- `integration_to_instances`
- `integration_to_load_balancers`

Também foi ajustada a inferência de reachability por superfície para usar:

- listeners
- target groups
- integrations

## Resultados por etapa

### Etapa 1 — Grafo de discovery usado no selection

Confirmada.

Com snapshot de discovery gerado pelo `FakeAwsClient`, o candidato externo
passou a receber:

- `network_reachability_proved`
- `backend_reachability_proved`

quando o grafo contém:

- `api gateway -> integration -> instance`
- ou
- `load balancer -> listener -> target group`

### Etapa 2 — Continuidade do conservadorismo

Confirmada.

Mesmo com esse ganho, o selection continua sem colapsar automaticamente:

- `credential_acquisition_possible`
em
- `data_path_exploitable`

## Erros, intervencoes e motivos

Nao houve falha experimental nova neste bloco.

## Descoberta principal

O discovery de rede passa a ter valor ofensivo concreto quando alimenta o
selection, e nao apenas o inventario.

## Interpretacao

Esse bloco aumenta a generalizacao ofensiva de `external entry` porque reduz a
dependencia de:

- metadata local da superfície

e aumenta o peso de:

- inferência por relationships observadas

## Implicacoes arquiteturais

- `external_entry_reachability` agora já pode ser derivado a partir do grafo de
  discovery
- isso aproxima mais o produto de uma futura validação real com evidência de
  rede

## Ameacas a validade

- o bloco ainda usa validação offline
- ainda faltam rules detalhadas e target health real
- ainda falta promoção seletiva em AWS real

## Conclusao

H1 confirmada.

H2 confirmada.

O `target selection` agora aproveita melhor o grafo `surface -> backend`
descoberto em AWS, reduzindo mais um atalho estrutural em `external entry`.

## Proximos passos

1. preparar promoção seletiva em AWS real com evidência de rede
2. depois endurecer target health / listener rules / integrations reais
