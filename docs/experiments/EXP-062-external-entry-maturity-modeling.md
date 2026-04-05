# EXP-062 — External Entry Maturity Modeling

## Identificacao

- ID: EXP-062
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

O produto ja provava bem:

- `credential path -> data`

Mas ainda faltava separar com rigor conceitual:

- exposicao publica estrutural
- reachability real de rede ate o workload
- aquisicao de credenciais
- explotabilidade completa ate o dado

Sem essa separacao, `external entry` corria risco de falso positivo
conceitual no reporting.

## Hipoteses

H1. O reporting do produto deveria distinguir explicitamente os estados de
maturidade de `external entry`.

H2. Findings e sumarios executivos nao deveriam mais sugerir
`public exploit path proved end-to-end` quando so existe:

- superficie publica estrutural
- pivô credenciado controlado
- path ao dado

## Desenho experimental

### Intervencao estrutural

Foram adicionados ao `executive_summary`:

- `external_entry_maturity.applicable`
- `external_entry_maturity.classification`
- `external_entry_maturity.network_reachable_from_internet`
- `external_entry_maturity.backend_reachable`
- `external_entry_maturity.credential_acquisition_possible`
- `external_entry_maturity.data_path_exploitable`

Estados atuais por item:

- `not_observed`
- `structural`
- `proved`

Classificacoes atuais:

- `not_applicable`
- `public_exposure_structurally_linked_to_privileged_path`
- `public_exploit_path_proved_end_to_end`

Tambem foi ajustado o texto de findings para `aws-external-entry-data`.

## Resultados por etapa

### Etapa 1 — Report de external entry

Confirmada.

No fixture sintético `compute_pivot_app_external_entry_lab.json`, o report agora
registra:

- `network_reachable_from_internet = structural`
- `backend_reachable = structural`
- `credential_acquisition_possible = structural`
- `data_path_exploitable = not_observed`
- classificacao:
  - `public_exposure_structurally_linked_to_privileged_path`

Interpretacao:

- o run prova o pivô estrutural
- nao prova explorabilidade fim a fim da internet ate o dado

### Etapa 2 — Findings executivos

Confirmada.

Findings de `aws-external-entry-data` passaram a usar linguagem controlada:

- `Public exposure structurally linked to privileged path.`

e deixam de implicar automaticamente:

- `public exploit path proved end-to-end`

## Erros, intervencoes e motivos

Nao houve falha experimental nova neste bloco.

## Descoberta principal

O gap era conceitual e de produto, nao do engine:

- o produto precisava de uma régua explicita para `external entry`
- sem isso, a linguagem podia comprimir estados diferentes em uma prova unica

## Interpretacao

Esse bloco nao aumenta alcance ofensivo por si so.

Ele melhora a qualidade epistemica do Produto 01:

- evita overclaim
- prepara os proximos blocos de reachability real de rede
- separa claramente o que foi provado do que ainda nao foi

## Implicacoes arquiteturais

- `external entry` agora tem semantica de maturidade explicita no report
- findings e reporting podem evoluir sem colapsar:
  - exposicao estrutural
  - pivô credenciado
  - exploit path completo

## Ameacas a validade

- esse bloco modela estados; nao prova ainda reachability real de rede
- a classificacao `proved end-to-end` ainda depende dos blocos futuros de rede

## Conclusao

H1 confirmada.

H2 confirmada.

O bloco reduziu falso positivo conceitual no produto e abriu a trilha correta
para maturidade de `external entry`.

## Proximos passos

1. discovery de rede AWS para compute publico
2. reachability de ALB/NLB/API Gateway ate backend
3. promocao seletiva para AWS real com evidencia de rede
