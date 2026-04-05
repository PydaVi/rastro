# EXP-042 - External Entry AWS Real

- ID: EXP-042
- Fase: Prioridade 3 - promocao AWS real do segundo nivel
- Data: 2026-04-03
- Status: concluida

## Contexto

Segunda promocao real do bloco de generalizacao ofensiva.

Objetivo:
- sair de `compute -> iam` puro
- provar uma cadeia completa:
  - superficie publica de compute
  - pivô para role anexada
  - leitura real de dado sensível em S3

Lab efemero:
- 1 EC2 `t3.micro` com IP publico
- IMDS com `HttpTokens=optional`
- 1 `instance profile`
- 1 role `PublicPayrollAppRole`
- 1 bucket S3 com objeto sensível

## Hipoteses

- H1: o executor real consegue provar um entrypoint publico via compute.
- H2: depois do pivô, o engine progride para a role ativada e acessa o dado final.
- H3: essa cadeia pode ser validada com o mesmo loop central, sem path pré-roteirizado fora do discovery/fixture.

## Desenho experimental

- Variavel independente:
  - lab AWS real efemero em `terraform_local_lab/external_entry_real/`
- Criterio:
  - `objective_met = true`
  - evidência real de:
    - `ec2:DescribeInstances`
    - `iam:GetInstanceProfile`
    - `ec2:DescribeIamInstanceProfileAssociations`
    - `s3:GetObject`

## Resultado por etapa

### Etapa R1 - primeiro run real

Resultado:
- `objective_met = false`
- o pivô publico foi validado com sucesso
- o engine repetiu o pivô e nunca avançou para `s3_read_sensitive`

Artefatos:
- `outputs_real_exp42_external_entry_openai/report.md`
- `outputs_real_exp42_external_entry_openai/audit.jsonl`

### Etapa R2 - rerun apos correcao geral inicial

Resultado:
- `objective_met = true`
- cadeia completa validada em `3` steps
- o engine:
  - enumerou roles
  - pivotou da superficie publica para `PublicPayrollAppRole`
  - executou `s3:GetObject` no objeto sensível

Artefatos:
- `outputs_real_exp42_external_entry_openai/report.md`
- `outputs_real_exp42_external_entry_openai/audit.jsonl`

### Etapa R3 - rerun com surrogate credential acquisition controlado

Resultado:
- `objective_met = true`
- a cadeia completa foi revalidada com semântica de credenciais explícita
- o pivô agora inclui:
  - `sts:AssumeRole` controlado para a role alcançada por compute
  - `sts:GetCallerIdentity` para provar a identidade credenciada

Artefatos:
- `outputs_real_exp42_external_entry_openai/report.md`
- `outputs_real_exp42_external_entry_openai/audit.jsonl`

Observação importante:
- a validação final usa `credential_acquisition.mode = assume_role_surrogate`
- isso não simula extração literal de credenciais do host
- mas torna explícita e auditável a aquisição controlada de credenciais para continuar a chain sem fallback silencioso

### Etapa R4 - rerun com evidência explícita de reachability de rede

Resultado:
- `objective_met = true`
- a cadeia completa foi revalidada com evidência explícita de rede AWS no pivô
- o step `ec2_instance_profile_pivot` passou a registrar:
  - `ec2:DescribeRouteTables`
  - `ec2:DescribeSubnets`
  - `ec2:DescribeSecurityGroups`
  - `ec2:DescribeInternetGateways`
- o report final passou a classificar o caso como:
  - `public_exploit_path_proved_end_to_end`

Artefatos:
- `outputs_real_exp42_external_entry_openai/report.md`
- `outputs_real_exp42_external_entry_openai/report.json`
- `outputs_real_exp42_external_entry_openai/audit.jsonl`

Evidência adicional observada:
- `network_reachable_from_internet = proved`
- `backend_reachable = proved`
- `credential_acquisition_possible = proved`
- `data_path_exploitable = proved`
- `network_path` com:
  - `internet_gateway_ids`
  - `route_table_ids`
  - `route_to_internet_gateway = true`
  - `security_group_public_ingress = true`
  - `public_ip`

## Erros, intervencoes e motivos

### Causa raiz

Falha combinada de policy e representação de estado:

1. `ToolRegistry` exigia `audit_role_assumed` para ações de S3/Secrets/SSM
2. pivôs via `ec2_instance_profile_pivot` não satisfaziam essa semântica
3. o engine tinha validado o pivô, mas os próximos passos eram filtrados

Isso revelou um viés arquitetural:
- os tool preconditions ainda estavam presos a `assume_role`
- não a uma noção mais geral de `privileged identity active`

### Separacao de causas possiveis

- Infraestrutura:
  - nao
  - o lab e o executor real do pivô funcionaram
- Representacao de estado:
  - sim
  - a identidade alcançada por pivô precisava ser tratada como branch ativa
- Policy:
  - sim
  - os preconditions dos tools de acesso a dado eram estreitos demais
- Framing do planner:
  - nao
  - o planner escolheu o pivô correto
- Limitacao genuina do modelo:
  - nao

## Descoberta principal

`external entry` expôs um gap mais geral do produto:
- o engine já sabia chegar a identidades privilegiadas por caminhos não baseados em STS
- mas a camada de policy ainda estava modelada como se toda identidade privilegiada viesse de `assume_role`

## Interpretacao

Esse experimento foi valioso porque revelou drift de produto:
- o Rastro estava mais generalista no path engine
- mas ainda parcialmente acoplado a campaigns AWS IAM-first na camada de tools

## Implicacoes arquiteturais

- preconditions de tools de dados devem depender de `privileged_identity_active`
- não de `audit_role_assumed`
- pivôs via compute/external entry precisam ativar branch identities do mesmo jeito que `assume_role`
- `external entry` real precisa exportar evidência de rede suficiente para
  separar:
  - exposição estrutural
  - reachability real até workload
  - aquisição controlada de credenciais
  - exploração até o dado final

## Ameacas a validade

- este lab usa EC2 pública controlada como entrypoint
- não modela SSRF real nem exploração HTTP, apenas a relação estrutural `public compute -> attached role -> data`

## Conclusao

EXP-042 confirmou a hipótese sob a semântica endurecida do produto.

Resultado final:
- `objective_met = true`
- evidência real de:
  - `ec2:DescribeInstances`
  - `iam:GetInstanceProfile`
  - `ec2:DescribeIamInstanceProfileAssociations`
  - `ec2:DescribeRouteTables`
  - `ec2:DescribeSubnets`
  - `ec2:DescribeSecurityGroups`
  - `ec2:DescribeInternetGateways`
  - `sts:AssumeRole` controlado para a role alcançada
  - `sts:GetCallerIdentity`
  - `s3:GetObject`

O que ficou provado:
- `external entry -> compute -> attached role -> data` funciona em AWS real
- a continuidade da chain agora depende de credenciais explicitamente adquiridas
- o modo `assume_role_surrogate` é auditável e evita falso positivo por fallback de credenciais base
- neste lab de EC2 pública direta, a prova agora também inclui reachability de
  rede até o workload:
  - IP público
  - subnet / route table com rota para Internet Gateway
  - security group com ingresso público

## Proximos experimentos

- usar a mesma semântica endurecida para fechar `EXP-043`
- manter distinção explícita entre:
  - pivô estrutural
  - aquisição controlada de credenciais
