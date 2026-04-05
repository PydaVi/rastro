# EXP-074 — External Entry Reachability in Selection and Synthesis

## Identificacao

- ID: EXP-074
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Depois de:

- `EXP-071` — discovery foundation de rede AWS
- `EXP-073` — benchmark sintético com quatro estados de maturidade

faltava o passo 4 do `Bloco 1`:

- refletir a nova semantica de `external entry` em:
  - target selection
  - campaign synthesis
  - reporting intermediario

Sem isso, a nova modelagem ficava restrita ao `report.json` final do run.

## Hipoteses

H1. O `target selection` deveria carregar, para `aws-external-entry-data`,
uma hipótese explícita de maturidade de reachability.

H2. Essa hipótese deveria ser propagada para o `campaign_plan`, evitando perder
o contexto estrutural entre discovery e execução.

H3. A integração deveria permanecer conservadora:

- surface pública declarada no discovery não deveria virar
  `public exploit path proved end-to-end`

## Desenho experimental

### Intervencao estrutural

Foram adicionados ao `target selection`:

- derivação de `instance_network_maturity`
- hipótese `external_entry_reachability` por candidato

Estados propagados:

- `network_reachable_from_internet`
- `backend_reachable`
- `credential_acquisition_possible`
- `data_path_exploitable`

Tambem foi ajustado o `campaign_synthesis` para carregar essa hipótese no
`campaign_plan.json` e no `campaign_plan.md`.

## Resultados por etapa

### Etapa 1 — Target selection

Confirmada.

No `compute_pivot_app_variant_b.discovery.json`, o melhor candidato de
`aws-external-entry-data` agora carrega:

- `network_reachable_from_internet = structural`
- `backend_reachable = structural`
- `credential_acquisition_possible = structural`

Interpretacao:

- o discovery estrutural ainda nao prova reachability fim a fim
- mas agora a campanha carrega explicitamente essa fronteira

### Etapa 2 — Campaign synthesis

Confirmada.

O `campaign_plan` agora preserva `external_entry_reachability`, o que melhora:

- auditoria do plano derivado
- coerencia entre candidate selection e execução
- reporting intermediario antes do run final

### Etapa 3 — Conservadorismo sem overclaim

Confirmada.

A integração manteve a linguagem correta:

- contexto estrutural no plano
- sem promover automaticamente esse contexto a prova de exploit fim a fim

## Erros, intervencoes e motivos

Nao houve falha experimental nova relevante neste bloco.

## Descoberta principal

A semantica de maturidade de `external entry` precisa existir em toda a cadeia
do produto, nao apenas no report final:

- discovery
- target selection
- campaign synthesis
- reporting

## Interpretacao

Esse bloco nao prova rede real fim a fim.

Ele fecha a coesao interna do Produto 01:

- a hipótese de reachability agora acompanha o candidato e o plano
- a execução futura pode ser comparada contra uma hipótese explícita

## Implicacoes arquiteturais

- `target_candidates.json` ficou mais expressivo para `external entry`
- `campaign_plan.json` agora preserva contexto de maturidade
- o próximo ganho forte passa a ser:
  - modelar ALB/NLB/API Gateway -> backend com mais detalhe
  - depois promover isso para AWS real

## Ameacas a validade

- a hipótese no plano ainda é estrutural e pré-execução
- o benchmark continua sintético
- o bloco ainda nao resolve reachability real de rede em AWS

## Conclusao

H1 confirmada.

H2 confirmada.

H3 confirmada.

O passo 4 do `Bloco 1 — External Entry Reachability Real` foi concluido no
nivel sintético e de integração interna do produto.

## Proximos passos

1. modelar ALB/NLB/API Gateway -> backend com mais rigor
2. preparar promoção seletiva para AWS real com evidência de rede
3. usar essa semântica em validação real de `external entry`
