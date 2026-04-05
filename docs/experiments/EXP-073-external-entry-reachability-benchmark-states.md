# EXP-073 — External Entry Reachability Benchmark States

## Identificacao

- ID: EXP-073
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Depois do `EXP-072`, o benchmark de maturidade de `external entry` passou a
usar um objetivo proprio, sem `success_criteria.flag` herdado da campaign
operacional.

O objetivo deste experimento foi validar os quatro estados previstos no
`Bloco 1 — External Entry Reachability Real`.

## Hipoteses

H1. O benchmark deveria separar corretamente:

- superficie publica sem backend reachavel
- backend reachavel sem cred acquisition
- cred acquisition possivel sem path ao dado
- cadeia completa

H2. Apenas a cadeia completa deveria gerar:

- `public_exploit_path_proved_end-to-end`

H3. Os tres estados intermediarios deveriam permanecer em:

- `public_exposure_structurally_linked_to_privileged_path`

## Desenho experimental

### Ambiente

Fixtures sintéticos:

- `compute_pivot_app_external_entry_surface_only_lab.json`
- `compute_pivot_app_external_entry_backend_reachable_lab.json`
- `compute_pivot_app_external_entry_credential_acquisition_lab.json`
- `compute_pivot_app_external_entry_end_to_end_lab.json`

Objetivo de benchmark:

- `examples/objective_external_entry_reachability_benchmark.json`

### Critério

Validar, no `report.json`, os estados:

- `network_reachable_from_internet`
- `backend_reachable`
- `credential_acquisition_possible`
- `data_path_exploitable`

## Resultados por etapa

### Etapa 1 — Surface only

Confirmada.

Resultado:

- `network_reachable_from_internet = structural`
- `backend_reachable = not_observed`
- `credential_acquisition_possible = not_observed`
- `data_path_exploitable = not_observed`
- classificacao:
  - `public_exposure_structurally_linked_to_privileged_path`

### Etapa 2 — Backend reachable

Confirmada.

Resultado:

- `network_reachable_from_internet = proved`
- `backend_reachable = proved`
- `credential_acquisition_possible = not_observed`
- `data_path_exploitable = not_observed`
- classificacao:
  - `public_exposure_structurally_linked_to_privileged_path`

### Etapa 3 — Credential acquisition possible

Confirmada.

Resultado:

- `network_reachable_from_internet = proved`
- `backend_reachable = proved`
- `credential_acquisition_possible = proved`
- `data_path_exploitable = not_observed`
- classificacao:
  - `public_exposure_structurally_linked_to_privileged_path`

### Etapa 4 — Full chain

Confirmada.

Resultado:

- `network_reachable_from_internet = proved`
- `backend_reachable = proved`
- `credential_acquisition_possible = proved`
- `data_path_exploitable = proved`
- classificacao:
  - `public_exploit_path_proved_end-to-end`

## Erros, intervencoes e motivos

O erro relevante deste bloco foi o run inicial documentado no `EXP-072`.

Depois da separacao do objetivo de benchmark, nao houve nova falha.

## Descoberta principal

Com objetivo alinhado ao benchmark, o produto agora separa corretamente os
quatro estados de maturidade de `external entry`.

## Interpretacao

Esse resultado fecha a parte sintética do passo 3 do bloco:

- agora o produto ja nao confunde automaticamente:
  - superficie publica
  - backend reachavel
  - cred acquisition
  - explorabilidade completa

## Implicacoes arquiteturais

- `external_entry_maturity` ja suporta um benchmark progressivo realista
- o proximo ganho de leverage passa a ser integrar essa semantica:
  - ao selection
  - ao campaign synthesis
  - e depois a validacao AWS real com evidencia de rede

## Ameacas a validade

- benchmark ainda sintético
- ainda nao ha ALB/NLB/API Gateway -> backend real
- ainda nao ha prova de reachability de rede fim a fim em AWS real

## Conclusao

H1 confirmada.

H2 confirmada.

H3 confirmada.

O benchmark de maturidade de `external entry` agora esta validado e separa os
quatro estados esperados.

## Proximos passos

1. integrar a nova semantica ao target selection / campaign synthesis
2. modelar ALB/NLB/API Gateway -> backend
3. preparar promocao seletiva para AWS real com evidencia de rede
