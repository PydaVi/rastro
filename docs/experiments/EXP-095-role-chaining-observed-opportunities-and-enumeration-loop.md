# EXP-095 — Role-chaining observed opportunities and enumeration loop

- ID: EXP-095
- Fase: Reestruturacao do nucleo para blind real IAM-heavy
- Data: 2026-04-04
- Status: concluido

## Contexto

Depois do rerun2, `aws-iam-role-chaining` produziu `0` findings e varias
campaigns ficaram presas em `iam_list_roles` repetido. Isso mostrou dois erros
centrais:
- loop de enumeracao sem memoria quando o target da enumerate e `None`
- findings descartando campaigns `objective_not_met` mesmo quando havia
  evidencia observacional util

## Hipoteses

1. `attempted_enumerations` nao estava bloqueando repeticao quando `target=None`.
2. `role-chaining` observado por simulacao de `sts:AssumeRole` deveria continuar
   aparecendo como finding `observed`, mesmo sem fechar `objective_met`.

## Desenho experimental

Variavel independente:
- registrar enumerate nula como alvo sentinela `*`
- permitir findings a partir de campaigns `objective_not_met` com evidencia util
- impedir que assume role simulada eleve `finding_state` para `credentialed`

## Resultados por etapa

1. `StateManager`
- enumerate com `target=None` agora entra em memoria como `*`

2. `action_shaping`
- repeticoes de `iam_list_roles` passaram a ser filtradas tambem nesse caso
- `assume_role_proved` continua preferindo `ASSUME_ROLE` coerente

3. `assessment findings`
- campaigns `objective_not_met` com report util agora entram no processo de
  findings
- `role-chaining` simulado passa a aparecer como `observed/reachable`
- assume role simulada nao sobe mais `finding_state` para `credentialed`

## Descoberta principal

O produto estava descartando exatamente o tipo de evidencia honesta que precisava
mostrar no IAM-heavy: oportunidades observadas ainda nao provadas.

Ao mesmo tempo, um detalhe de memoria da enumerate estava permitindo loops que
empobreciam ainda mais a exploracao.

## Interpretacao

Esse bloco nao faz o produto resolver o lab.
Mas corrige dois erros de medicao importantes:
- parar de girar em enumerate inutil
- parar de esconder findings observacionais reais em campaigns nao concluídas

## Implicacoes arquiteturais

- em modo blind real, `objective_not_met` nao pode significar automaticamente
  `nenhuma descoberta util`
- o sistema precisa separar melhor:
  - campanha nao concluida
  - oportunidade observada
  - path provado

## Ameacas a validade

- ainda falta rerun real apos esta correcao
- findings observacionais continuam dependentes da qualidade do runtime e do
  contrato de distinctness

## Conclusao

A engine ficou menos cega para oportunidades IAM observadas e menos propensa a
loop de enumeracao trivial.

## Proximos experimentos

1. rerodar o bundle `aws-iam-heavy`
2. verificar se `aws-iam-role-chaining` volta a aparecer como finding observado
3. medir se a diversidade de paths distintos sobe ou continua comprimida
