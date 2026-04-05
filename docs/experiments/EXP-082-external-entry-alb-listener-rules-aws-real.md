# EXP-082 - External Entry ALB Listener Rules AWS Real

- ID: EXP-082
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-04
- Status: concluida

## Contexto

Depois de provar `external entry` real em:
- EC2 publica direta
- ALB publico com backend privado
- API Gateway publico com integration ate backend privado
- NLB publico com backend privado

faltava uma observacao real mais rica de edge routing:

- `ALB publico -> listener rules -> multiplos target groups -> backend correto -> role -> data`

## Hipoteses

- H1: o executor real consegue observar `listener rules` e `multiplos target groups`
  sem degradar a semantica de `external entry`.
- H2: o report consegue separar:
  - target groups observados
  - target group efetivamente casado pelo path
  - regra de listener efetivamente aplicada
- H3: a prova continua sustentando `public_exploit_path_proved_end_to_end`
  quando o workload correto depende de regra especifica, nao de default action.

## Desenho experimental

- Variavel independente:
  - lab AWS real efemero em `terraform_local_lab/external_entry_alb_rules_real/`
- Ambiente:
  - ALB publico
  - listener HTTP
  - default action -> target group decoy
  - regra `path-pattern=/payroll/*` -> target group correto
  - dois backends privados
- Criterio:
  - `objective_met = true`
  - evidencia real de:
    - `elasticloadbalancing:DescribeLoadBalancers`
    - `elasticloadbalancing:DescribeListeners`
    - `elasticloadbalancing:DescribeRules`
    - `elasticloadbalancing:DescribeTargetGroups`
    - `elasticloadbalancing:DescribeTargetHealth`
    - `s3:GetObject`

## Resultado por etapa

### Etapa R1 - run real

Resultado:
- `objective_met = true`
- a cadeia completa foi validada:
  - `ALB publico`
  - `listener HTTP`
  - `listener rule /payroll/*`
  - `target group correto healthy`
  - `backend EC2 privado`
  - `surrogate credential acquisition`
  - `s3:GetObject`

Artefatos:
- `outputs_real_exp82_external_entry_alb_rules_openai/report.json`
- `outputs_real_exp82_external_entry_alb_rules_openai/report.md`

Evidencia nova observada no report:
- `multiple_target_groups_observed = true`
- `matched_listener_rule_arns`
- `matched_listener_rule_priorities = ["10"]`
- `request_path = "/payroll/export.csv"`
- `matched_target_groups` apontando apenas para o target group correto

APIs reais observadas:
- `elasticloadbalancing:DescribeLoadBalancers`
- `elasticloadbalancing:DescribeListeners`
- `elasticloadbalancing:DescribeRules`
- `elasticloadbalancing:DescribeTargetGroups`
- `elasticloadbalancing:DescribeTargetHealth`
- `ec2:DescribeRouteTables`
- `ec2:DescribeSubnets`
- `ec2:DescribeSecurityGroups`
- `ec2:DescribeInternetGateways`
- `iam:GetInstanceProfile`
- `ec2:DescribeIamInstanceProfileAssociations`
- `sts:AssumeRole`
- `sts:GetCallerIdentity`
- `s3:GetObject`

Maturidade final:
- `public_exploit_path_proved_end_to_end`

## Erros, intervencoes e motivos

Nao houve falha experimental nova no run real.

Durante a implementacao offline, um teste revelou um bug de representacao:
- o parametro `target_group_arn` era sombreado por uma variavel local durante a
  agregacao de health
- isso fazia `matched_target_groups = []` mesmo quando a regra correta estava
  observada

A correcao foi geral no executor:
- preservacao do `target_group_arn` parametrico
- matching explicito de regras por `request_path`
- inclusao de `DescribeRules` no grafo de evidencia

## Descoberta principal

`External entry` agora nao depende apenas de:
- listener default
- unico target group

O produto consegue distinguir, em AWS real:
- edge publico observado
- pluralidade de backends observados
- backend correto selecionado por regra de listener

## Interpretacao

Esse experimento reduz um gap conceitual importante:
- o produto deixa de tratar `ALB -> backend` como uma ligacao unica e trivial
- passa a representar um caso mais proximo de edge routing real, com
  competencia entre target groups

## Implicacoes arquiteturais

- `external entry` com ALB agora sustenta:
  - `listener rules`
  - `multiple target groups`
  - `matched target group`
- isso fortalece o `Bloco 1` sem mudar a regra de linguagem:
  a classificacao forte so aparece quando a cadeia completa esta observada

## Ameacas a validade

- o matching usa `path-pattern` simples
- ainda nao cobre:
  - host-based routing
  - weighted forward
  - multiplas regras concorrentes com mesma expressividade
  - auth/WAF no edge

## Conclusao

EXP-082 concluiu a observacao real mais rica de `ALB listener rules`.

O que ficou provado:
- `ALB publico -> listener rule -> target group correto -> backend privado -> role -> data`
  funciona em AWS real
- o report agora consegue mostrar competicao entre target groups sem perder
  rigor na classificacao de `external entry`

## Proximos experimentos

- API Gateway com integracoes e roteamento mais ricos
- host-based routing e multiplas regras concorrentes
- consolidacao do `Bloco 1` com as familias reais e os niveis de edge routing
