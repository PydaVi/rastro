# EXP-013 — Branch Profundo em AWS Secrets Manager

## Identificacao
- ID: EXP-013
- Fase: 3
- Status: confirmado em `dry_run`

## Contexto
O `EXP-012` validou uma nova classe de recurso final fora de S3:
- AWS Secrets Manager

Mas o path ainda era curto:
- `assume_role -> enumerate -> read`

Faltava testar se a mesma arquitetura continuava funcionando quando o branch correto em `Secrets Manager` exigia mais de uma etapa de descoberta antes do acesso final.

## Hipotese
H1: o `lookahead-aware path scoring` continua priorizando corretamente o branch certo em `Secrets Manager` quando o caminho exige duas enumeracoes antes do `GetSecretValue`.

H2: o simulador continua consistente para branches multiestagio em `Secrets Manager`, sem repetir transicoes erradas no mesmo alvo.

## Desenho experimental

### Ambiente
Path AWS com tres roles assumiveis:
- `RoleA`: dead-end curto
- `RoleM`: dead-end curto
- `RoleQ`: branch correto profundo

Recurso final:
- `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll-api-key`

### Branches
- `RoleA`
  - `assume_role`
  - `secretsmanager_list_secrets` com `archive/`
  - revela `archive/payroll-history`
- `RoleM`
  - `assume_role`
  - `secretsmanager_list_secrets` com `reports/`
  - revela `reports/quarterly-summary`
- `RoleQ`
  - `assume_role`
  - `secretsmanager_list_secrets` com `prod/`
  - revela `prod/`
  - `secretsmanager_list_secrets` com `prod/payroll`
  - revela `prod/payroll-api-key`
  - `secretsmanager_read_secret`

### Criterio de sucesso
- escolher `RoleQ`
- executar duas etapas de descoberta em `Secrets Manager`
- acessar `prod/payroll-api-key`
- registrar sucesso no report

## Implementacao
Artefatos do benchmark:
- `fixtures/aws_secrets_deeper_branching_lab.json`
- `examples/objective_aws_secrets_deeper_branching.json`
- `examples/scope_aws_secrets_deeper_branching.json`
- `examples/scope_aws_secrets_deeper_branching_openai.json`

Teste offline adicionado:
- `tests/test_mvp.py::test_aws_secrets_deeper_branching_dry_run_end_to_end`

## Resultado com MockPlanner
O benchmark passou com `MockPlanner`.

Caminho observado:
1. `iam_list_roles`
2. `assume_role -> RoleQ`
3. `secretsmanager_list_secrets` com `prod/`
4. `secretsmanager_list_secrets` com `prod/payroll`
5. `secretsmanager_read_secret -> prod/payroll-api-key`

Resultado:
- `objective_met: True`
- `5` passos

## Resultado com OpenAIPlanner
O benchmark tambem passou com `OpenAIPlanner`.

Caminho observado:
1. `iam_list_roles`
2. `assume_role -> RoleQ`
3. `secretsmanager_list_secrets` com `prod/`
4. `secretsmanager_list_secrets` com `prod/payroll`
5. `secretsmanager_read_secret -> prod/payroll-api-key`

Resultado:
- `objective_met: True`
- `5` passos

Justificativas do planner no report:
- `RoleQ` foi escolhida por `best path score`
- a primeira enumeracao foi usada para descobrir o namespace `prod/`
- a segunda enumeracao foi usada para aproximar o alvo `prod/payroll-api-key`
- o acesso final foi executado somente apos descoberta suficiente

## Descoberta principal
O `lookahead-aware path scoring` generaliza nao apenas para uma nova superficie (`Secrets Manager`), mas tambem para um branch profundo nessa nova superficie.

O engine conseguiu:
- priorizar o pivot correto
- manter exploracao disciplinada do branch ativo
- completar duas etapas de descoberta antes do acesso final

## O que foi provado
- `Secrets Manager` suporta benchmark profundo de forma consistente
- o `lookahead` continua forte fora da familia S3
- a combinacao `path_score + action shaping + branch exploration` continua suficiente em um path mais profundo

## O que nao foi provado
- nao houve backtracking neste experimento
- nao houve validacao em AWS real
- o experimento nao mediu sensitivity a ordem das acoes nessa nova variante

## Implicacoes arquiteturais
- o eixo de generalizacao agora cobre:
  - superficie nova (`Secrets Manager`)
  - branch curto (`EXP-012`)
  - branch profundo (`EXP-013`)
- a estrategia de diversificar familias de path em `dry_run` antes do real continua se pagando
- o proximo ganho cientifico depende de testar:
  - order sensitivity em `Secrets Manager`
  - ou backtracking real/forcado em `Secrets Manager`

## Arquivos relevantes
- `fixtures/aws_secrets_deeper_branching_lab.json`
- `examples/objective_aws_secrets_deeper_branching.json`
- `examples/scope_aws_secrets_deeper_branching.json`
- `examples/scope_aws_secrets_deeper_branching_openai.json`
- `tests/test_mvp.py`

## Conclusao
H1 foi confirmada.

H2 tambem foi confirmada neste benchmark.

O `EXP-013` fecha a validacao de que o engine consegue navegar um branch profundo em `Secrets Manager` com duas etapas de descoberta antes do acesso final.
