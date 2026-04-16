# EXP-094 — Role-chaining runtime contract misalignment

- ID: EXP-094
- Fase: Reestruturacao do nucleo para blind real IAM-heavy
- Data: 2026-04-04
- Status: concluido

## Contexto

O rerun IAM-heavy mostrou que `aws-iam-role-chaining` era planejado, mas as
campaigns executavam `iam_simulate_target_access` contra a role alvo em vez de
`assume_role`.

Isso era um erro de contrato entre objective, action shaping e runtime.

## Hipoteses

1. `action_shaping` estava preferindo acesso direto ao target mesmo quando o modo
   de sucesso exigia `assume_role_proved`.
2. `_restore_objective_target_access_actions()` estava reintroduzindo probes de
   acesso direto ao target para classes em que o sucesso nao e por acesso.

## Desenho experimental

Variavel independente:
- restringir a preferencia/restauracao de acesso direto ao target apenas aos modos
  em que isso faz sentido (`access_proved` e compatibilidade com
  `target_observed`)

Ambiente:
- suite offline focada em shaping e restauracao de acoes

Criterio:
- `assume_role_proved` nao pode preferir nem restaurar
  `iam_simulate_target_access` ao target objetivo

## Resultados por etapa

1. `shape_available_actions()`
- deixou de preferir `ACCESS_RESOURCE` direto ao target quando o objective esta em
  `assume_role_proved`

2. `_restore_objective_target_access_actions()`
- deixou de restaurar probes de acesso direto ao target para classes cujo contrato
  de sucesso nao e baseado em acesso

3. Validacao offline
- `assume_role_proved` passou a manter `iam_simulate_assume_role` como acao
  coerente
- probes de acesso direto deixaram de ser restaurados nesse caso

## Descoberta principal

Parte da subcobertura do IAM-heavy vinha de um atalho global pensado para classes
baseadas em dado sendo aplicado tambem a classes de chain IAM.

## Interpretacao

Esse erro nao era cosmetico.
Era exatamente o tipo de desalinhamento `profile -> runtime` que faz o produto
parecer mais geral no plano do que na execucao real.

## Implicacoes arquiteturais

- otimizacoes globais de `objective target access` precisam respeitar o modo de
  sucesso da classe
- o runtime IAM-heavy nao pode herdar atalhos pensados para `data access`

## Ameacas a validade

- a validacao foi offline; ainda falta confirmar o efeito no rerun real seguinte

## Conclusao

O contrato de `role-chaining` ficou menos incoerente.
Isso nao resolve sozinho a coverage do lab, mas remove um desvio claro que fazia
campaigns de chain degenerarem em probes de acesso direto.

## Proximos experimentos

1. rerodar IAM-heavy apos essa correcao
2. medir se `aws-iam-role-chaining` volta a aparecer como path distinto util
3. continuar abrindo diversidade de plans antes do colapso precoce por classe
