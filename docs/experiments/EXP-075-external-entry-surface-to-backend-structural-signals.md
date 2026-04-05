# EXP-075 — External Entry Surface-to-Backend Structural Signals

## Identificacao

- ID: EXP-075
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Depois do `EXP-074`, a semantica de maturidade de `external entry` ja era
propagada em:

- `target selection`
- `campaign synthesis`
- reporting

Mas ainda faltava um passo importante dentro do proprio bloco:

- distinguir melhor quando uma superficie publica traz sinais estruturais mais
  fortes de reachability ate o backend

Isso era especialmente relevante para:

- API Gateway
- ALB/NLB

## Hipoteses

H1. O `target selection` deveria conseguir reconhecer sinais estruturais mais
fortes de `surface -> backend`, mesmo antes da execucao final.

H2. Esses sinais deveriam aumentar apenas:

- `network_reachable_from_internet`
- `backend_reachable`

sem colapsar automaticamente o path em:

- `public exploit path proved end-to-end`

## Desenho experimental

### Intervencao estrutural

Foi estendida a inferencia de `external_entry_reachability` para usar metadados
de superficies publicas:

- API Gateway:
  - `public_stage`
  - `integration_status`
- Load balancer:
  - `listener_public`
  - `listener_forwarding`
  - `target_health`

Tambem foi adicionado um teste sintético especifico com:

- API Gateway publico com integracao ativa
- ALB publico com listener publico e target saudavel

## Resultados por etapa

### Etapa 1 — Surface metadata mais forte no selection

Confirmada.

O candidato de `aws-external-entry-data` passou a registrar:

- `network_reachability_proved`
- `backend_reachability_proved`

quando a superficie publica carrega sinais estruturais fortes suficientes.

### Etapa 2 — Conservadorismo mantido

Confirmada.

Mesmo com esses sinais, o sistema nao promove automaticamente o candidato para:

- `public_exploit_path_proved_end-to-end`

Os estados de:

- `credential_acquisition_possible`
- `data_path_exploitable`

continuam separados.

## Erros, intervencoes e motivos

Nao houve falha experimental nova neste bloco.

## Descoberta principal

Nem toda superficie publica deve ser tratada igual.

Ha um nivel intermediario relevante entre:

- exposicao publica declarada
e
- exploit completo provado

Esse nivel e:

- superficie publica com sinais estruturais fortes de reachability ate o backend

## Interpretacao

O ganho aqui e de expressividade ofensiva no plano e no selection:

- o produto escolhe melhor quais `external entry` sao mais promissores
- sem transformar isso em falso positivo operacional

## Implicacoes arquiteturais

- `external_entry_reachability` agora distingue melhor superficies publicas
  fracas vs. fortes
- a futura promocao real pode comparar:
  - hipotese estrutural do plano
  - prova observada no run

## Ameacas a validade

- o bloco continua sintético
- ainda nao ha descoberta AWS real de listeners, target groups e integracoes
- ainda nao ha prova de rede fim a fim em AWS real

## Conclusao

H1 confirmada.

H2 confirmada.

O produto agora modela melhor o trecho:

- `public surface -> backend`

sem misturar isso com:

- cred acquisition
- data path exploitation

## Proximos passos

1. levar esses sinais para discovery AWS real quando possivel
2. modelar listeners, target groups e integracao de API Gateway no inventario
3. preparar promocao seletiva com evidencia de rede em AWS real
