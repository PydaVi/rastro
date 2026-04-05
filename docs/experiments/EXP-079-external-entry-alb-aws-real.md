# EXP-079 - External Entry ALB AWS Real

- ID: EXP-079
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-04
- Status: concluida

## Contexto

Depois do `EXP-042`, o produto ja provava `external entry` real em EC2 publica
direta. O proximo passo e subir o rigor para uma superficie mais comum:

- `ALB publico -> target group -> backend EC2 -> attached role -> data`

O objetivo e reduzir a lacuna restante do `Bloco 1`:
- sair de reachability direto por IP publico
- para um caminho com superficie publica intermediada por load balancer

## Hipoteses

- H1: o executor real consegue coletar evidência suficiente de `ALB -> listener -> target group -> backend`.
- H2: o report final consegue sustentar `external entry` com maturidade superior a mera exposição estrutural.
- H3: o mesmo loop central continua suficiente para validar:
  - superfície pública
  - pivô credenciado controlado
  - acesso ao dado final

## Desenho experimental

- Variavel independente:
  - lab AWS real efemero em `terraform_local_lab/external_entry_alb_real/`
- Criterio:
  - `objective_met = true`
  - evidência real de:
    - `elasticloadbalancing:DescribeLoadBalancers`
    - `elasticloadbalancing:DescribeListeners`
    - `elasticloadbalancing:DescribeTargetGroups`
    - `elasticloadbalancing:DescribeTargetHealth`
    - `iam:GetInstanceProfile`
    - `ec2:DescribeIamInstanceProfileAssociations`
    - `s3:GetObject`

## Resultado por etapa

### Etapa R1 - primeiro run real

Resultado:
- `objective_met = true`
- a cadeia operacional foi validada:
  - ALB publico
  - target group saudavel
  - surrogate credential acquisition
  - `s3:GetObject`
- mas a maturidade final ficou subavaliada como:
  - `public_exposure_structurally_linked_to_privileged_path`

Artefatos:
- `outputs_real_exp79_external_entry_alb_openai/report.json`
- `outputs_real_exp79_external_entry_alb_openai/report.md`

### Etapa R2 - rerun apos correcao geral de agregacao

Resultado:
- `objective_met = true`
- a cadeia completa foi revalidada
- a maturidade final passou para:
  - `public_exploit_path_proved_end_to_end`

Artefatos:
- `outputs_real_exp79_external_entry_alb_openai/report.json`
- `outputs_real_exp79_external_entry_alb_openai/report.md`

Evidência real observada no pivô:
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

Evidência estrutural exportada:
- ALB `internet-facing`
- DNS público
- listener público na porta `80`
- forwarding para target group
- target backend `healthy`
- security group do backend restrito ao SG do ALB

## Erros, intervencoes e motivos

### Causa raiz

Falha de representacao de estado no executor real:

1. o pivô `ec2_instance_profile_pivot` passou a coletar evidência de ALB
2. mas a agregação final de:
   - `network_reachable_from_internet`
   - `backend_reachable`
   ainda exigia que a instância backend fosse diretamente pública
3. isso funciona para EC2 pública direta
4. mas falha para `ALB publico -> backend privado`

Separacao de causas possiveis:
- Infraestrutura:
  - nao
  - o lab subiu e o target group ficou `healthy`
- Representacao de estado:
  - sim
  - a semântica de reachability ainda estava enviesada para `public instance`
- Policy:
  - nao
- Framing do planner:
  - nao
- Limitacao genuina do modelo:
  - nao

## Descoberta principal

`external entry` via ALB expôs um viés residual do produto:
- a maturidade de reachability real já aceitava superficie publica direta
- mas ainda não representava corretamente superficie publica mediada por load balancer

## Interpretacao

O run foi valioso porque mostrou que:
- o executor já coleta a evidência certa
- o problema restante estava na regra de agregação da prova

## Implicacoes arquiteturais

- reachability real de `external entry` nao pode exigir backend com IP publico
- para `ALB/NLB`, a prova correta é:
  - load balancer internet-facing
  - listener publico
  - forwarding para target group
  - target backend saudavel

## Ameacas a validade

- o lab usa `ALB -> EC2` simples com listener default
- ainda nao cobre:
  - rules mais complexas
  - multiplos target groups
  - API Gateway
  - NLB

## Conclusao

EXP-079 fechou a proxima superficie real relevante de `external entry`.

O que ficou provado:
- `ALB publico -> target group saudavel -> backend EC2 -> attached role -> data`
  funciona em AWS real
- a agregacao de maturidade agora distingue corretamente:
  - backend privado atras de ALB publico
  - backend publico direto
- o produto conseguiu sustentar `public_exploit_path_proved_end_to_end`
  sem depender de IP publico no backend

## Proximos experimentos

- API Gateway real com integration ate backend
- observar:
  - listener rules
  - target health mais detalhado
  - integracao `API Gateway -> backend`

## Ameacas a validade

_Pendente._

## Conclusao

_Pendente._

## Proximos experimentos

- API Gateway real com integration ate backend
- comparacao entre:
  - `public exposure structurally linked to privileged path`
  - `public exploit path proved end-to-end`
