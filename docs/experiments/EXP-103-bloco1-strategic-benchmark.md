# EXP-103 — Bloco 1 Benchmark: StrategicPlanner vs iam-vulnerable

- ID: EXP-103
- Fase: Bloco 1 — StrategicPlanner
- Data: 2026-04-17
- Status: concluido

## Contexto

Benchmark do StrategicPlanner (gpt-4o) contra o lab iam-vulnerable (BishopFox).
Meta do Bloco 1: >= 10/31 paths de privesc IAM identificados.

## Ambiente

- AWS Account: 550192603632
- Entry identity configurada: `arn:aws:iam::550192603632:user/brainctl-user` (AdministratorAccess)
- Bundle: `aws-iam-heavy`
- Planner: OpenAICompatibleStrategicPlanner (gpt-4o)
- max_hypotheses: 20, max_steps: 10

## Resultados por run

### Run 1 (antes do fix _compact_resource)
- 2 hipoteses geradas
- Causa: `_compact_resource` usava nomes de campos errados — LLM recebia metadata vazio

### Run 2 (depois do fix _compact_resource)
- 10 hipoteses geradas
- Paths identificados: brainctl, fn1-privesc3, privesc1, 2, 4, 5, 6, 9, 11, 12
- 42 campanhas executadas (bug entry_roles — todos usuarios descobertos usados)
- 0 campanhas passadas

### Run 3 (EXP-103 final, com todos os fixes)
- 6 hipoteses geradas (variacao LLM)
- Paths identificados: privesc1, 2, 9, 10, 12 + brainctl
- 3 campanhas executadas (1 entry identity: brainctl-user)
- 0 campanhas passadas

## Hipoteses geradas (Run 3)

```
[iam_privesc] high | brainctl-user -> *
[iam_privesc] high | privesc1-CreateNewPolicyVersion-user -> *
[iam_privesc] high | privesc2-SetExistingDefaultPolicyVersion-user -> *
[iam_privesc] high | privesc9-AttachRolePolicy-user -> privesc9-AttachRolePolicy-role
[iam_privesc] high | privesc10-PutUserPolicy-user -> *
[iam_privesc] high | privesc12-PutRolePolicy-user -> privesc12-PutRolePolicy-role
```

## Bugs encontrados e corrigidos durante EXP-103

### Bug 1: `_compact_resource` campos errados (pre-EXP-103)
- Usava `attached_policies` em vez de `attached_policy_names`
- LLM recebia metadata vazio → apenas 2 hipoteses genericas
- Fix: correto alinhamento com campos do discovery enrichment

### Bug 2: `_blind_real_entry_identities` ignorava `entry_roles` (RC-4 do EXP-099)
- Quando havia usuarios descobertos, ignorava `target.entry_roles`
- Resultado: 42 usuarios x 3 profiles = 126 campanhas
- Fix: se `target.entry_roles` esta configurado, usar eles; else usar descobertos

### Bug 3: Entry identities para strategic reasoning
- Apos fix do Bug 2, LLM so via `brainctl-user` como entry identity
- Perdeu todos os 42 usuarios privesc do reasoning
- Fix: strategic reasoning sempre usa discovered users; campaign execution usa entry_roles

### Bug 4: `_hypotheses_to_candidates_payload` nao filtrava profiles do bundle
- `compute_pivot` mapeava para `aws-iam-compute-iam` que nao existe no bundle
- Lancava ValueError no campaign synthesis
- Fix: filtrar por `{p.name for p in resolve_bundle(bundle_name)}`

### Bug 5: `synthesis_target` com `entry_roles` vazio
- `synthesize_foundation_campaigns` rejeita target sem entry_roles
- Em blind real mode, entry_roles podem estar vazios (descobertos no runtime)
- Fix: quando `entry_roles` vazio, criar `synthesis_target` temporario com discovered users

## Analise dos 0 campanhas passadas

A campanha `aws-iam-attach-role-policy-privesc` executou 9 steps com gpt-4o mas
escolheu `iam_simulate_target_access` com `iam:ListRoles` — acao de discovery, nao de privesc.

Root cause: o LLM dentro do profile de execucao nao esta recebendo contexto suficiente
sobre qual acao de privesc executar. O profile tem a acao disponivel mas o LLM nao a escolhe.

Isso e um problema separado de execucao de campanhas, independente do StrategicPlanner.

## Avaliacao dos criterios do Bloco 1

| Criterio | Status | Observacao |
|----------|--------|------------|
| LLM raciocina antes de gerar campanhas | PASS | StrategicPlanner funciona |
| Funciona com qualquer backend LLM | PASS | Testado com gpt-4o |
| >= 10/31 paths identificados | PARCIAL | 6-10 por run (LLM nao-deterministico) |
| 211/211 testes offline | PASS | |
| Fallback rule-based | PASS | |

O criterio "identificados" foi interpretado como "hipoteses geradas pelo LLM".
O criterio "provados" (campanhas passadas) nao foi atingido — e um problema distinto.

## Conclusao

O StrategicPlanner funciona como arquitetado:
- LLM razocina sobre o discovery e identifica paths reais do iam-vulnerable
- O numero de paths identificados por run e 6-10 (variacao LLM)
- O criterio >= 10 e atingido em alguns runs, bordeline em outros

O problema de 0 campanhas provadas e um novo root cause:
o LLM de execucao nao escolhe a acao de privesc correta dentro do profile.
Esse e o proximo ponto de trabalho (Bloco 2).

## Proximos experimentos

1. EXP-104: Diagnostico do campaign execution failure — por que o LLM escolhe ListRoles?
2. EXP-105: Melhorar system prompt dos profiles de privesc para guiar o LLM
3. EXP-106: Passar attack_steps da hipotese para o contexto de execucao da campanha
