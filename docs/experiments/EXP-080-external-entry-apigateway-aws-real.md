# EXP-080 - External Entry API Gateway AWS Real

- ID: EXP-080
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-04
- Status: concluida

## Contexto

Depois de fechar `external entry` real em:
- EC2 publica direta
- ALB publico com backend privado

o proximo passo e validar uma terceira superficie publica:

- `API Gateway publico -> integration -> ALB -> target group -> backend EC2 -> role -> data`

## Hipoteses

- H1: o executor real consegue coletar evidência suficiente de:
  - `API Gateway -> integration`
  - `integration -> ALB`
  - `ALB -> target group -> backend`
- H2: o report final consegue sustentar `public_exploit_path_proved_end_to_end`
  sem depender de backend diretamente publico.
- H3: a mesma semantica de surrogate credential acquisition continua suficiente
  para manter a chain auditável.

## Desenho experimental

- Variavel independente:
  - lab AWS real efemero em `terraform_local_lab/external_entry_apigw_real/`
- Criterio:
  - `objective_met = true`
  - evidência real de:
    - `apigateway:GetStages`
    - `apigateway:GetIntegration`
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
  - `API Gateway publico`
  - `integration HTTP_PROXY`
  - `ALB internet-facing`
  - `target group healthy`
  - `backend EC2`
  - `surrogate credential acquisition`
  - `s3:GetObject`

Artefatos:
- `outputs_real_exp80_external_entry_apigw_openai/report.json`
- `outputs_real_exp80_external_entry_apigw_openai/report.md`

Evidência real observada no pivô:
- `apigateway:GET`
- `apigateway:GetStages`
- `apigateway:GetIntegration`
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

O produto agora sustenta `external entry` real em tres familias distintas:
- EC2 publica direta
- ALB publico com backend privado
- API Gateway publico com integration ate ALB e backend privado

## Interpretacao

Esse experimento reduz um gap conceitual importante:
- `external entry` deixou de depender de superficie publica direta ou de uma
  unica familia de edge service
- a mesma semantica de maturidade agora cobre edge API mais comum em AWS

## Implicacoes arquiteturais

- a semantica de reachability real de `external entry` ja consegue representar:
  - `stage publico`
  - `integration ativa`
  - `integration -> ALB`
  - `ALB -> target group -> backend healthy`
- isso fortalece o bloco de maturidade sem depender de naming favoravel

## Ameacas a validade

- o lab usa `HTTP_PROXY` simples
- ainda nao cobre:
  - autorizadores
  - integracoes privadas via VPC Link
  - regras mais complexas de API Gateway
  - NLB

## Conclusao

EXP-080 concluiu a proxima familia real de `external entry`.

O que ficou provado:
- `API Gateway publico -> integration -> ALB -> backend EC2 -> role -> data`
  funciona em AWS real
- o report consegue sustentar `public_exploit_path_proved_end_to_end`
  com evidencia de rede e de cadeia credenciada

## Proximos experimentos

- NLB real com backend privado
- API Gateway com integracoes mais complexas
- observacao real de rules e semantics mais ricas de edge routing

## Proximos experimentos

- NLB real com backend privado
- API Gateway com integracoes mais complexas
