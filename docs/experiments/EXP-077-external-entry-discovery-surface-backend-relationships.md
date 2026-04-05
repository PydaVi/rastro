# EXP-077 — External Entry Discovery Surface-Backend Relationships

## Identificacao

- ID: EXP-077
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

O `EXP-076` fez o discovery AWS coletar superfícies públicas:

- `network.load_balancer`
- `network.api_gateway`

Faltava o próximo passo natural:

- representar no inventário as relações estruturais entre a superfície pública
  e o backend

Sem isso, ainda havia uma lacuna entre:

- “a conta tem uma superfície pública”
e
- “o produto já sabe como essa superfície se encadeia até um workload”

## Hipoteses

H1. O discovery AWS deveria coletar, em primeiro corte, os artefatos mínimos
para `surface -> backend`:

- `target_group`
- `listener`
- `api_integration`

H2. O inventory deveria registrar relações suficientes para suportar a
semântica futura de:

- `ALB/NLB -> listener -> target group -> backend`
- `API Gateway -> integration -> backend`

## Desenho experimental

### Intervencao estrutural

Foram adicionados ao `AwsClient`:

- `list_target_groups()`
- `list_listeners()`
- `list_api_integrations()`

O `run_foundation_discovery()` passou a coletar:

- `network.target_group`
- `network.lb_listener`
- `network.api_integration`

Relações novas:

- `exposes_listener`
- `forwards_to_target_group`
- `uses_target_group`
- `uses_integration`
- `integrates_with_instance`
- `integrates_with_load_balancer`

## Resultados por etapa

### Etapa 1 — Listener / target group

Confirmada.

O discovery agora já registra:

- o load balancer
- seu listener
- o target group associado

### Etapa 2 — API Gateway integration

Confirmada.

O discovery agora já registra:

- a API
- a integration
- e o vínculo estrutural com:
  - instância
  - ou load balancer

### Etapa 3 — Relações estruturais até o backend

Confirmada.

O inventário agora suporta, no mínimo:

- `surface -> listener -> target group`
- `surface -> integration -> backend`

## Erros, intervencoes e motivos

Nao houve falha experimental nova neste bloco.

## Descoberta principal

O discovery de `external entry` deixou de ser apenas inventário de superfícies
e passou a registrar o primeiro corte útil de `surface -> backend`.

## Interpretacao

Esse bloco ainda nao prova:

- target health real por target
- rules detalhadas
- API Gateway fim a fim em AWS real

Mas ele fecha uma lacuna arquitetural importante:

- agora existe um grafo de rede mínimo entre entrada pública e backend

## Implicacoes arquiteturais

- a próxima promoção real de `external entry` pode ser sustentada por
  inventário melhor
- o `target selection` e o reporting poderão comparar:
  - hipótese estrutural
  - e observação real de execução

## Ameacas a validade

- ainda faltam:
  - listener rules detalhadas
  - target health por backend real
  - integração real observada em AWS

## Conclusao

H1 confirmada.

H2 confirmada.

O discovery AWS agora registra um primeiro grafo útil de
`public surface -> backend`, aproximando o Produto 01 de validação mais forte
de `external entry`.

## Proximos passos

1. usar essas relações no selection/reporting quando existirem
2. preparar promoção seletiva em AWS real com evidência de rede
3. depois endurecer target health / rules / integrations reais
