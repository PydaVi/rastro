# EXP-071 — External Entry Network Discovery Foundation

## Identificacao

- ID: EXP-071
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

O produto ja separava conceitualmente os estados de maturidade de
`external entry`, mas o discovery AWS ainda era pobre para reachability de rede.

O inventario coletava bem:

- IAM
- S3
- Secrets Manager
- SSM

Mas ainda nao coletava, no fluxo discovery-driven real, os elementos minimos
para sustentar uma prova mais rigorosa de compute publico:

- instance profile
- instância EC2
- subnet
- route table
- Internet Gateway
- security group

Sem isso, `external entry` continuava excessivamente dependente de:

- metadata estrutural pre-curada
- path semantico plausivel

## Hipoteses

H1. O discovery AWS do Produto 01 deveria coletar um conjunto minimo de
recursos e relacoes de rede para compute publico.

H2. Esse primeiro corte de discovery de rede deveria ser suficiente para
representar, no inventory, o encadeamento:

- Internet Gateway
- route table
- subnet
- EC2
- instance profile
- role

H3. Esse bloco ainda nao deveria ser descrito como prova de exploit publico
fim a fim.

## Desenho experimental

### Intervencao estrutural

Foram adicionados ao `AwsClient` e ao `run_foundation_discovery()`:

- `list_instance_profiles()`
- `list_instances()`
- `list_internet_gateways()`
- `list_route_tables()`
- `list_subnets()`
- `list_security_groups()`

O discovery passou a registrar:

- novos recursos em `resources`
- novas relacoes em `relationships`

Relacoes introduzidas:

- `attached_to_instance_profile`
- `uses_instance_profile`
- `deployed_in_subnet`
- `associated_with_route_table`
- `routes_to_internet_gateway`
- `protected_by_security_group`

### Validacao

Foi usada a suite offline com `FakeAwsClient`.

## Resultados por etapa

### Etapa 1 — Inventory de rede AWS no discovery

Confirmada.

O discovery agora produz, alem do inventario original:

- `compute.instance_profile`
- `compute.ec2_instance`
- `network.internet_gateway`
- `network.route_table`
- `network.subnet`
- `network.security_group`

### Etapa 2 — Relacoes explicitas ate o workload

Confirmada.

O snapshot agora registra relacoes suficientes para provar, no minimo:

- a instância pertence a uma subnet
- a subnet esta associada a uma route table
- a route table roteia para um Internet Gateway
- a instância esta protegida por um security group
- a instância usa um instance profile

### Etapa 3 — Reporting sem overclaim

Confirmada.

O bloco foi mantido como discovery foundation.

Nao houve mudanca de linguagem para sugerir:

- `public exploit path proved end-to-end`

## Erros, intervencoes e motivos

Nao houve falha experimental nova neste bloco.

O trabalho foi de ampliacao de representacao e inventario.

## Descoberta principal

O gap principal nao estava em selection nem em execution.

O gap estava no discovery real:

- faltava o grafo minimo de rede para que `external entry` deixasse de depender
  apenas de exposicao estrutural declarada

## Interpretacao

Esse bloco nao prova explorabilidade publica fim a fim.

Ele melhora a base epistemica do Produto 01 para os proximos blocos:

- agora existe inventario de rede minimo
- agora existe relacao explicita ate o workload
- agora os proximos benchmarks podem separar melhor:
  - exposicao estrutural
  - backend reachability
  - cred acquisition
  - path ao dado

## Implicacoes arquiteturais

- `run_foundation_discovery()` deixou de ser apenas discovery de dados e
  identidades; ele passou a incluir uma camada minima de topologia de rede AWS
- o inventory do Produto 01 agora suporta evolucao posterior de:
  - selection
  - synthesis
  - reporting
  para `external entry` com mais rigor

## Ameacas a validade

- ainda nao ha modelagem de:
  - ALB/NLB listeners e rules
  - API Gateway ate backend
  - reachability real de rede ate o workload
- ainda nao ha benchmark sintético novo com estados separados de maturidade
- ainda nao ha promocao real de rede fim a fim

## Conclusao

H1 confirmada.

H2 confirmada.

H3 confirmada.

O primeiro corte do `Bloco 1 — External Entry Reachability Real` foi concluido:

- inventory de rede AWS minimo
- relacoes explicitas ate o workload

O que ainda falta e exatamente o que o bloco precisava deixar claro:

- benchmark sintético de reachability separado por estados
- integracao dessa semantica em selection / synthesis / reporting

## Proximos passos

1. criar benchmark sintético com:
   - superfície publica sem backend reachável
   - backend reachável sem cred acquisition
   - cred acquisition possível sem path ao dado
   - cadeia completa
2. integrar essa semantica ao target selection e ao campaign synthesis
3. preparar promocao seletiva para AWS real com evidencia de rede
