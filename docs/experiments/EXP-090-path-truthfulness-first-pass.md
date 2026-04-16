# EXP-090 — Path truthfulness first pass

- ID: EXP-090
- Fase: Reestruturacao do nucleo para verdade de path e distinctness
- Data: 2026-04-04
- Status: concluido

## Contexto

O reteste IAM-heavy revelou inflacao de findings por multiplicidade de principal,
uso excessivo de `target_observed` como criterio de sucesso e mistura entre
`campaign passed`, `validated` e `distinct path`.

Antes de qualquer novo reteste relevante, o produto precisava dar um primeiro
passo concreto para endurecer o contrato de verdade do nucleo.

## Hipoteses

1. `aws-iam-s3`, `aws-iam-secrets` e `aws-iam-ssm` nao devem continuar herdando
   `target_observed` como criterio principal de sucesso.
2. `aws-iam-role-chaining` precisa exigir prova real de `assume_role`, nao apenas
   observacao do target.
3. Findings agregados por principal inflacionam o resultado e escondem a unidade
   correta de verdade: `distinct path`.

## Desenho experimental

Variavel independente:
- endurecimento do contrato de sucesso gerado por synthesis
- endurecimento de `StateManager.is_objective_met()`
- agregacao de findings orientada a `distinct_path_key`

Ambiente:
- suite offline focada em synthesis, state e assessment findings

Criterio:
- `aws-iam-s3` gerar `access_proved`
- `aws-iam-role-chaining` gerar `assume_role_proved`
- sucesso nao contar quando a evidencia for apenas simulada
- campaigns com o mesmo path e principals diferentes colapsarem em um finding
  unico com `principal_multiplicity`

## Resultados por etapa

1. `campaign_synthesis`
- `aws-iam-s3`, `aws-iam-secrets` e `aws-iam-ssm` passaram a gerar
  `success_criteria.mode = access_proved`
- `aws-iam-role-chaining` passou a gerar
  `success_criteria.mode = assume_role_proved`
- classes restantes continuam em `target_observed` por compatibilidade

2. `StateManager`
- `access_proved` agora exige `access_resource` bem-sucedido no target
- evidencia marcada como `simulated` nao fecha o objetivo
- `assume_role_proved` agora exige `assume_role` bem-sucedido no target
- `iam_simulate_assume_role` nao fecha o objetivo

3. `assessment findings`
- agregacao passou a usar um fingerprint com `distinct_path_key`
- `entry_points` agora sao preservados como multiplicidade de principal do mesmo
  path, nao como findings separados
- markdown principal passou a expor:
  - `Finding state`
  - `Principal multiplicity`
  - `Entry points`
  - `Distinct path key`

## Erros, intervencoes e motivos

- Um teste existente assumia que um achado com `proof` em S3 teria estado final
  `exploited`; o estado correto e `validated_impact`.
- A expectativa foi corrigida para refletir o novo contrato.

## Descoberta principal

Foi possivel retirar parte do papel central de `target_observed` sem quebrar o
fluxo principal de synthesis e findings.

O produto ainda nao resolveu `truthfulness and path distinctness`, mas agora ja
consegue distinguir melhor:
- path provado
- path apenas observado
- mesmo path repetido por principals diferentes

## Interpretacao

Este experimento nao prova generalizacao ofensiva.
Ele prova algo mais basico e necessario: o produto ficou epistemicamente mais
honesto em uma parte central do nucleo.

O ganho e real, mas parcial:
- ainda existem classes que continuam em `target_observed`
- `distinct_path_key` ainda e uma heuristica sobre steps, nao uma semantica
  ofensiva completa
- a coverage IAM-heavy continua insuficiente

## Implicacoes arquiteturais

- `target_observed` pode e deve perder centralidade nas classes em que ja existe
  prova minima mais forte.
- multiplicidade de principal precisa continuar separada de `distinct path` em
  todas as metricas e outputs principais.
- o proximo trabalho deve continuar no mesmo eixo:
  - cobertura de estados por finding
  - distinctness mais semantico
  - depois runtime/portfolio IAM-heavy sob esse contrato

## Ameacas a validade

- O experimento foi offline; nao rerodou ainda o lab IAM-heavy.
- `distinct_path_key` ainda pode colapsar paths ofensivos diferentes que tenham
  a mesma sequencia superficial de steps.
- Parte relevante do portfolio continua em `target_observed`.

## Conclusao

Este foi um primeiro passo valido de `truthfulness and path distinctness`.
Nao resolve a falha principal do IAM-heavy, mas corrige um erro arquitetural
real: tratar observacao ou repeticao por principal como verdade ofensiva.

## Proximos experimentos

1. ampliar `finding_state` e distinctness para o output principal do reteste
   IAM-heavy
2. revisar coverage e metricas por path distinto e por classe ofensiva
3. so depois ampliar runtime/portfolio IAM-heavy e rerodar o lab
