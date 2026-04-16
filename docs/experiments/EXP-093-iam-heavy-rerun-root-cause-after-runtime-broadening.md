# EXP-093 — IAM-heavy rerun root cause after runtime broadening

- ID: EXP-093
- Fase: Reestruturacao do nucleo para blind real IAM-heavy
- Data: 2026-04-04
- Status: concluido

## Contexto

Depois de endurecer `truthfulness`, distinctness e abrir um primeiro bundle
`aws-iam-heavy`, foi executado um novo assessment real contra o lab IAM-heavy.

A expectativa era aumentar coverage estrutural sem inflar `validated`.
O rerun melhorou a honestidade do output, mas continuou com coverage muito baixa.

## Hipoteses

1. Se o runtime e o portfolio IAM-heavy fossem o gargalo principal, o novo bundle
   deveria aumentar de forma perceptivel a quantidade de paths distintos.
2. Se o selection estivesse escolhendo bem, os plans gerados deveriam refletir o
   espaco ofensivo mais rico do lab.
3. Se o contrato de sucesso ainda estivesse frouxo, isso apareceria em findings
   erroneamente promovidos.

## Desenho experimental

Bundle:
- `aws-iam-heavy`

Target:
- `examples/target_aws_blind_real.json`

Authorization:
- `examples/authorization_aws_blind_real_iamheavy.json`

Criterio:
- medir `distinct_paths_total`
- medir coverage por classe
- inspecionar campanha por campanha onde o espaco ofensivo colapsou

## Resultados observados

### Assessment

- `campaigns_total = 168`
- `campaigns_passed = 123`
- `campaigns_objective_not_met = 45`

### Findings

- `source_campaign_findings_total = 123`
- `distinct_paths_total = 3`
- `principal_multiplicity_total = 123`
- `additional_principal_observations = 120`

Distribuicao final:
- `aws-iam-attach-role-policy-privesc = 1`
- `aws-iam-pass-role-privesc = 1`
- `aws-iam-s3 = 1`

### Selection e planning

Discovery viu:
- `105` recursos
- `46` roles
- `42` users

Target selection gerou `20` candidatos, mas o campaign plan final ficou com
apenas `4` plans:
- `aws-iam-role-chaining`
- `aws-iam-attach-role-policy-privesc`
- `aws-iam-pass-role-privesc`
- `aws-iam-s3`

Ou seja: o espaco ofensivo ja foi comprimido fortemente no planejamento.

### Inspecao dos reports

1. `aws-iam-role-chaining`
- campanhas falham com `objective_met = false`
- os steps observados sao repeticoes de `iam_simulate_target_access` contra a
  role alvo
- nao ha `assume_role` real nem probe coerente com o objetivo

2. `aws-iam-s3`
- campanhas saem com `objective_met = true`
- mas o report mostra apenas:
  - `iam_simulate_target_access`
  - `simulated_policy_result.decision = implicitDeny`
  - `proof = None`
- isso e classificacao errada de sucesso

3. `aws-iam-attach-role-policy-privesc` e `aws-iam-pass-role-privesc`
- aparecem corretamente como `observed`
- mas continuam sendo apenas opportunities por simulacao de policy

## Descoberta principal

A causa raiz e **mista**, mas o bloqueio dominante agora e estrutural:

### 1. Compression no plano antes da execucao

O sistema viu um ambiente rico, gerou alguns candidatos uteis, mas colapsou tudo
em apenas `4` plans. Isso significa que a diversidade ofensiva ja esta sendo
perdida antes do runtime.

### 2. Misalignment entre profile e action space

`aws-iam-role-chaining` foi planejado, mas o runtime executou repetidamente
`iam_simulate_target_access` contra a role alvo. Isso e um erro de contrato.

O plano pede uma classe de chain; o runtime entrega um probe de acesso.

### 3. Success contract ainda incorreto em S3 blind real

`aws-iam-s3` ainda fecha `objective_met = true` com simulacao de policy e sem
`proof`. Isso significa que a reestruturacao de `truthfulness` ainda nao fechou o
caso blind real em que o runtime usa `iam_simulate_target_access`.

### 4. Portfolio abriu, mas ainda nao virou coverage real

O bundle IAM-heavy novo foi util para expor duas classes adicionais. Mas isso nao
se converteu em mais distinct paths de impacto. O portfolio melhorou a
representacao, nao a cobertura real do lab.

## Interpretacao

O fracasso deixou de ser explicado por uma unica causa superficial.

Hoje a leitura correta e:
- discovery nao e o gargalo dominante
- selection ainda comprime demais o espaco ofensivo
- synthesis/runtime continuam mal alinhados para algumas classes
- o contrato de sucesso ainda esta errado em pelo menos um caminho cego real

## Implicacoes arquiteturais

1. Nao basta abrir mais classes IAM-heavy.
2. Nao basta rerodar com mais principals.
3. O proximo bloco tem que atacar especificamente:
   - `plan diversity`
   - `profile -> runtime contract`
   - `blind real success truthfulness`

## Ameacas a validade

- o rerun ainda depende do current bundle design; outra estrategia de planning
  poderia abrir paths diferentes
- `distinct_path_key` continua sendo uma aproximacao estrutural

## Conclusao

A causa raiz principal nao e `faltou mais profile`.

A causa raiz e:
- o sistema ainda comprime cedo demais a diversidade ofensiva do ambiente
- e ainda executa algumas classes com action space incoerente com o profile
- alem de manter pelo menos um caso grave de sucesso falso em blind real

## Proximos experimentos

1. corrigir `objective_met` falso em `aws-iam-s3` blind real com simulacao
2. investigar e corrigir por que `aws-iam-role-chaining` cai em
   `iam_simulate_target_access` em vez de `assume_role`
3. abrir um bloco de `plan diversity for IAM-heavy`, permitindo mais de um path
   ofensivo por classe antes do colapso em um unico plano
