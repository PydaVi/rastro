# EXP-012 — Branching em AWS Secrets Manager

## Identificacao
- ID: EXP-012
- Fase: 3
- Status: confirmado em `dry_run` e em AWS real

## Contexto
Os experimentos anteriores validaram escolhas de pivot, backtracking e `path scoring` principalmente em cenarios com S3 como recurso final.
A proxima pergunta arquitetural era se o engine generalizava para outra superficie AWS sem depender do padrao `assume_role -> s3_list_bucket -> s3_read_sensitive`.

O `EXP-012` foi desenhado para responder essa pergunta com um recurso final diferente:
- AWS Secrets Manager

## Hipotese
H1: o `path_score` com `lookahead` tambem prioriza corretamente o branch que leva a um secret sensivel no AWS Secrets Manager.

H2: a mesma arquitetura de estado, shaping e prompting usada para S3 generaliza para um novo tipo de recurso final sem exigir regra especifica de cenario.

## Desenho experimental

### Ambiente
Path AWS com tres roles assumiveis:
- `RoleA`: dead-end
- `RoleM`: branch correto
- `RoleQ`: dead-end

Recurso final:
- `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key`

### Branches
- `RoleA`
  - `assume_role`
  - `secretsmanager_list_secrets`
  - revela `archive/payroll-history`
- `RoleM`
  - `assume_role`
  - `secretsmanager_list_secrets`
  - revela `prod/payroll-api-key`
  - `secretsmanager_read_secret`
- `RoleQ`
  - `assume_role`
  - `secretsmanager_list_secrets`
  - revela `reports/quarterly-summary`

### Criterio de sucesso
- escolher `RoleM`
- enumerar o catalogo de secrets
- acessar o secret `prod/payroll-api-key`
- registrar sucesso no report e no audit

## Problema encontrado durante a implementacao
Antes da validacao com `OpenAIPlanner`, o baseline com `MockPlanner` revelou um problema de coerencia interna.

### Sintoma
O `action_shaping` ranqueava `RoleM` corretamente com maior `path_score`, mas o `MockPlanner` ainda selecionava outra role ao reordenar `assume_role` por nome do target.

### Causa
O `MockPlanner` nao estava respeitando `candidate_paths.path_score` ao decidir entre multiplas acoes `assume_role`.
Ele continuava deterministico, mas destoava da policy layer do engine.

### Correcao
Ajuste em `src/planner/mock_planner.py`:
- `assume_role` passou a considerar `candidate_paths.path_score`
- as regras anteriores de `failed` e `untested` foram preservadas

## Implementacao do experimento
Para suportar a nova superficie, foram adicionados artefatos declarativos novos:
- `tools/aws/secretsmanager_list_secrets.yaml`
- `tools/aws/secretsmanager_read_secret.yaml`

Tambem foram adicionados placeholders locais:
- `tools/aws/secretsmanager_list_secrets.py`
- `tools/aws/secretsmanager_read_secret.py`

Artefatos do benchmark `dry_run`:
- `fixtures/aws_secrets_branching_lab.json`
- `examples/objective_aws_secrets_branching.json`
- `examples/scope_aws_secrets_branching.json`
- `examples/scope_aws_secrets_branching_openai.json`

## Resultado em dry_run
O benchmark passou com `OpenAIPlanner`.

Caminho observado:
1. `iam_list_roles`
2. `assume_role -> RoleM`
3. `secretsmanager_list_secrets`
4. `secretsmanager_read_secret -> prod/payroll-api-key`

Resultado:
- `objective_met: True`
- `4` passos

O planner justificou a escolha de `RoleM` por:
- `high path score`
- `lookahead signals leading directly to the sensitive Secrets Manager secret`

## Extensao para AWS real
Como o `EXP-012` introduziu uma nova superficie relevante, ele foi escolhido como o proximo candidato para validacao real.

### Suporte real adicionado
Em `src/execution/aws_client.py`:
- `list_secrets(...)`
- `get_secret_value(...)`

Em `src/execution/aws_executor.py`:
- `secretsmanager_list_secrets`
- `secretsmanager_read_secret`

Foi adicionado teste offline do executor real com cliente fake:
- `tests/test_mvp.py::test_aws_real_executor_supports_secretsmanager_path`

### Lab real local
Foram preparados artefatos locais em `terraform_local_lab/rastro_local/` para o path real:
- `aws_secrets_branching_lab.local.json`
- `objective_aws_secrets_branching.local.json`
- `scope_aws_secrets_branching_openai.local.json`

Esses arquivos permaneceram fora do repositório, seguindo a regra local-only para Terraform.

## Resultado em AWS real
O path real passou com `OpenAIPlanner`.

Caminho observado:
1. `iam_list_roles`
2. `assume_role -> role correta`
3. `secretsmanager:ListSecrets`
4. `secretsmanager:GetSecretValue -> prod/payroll-api-key`

Resultado:
- `objective_met: True`
- `real_api_called: True`
- `4` passos

O audit registrou chamadas reais para:
- `sts:GetCallerIdentity`
- `iam:ListRoles`
- `sts:AssumeRole`
- `iam:SimulatePrincipalPolicy`
- `secretsmanager:ListSecrets`
- `secretsmanager:GetSecretValue`

## Descoberta principal
O engine generaliza para uma nova familia de recurso final em AWS.

A combinacao de:
- `candidate_paths`
- `path_score`
- `lookahead_signals`
- `action shaping`

continuou suficiente para priorizar o branch correto em `Secrets Manager`, tanto em `dry_run` quanto em AWS real.

## O que foi provado
- o engine nao esta acoplado apenas a S3
- `lookahead-aware path scoring` tambem funciona para `Secrets Manager`
- o executor real passou a suportar uma nova superficie AWS com sucesso
- a validacao real confirmou generalizacao minima fora da familia S3

## O que nao foi provado
- este experimento nao exigiu backtracking
- nao mediu branch profundo em `Secrets Manager`
- nao mediu order sensitivity severa nessa nova superficie

## Implicacoes arquiteturais
- a estrategia de diversificar classes de attack path antes de multiplicar labs reais se mostrou correta
- `Secrets Manager` vira uma nova superficie valida para a Fase 3
- o baseline deterministico tambem precisa acompanhar a evolucao da policy layer para nao gerar falsos sinais

## Arquivos relevantes
- `src/execution/aws_client.py`
- `src/execution/aws_executor.py`
- `src/planner/mock_planner.py`
- `fixtures/aws_secrets_branching_lab.json`
- `examples/objective_aws_secrets_branching.json`
- `examples/scope_aws_secrets_branching.json`
- `examples/scope_aws_secrets_branching_openai.json`
- `tools/aws/secretsmanager_list_secrets.yaml`
- `tools/aws/secretsmanager_read_secret.yaml`
- `tests/test_mvp.py`

## Conclusao
H1 foi confirmada.

H2 tambem foi confirmada.

O `EXP-012` e a primeira validacao completa de uma nova classe de attack path fora de S3, com sucesso tanto em `dry_run` quanto em AWS real.
