# EXP-041 - Compute Pivot AWS Real

- ID: EXP-041
- Fase: Prioridade 3 - promocao AWS real do segundo nivel
- Data: 2026-04-03
- Status: concluida

## Contexto

Primeira promocao real do bloco de generalizacao ofensiva do `compute-pivot-app`.

Hipotese alvo:
- provar em AWS real um pivô `compute -> iam` sem depender ainda de `external entry`
- manter o lab efemero e barato: uma EC2 pequena com `instance profile`, sem ALB/NAT

## Hipoteses

- H1: o executor real consegue validar um pivô via `instance profile` usando somente APIs AWS de leitura.
- H2: o loop do engine trata esse pivô como `access_resource` suficiente para marcar `compute_identity_pivoted`.
- H3: o primeiro corte real pode provar a ligacao `compute surface -> instance profile -> role` sem nova logica especifica de planner.

## Desenho experimental

- Variavel independente:
  - lab AWS real efemero em `terraform_local_lab/compute_pivot_real/`
- Ambiente:
  - 1 EC2 `t3.micro`
  - 1 `instance profile`
  - 1 role `PayrollAppInstanceRole`
- Criterio:
  - `objective_met = true`
  - evidencia real de API para o pivô

## Resultado por etapa

### Etapa R1 - primeiro run real

Resultado:
- `objective_met = false`
- `iam_list_roles` funcionou
- `ec2_instance_profile_pivot` falhou repetidamente

Erro observado:
- `InvalidParameterValue` em `DescribeIamInstanceProfileAssociations`
- filtro usado: `iam-instance-profile.arn`

Artefatos:
- `outputs_real_exp41_compute_pivot_openai/report.md`
- `outputs_real_exp41_compute_pivot_openai/audit.jsonl`

### Etapa R2 - rerun apos correcao do executor

Resultado:
- `objective_met = true`
- `2` steps
- evidencia real registrada:
  - `iam:GetInstanceProfile`
  - `ec2:DescribeIamInstanceProfileAssociations`
- pivô provado:
  - `instance-profile/PayrollAppInstanceProfile`
  - `-> role/PayrollAppInstanceRole`

Lab real:
- 1 EC2 `t3.micro`
- 1 `instance profile`
- 1 IAM role de aplicacao
- ambiente destruido apos o run

## Erros, intervencoes e motivos

### Causa raiz

Falha de infraestrutura / executor real:
- o executor usou um filtro invalido na API `DescribeIamInstanceProfileAssociations`
- o problema nao foi do planner, nem da representacao de estado, nem do path scoring

### Intervencao aplicada

Correcao geral no executor AWS:
- `list_instance_profile_associations()` passou a paginar a API sem filtro invalido
- o filtro pelo `instance_profile_arn` agora e feito no cliente, sobre a resposta oficial

Valor da correcao:
- vale para qualquer cenário futuro que use `instance profile association`
- nao e remendo especifico deste lab

### Separacao de causas possiveis

- Infraestrutura:
  - sim, confirmada
  - a chamada real para EC2 estava errada
- Representacao de estado:
  - nao
  - o objetivo por `flag` ja estava correto
- Policy / action shaping:
  - nao
  - o loop apenas repetiu a unica acao restante depois do erro de executor
- Framing do planner:
  - nao
  - o planner escolheu a acao certa
- Limitacao genuina do modelo:
  - nao

## Descoberta principal

O primeiro corte real de `compute pivot` revelou um gap no executor AWS:
- a modelagem do pivô estava correta
- mas a implementacao real da evidência usou um filtro de API que a documentacao oficial nao suporta

## Interpretacao

Isso nao reduz o valor do experimento.

O experimento isolou algo importante:
- o produto ja consegue chegar até o pivô certo
- o que faltava era a traducao rigorosa desse pivô para chamadas AWS validas

## Implicacoes arquiteturais

- `compute pivot` real depende de um executor AWS mais preciso, nao de mais heuristica lexical
- a promocao real do segundo nivel continua alinhada a `mais generalizacao ofensiva`
- para pivôs compute/external entry, a qualidade da evidência de API passa a ser parte central do produto

## Ameacas a validade

- o lab real atual prova ligacao `instance profile -> role`, nao exploracao de metadata/SSRF
- isso e suficiente para este primeiro corte, mas nao fecha `external entry`

## Conclusao

EXP-041 confirmou a hipotese apos uma unica correcao geral de executor.

O Rastro agora possui uma validacao real de `IAM -> Compute -> IAM` com:
- evidencia auditavel
- lab efemero
- custo controlado
- sem depender de `external entry`

## Proximos experimentos

- promover `aws-external-entry-data` para AWS real em lab igualmente efemero
- manter a ordem de promocao definida no `PLAN.md`
