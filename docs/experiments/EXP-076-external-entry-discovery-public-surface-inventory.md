# EXP-076 — External Entry Discovery Public Surface Inventory

## Identificacao

- ID: EXP-076
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

O `EXP-075` refinou a inferencia estrutural de `surface -> backend` no
`target selection`.

Faltava agora levar parte dessa semantica para o discovery AWS real, para que o
inventario passasse a coletar superficies publicas de forma explicita, e nao
dependesse apenas de snapshots sintéticos mais ricos.

## Hipoteses

H1. O discovery AWS deveria coletar, no primeiro corte, superficies publicas de:

- ALB/NLB
- API Gateway

H2. O inventory deveria registrar metadados minimos suficientes para suportar
reachability estrutural mais forte em blocos futuros.

## Desenho experimental

### Intervencao estrutural

Foram adicionados ao `AwsClient`:

- `list_load_balancers()`
- `list_rest_apis()`

O `run_foundation_discovery()` passou a coletar:

- `network.load_balancer`
- `network.api_gateway`

Metadados iniciais:

- load balancer:
  - `exposure`
  - `internet_facing`
  - `dns_public`
  - `dns_name`
  - `state`
- api gateway:
  - `exposure`
  - `public_stage`
  - `endpoint_types`

## Resultados por etapa

### Etapa 1 — Inventory de public surfaces

Confirmada.

O discovery agora inclui, alem da camada EC2/rede já adicionada em `EXP-071`:

- `network.load_balancer`
- `network.api_gateway`

### Etapa 2 — Metadados minimos para reachability estrutural

Confirmada.

O inventory passou a carregar sinais mínimos que podem ser usados por blocos
seguintes para diferenciar:

- superficie publica apenas declarada
vs.
- superficie publica com sinais mais fortes de internet reachability

## Erros, intervencoes e motivos

Nao houve falha experimental nova neste bloco.

## Descoberta principal

Para `external entry`, o discovery precisava conhecer explicitamente as
superficies publicas da conta, e nao apenas os workloads atras delas.

## Interpretacao

Esse bloco nao prova integração fim a fim de:

- API Gateway -> backend
- ALB/NLB -> target group -> backend

Mas fecha um pre-requisito importante:

- o inventory real agora já conhece as entry surfaces publicas

## Implicacoes arquiteturais

- o discovery AWS ficou mais alinhado com a semantica de `external entry`
- a próxima evolução natural e:
  - target groups
  - listeners/rules
  - integracao de API Gateway

## Ameacas a validade

- ainda nao ha target groups/listeners
- ainda nao ha integracao completa de API Gateway
- ainda nao ha reachability real fim a fim

## Conclusao

H1 confirmada.

H2 confirmada.

O discovery AWS agora coleta um inventario minimo de superficies publicas para
`external entry`, reduzindo o gap entre benchmark sintético e discovery real.

## Proximos passos

1. adicionar target groups / listeners / forwarding
2. adicionar integracao de API Gateway ate backend
3. preparar promocao seletiva para AWS real com evidencia de rede
