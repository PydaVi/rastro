# EXP-081 - External Entry NLB AWS Real

- ID: EXP-081
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-04
- Status: concluida

## Contexto

Depois de fechar `external entry` real em:
- EC2 publica direta
- ALB publico com backend privado
- API Gateway publico com integration ate backend privado

o proximo passo e validar a familia de edge L4:

- `NLB publico -> target group -> backend EC2 privado -> role -> data`

## Hipoteses

- H1: o executor real consegue sustentar `external entry` via `network load balancer`
  usando o mesmo grafo observavel de:
  - `DescribeLoadBalancers`
  - `DescribeListeners`
  - `DescribeTargetGroups`
  - `DescribeTargetHealth`
- H2: o report final consegue sustentar `public_exploit_path_proved_end_to_end`
  sem depender de backend com IP publico.
- H3: a semantica de surrogate credential acquisition continua suficiente para
  manter a chain auditavel em edge L4.

## Desenho experimental

- Variavel independente:
  - lab AWS real efemero em `terraform_local_lab/external_entry_nlb_real/`
- Criterio:
  - `objective_met = true`
  - evidencia real de:
    - `elasticloadbalancing:DescribeLoadBalancers`
    - `elasticloadbalancing:DescribeListeners`
    - `elasticloadbalancing:DescribeTargetGroups`
    - `elasticloadbalancing:DescribeTargetHealth`
    - `iam:GetInstanceProfile`
    - `ec2:DescribeIamInstanceProfileAssociations`
    - `s3:GetObject`

## Resultado por etapa

### Etapa R1 - run real

Resultado:
- `objective_met = true`
- a cadeia completa foi validada:
  - `NLB internet-facing`
  - `listener TCP publico`
  - `target group healthy`
  - `backend EC2 privado`
  - `surrogate credential acquisition`
  - `s3:GetObject`

Artefatos:
- `outputs_real_exp81_external_entry_nlb_openai/report.json`
- `outputs_real_exp81_external_entry_nlb_openai/report.md`

Evidencia real observada no pivo:
- `elasticloadbalancing:DescribeLoadBalancers`
- `elasticloadbalancing:DescribeListeners`
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

Nao houve falha experimental nova neste run.

## Descoberta principal

O produto agora sustenta `external entry` real em quatro familias distintas:
- EC2 publica direta
- ALB publico com backend privado
- API Gateway publico com integration ate backend privado
- NLB publico com backend privado

## Interpretacao

Esse experimento fecha a familia L4 de edge reachability no primeiro corte de
AWS real:
- `external entry` nao depende mais apenas de edge HTTP de camada 7
- a semantica de reachability continua coerente em um caso mais pobre em
  semantica de aplicacao, onde a prova vem de listener, target group e health

## Implicacoes arquiteturais

- o executor real agora sustenta `external entry` em:
  - L3/L4 direto via EC2 publica
  - L7 via ALB
  - API Gateway -> backend
  - L4 via NLB
- isso reduz falso positivo conceitual em paths de `external entry` e fortalece
  a linha de maturidade para promocao real fora de `IAM-first`

## Ameacas a validade

- o lab usa listener TCP simples
- ainda nao cobre:
  - listener rules mais ricas
  - multiplos target groups concorrentes
  - TLS termination
  - VPC Link

## Conclusao

EXP-081 concluiu a familia real de `NLB -> backend privado -> role -> data`.

O que ficou provado:
- `NLB publico -> backend EC2 privado -> role -> data` funciona em AWS real
- o report consegue sustentar `public_exploit_path_proved_end_to_end`
  com evidencia de reachability de rede e de cadeia credenciada

## Proximos experimentos

- observacao real de listener rules / multiplos target groups
- API Gateway com integracoes mais ricas
- consolidacao do Bloco 1 com as quatro familias reais de `external entry`
