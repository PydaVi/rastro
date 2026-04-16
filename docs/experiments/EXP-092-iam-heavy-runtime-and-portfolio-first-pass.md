# EXP-092 — IAM-heavy runtime and portfolio first pass

- ID: EXP-092
- Fase: Reestruturacao do nucleo para blind real IAM-heavy
- Data: 2026-04-04
- Status: concluido

## Contexto

Depois de endurecer `truthfulness` e as metricas de `distinct path`, o proximo
bloqueio do lab IAM-heavy continuava claro: o runtime e o portfolio ofensivo
permaneciam estreitos demais para privilege escalation IAM.

O produto ainda concentrava a maior parte da cobertura em:
- `aws-iam-role-chaining`
- `aws-iam-s3`
- acesso final a dado

Isso era insuficiente para um ambiente dominado por abuse IAM.

## Hipoteses

1. O runtime blind real precisa expor probes IAM intermediarios dedicados, nao
   apenas `AssumeRole` e acesso ao target final.
2. O portfolio precisa separar classes IAM-heavy diferentes, em vez de empurrar
   tudo para `aws-iam-role-chaining`.
3. Essas classes novas nao devem inflar `validated`; devem produzir findings
   observados com evidencia explicita de simulacao de policy.

## Desenho experimental

Variavel independente:
- abertura de classes IAM-heavy dedicadas no selection, synthesis e blind runtime

Classes abertas:
- `aws-iam-create-policy-version-privesc`
- `aws-iam-attach-role-policy-privesc`
- `aws-iam-pass-role-privesc`

Criterio:
- o bundle IAM-heavy deve gerar candidatos dedicados para roles com sinais
  estruturais compativeis
- o blind runtime deve limitar o probe ao tool coerente com a classe
- findings dessas classes devem permanecer `observed`, nao `validated`

## Resultados por etapa

1. Portfolio
- novo bundle: `aws-iam-heavy`
- novas classes IAM dedicadas foram registradas no catalogo real

2. Target selection
- roles com sinais estruturais de:
  - `createpolicyversion`
  - `attachrolepolicy` / `putrolepolicy`
  - `passrole` / `codebuild` / `cloudformation`
  passaram a gerar candidatos dedicados

3. Campaign synthesis
- novas classes geram `success_criteria.mode = policy_probe_proved`
- o contrato exige o `required_tool` coerente com a classe

4. Blind real runtime
- o runtime agora restringe o action space IAM-heavy ao probe correto por classe,
  em vez de jogar todos os probes de policy em todos os planos

5. Findings
- as novas classes produzem achados `observed`
- a evidencia e apresentada como oportunidade observada por simulacao de policy,
  nao como impacto validado

## Erros, intervencoes e motivos

- Foi necessario corrigir a inferencia de profiles para roles IAM-heavy, que
  inicialmente continuava retornando apenas `aws-iam-role-chaining`.
- Foi necessario impedir que probes IAM fossem classificados como `exploited`
  apenas porque usam `access_resource` contra uma role.

## Descoberta principal

O portfolio podia ser alargado sem reintroduzir overclaim.

O produto agora consegue representar melhor algumas oportunidades IAM-heavy sem
precisar chamar isso de exploracao validada.

## Interpretacao

Este experimento melhora a utilidade do reteste manual IAM-heavy.
Ainda nao prova cobertura satisfatoria do lab.
Ainda nao prova distinctness semantico de path.

Mas corrige um problema real: antes, boa parte do espaco IAM-heavy nem virava
classe ofensiva propria.

## Implicacoes arquiteturais

- IAM-heavy precisa continuar abrindo classes por capacidade ofensiva estrutural,
  nao por naming ou bundles cosmeticos.
- `policy_probe_proved` e um contrato intermediario util para observacao honesta,
  mas nao substitui prova de impacto.
- o proximo passo natural e rerodar o ambiente IAM-heavy com esse bundle novo e
  medir distinct paths por classe.

## Ameacas a validade

- a validacao foi offline; ainda falta o rerun real do lab
- as classes abertas sao apenas um primeiro corte e nao cobrem todo o espaco de
  privesc IAM do ambiente
- o runtime ainda nao executa abuso mutavel real com cleanup seguro; ele ainda
  depende de probes observacionais para essas classes

## Conclusao

O runtime e o portfolio IAM-heavy ficaram menos estreitos.
Isso nao resolve o fracasso do lab, mas reduz um gargalo real que antes tornava a
subcobertura inevitavel.

## Proximos experimentos

1. rerodar o bundle `aws-iam-heavy` no ambiente IAM-heavy simples
2. medir coverage por classe e por distinct path
3. decidir quais classes IAM-heavy exigem execucao mutavel real e cleanup
   dedicado
