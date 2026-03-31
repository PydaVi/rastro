# EXP-017 — Backtracking em SSM Parameter Store com pivôs competitivos

## Identificação
- ID: EXP-017
- Fase: 3
- Pré-requisito: EXP-016 concluído
- Status: hipótese principal confirmada

## Contexto
EXP-016 validou backtracking em Secrets Manager com dois pivôs competitivos. O próximo
passo era portar o padrão para uma nova superfície AWS (SSM Parameter Store) para
confirmar generalização do engine sem mudar a lógica de backtracking.

## Hipóteses
H1: O backtracking observado em Secrets Manager generaliza para SSM Parameter Store.
H2: O engine consegue abandonar dois pivôs competitivos e convergir para o caminho correto
    mesmo quando a superfície muda e exige `enumerate -> analyze -> access_resource`.

## Desenho experimental

### Variável independente
- Superfície alvo: Secrets Manager (EXP-016) → SSM Parameter Store (EXP-017).

### Ambiente
- Quatro roles concorrentes (`RoleA`, `RoleB`, `RoleM`, `RoleQ`).
- `RoleA` e `RoleB` exibem sinais competitivos (listar parametro alvo), mas não liberam acesso.
- `RoleM` exige `enumerate -> analyze -> access_resource` para chegar ao parametro.
- `RoleQ` é distrator.

### Critério de sucesso
- Pivot inicial errado com backtracking por dois pivôs.
- Execução de `RoleM` com `enumerate -> analyze -> access_resource`.
- Flag `parameter_compromised` registrada no report/audit.

## Resultados por etapa

### Etapa 1 — OpenAIPlanner (dry_run, gpt-4o-mini)
- Resultado: passou em 9 passos.
- Comportamento observado: `RoleA -> enumerate`, pivot para `RoleB -> enumerate`,
  depois convergência em `RoleM` com `enumerate -> analyze -> access_resource`.

### Etapa 2 — OpenAIPlanner (AWS real, gpt-4o-mini)
- Resultado: passou em 9 passos.
- Comportamento observado: `RoleA -> enumerate`, pivot para `RoleB -> enumerate`,
  depois convergência em `RoleM` com `enumerate -> analyze -> access_resource`.
- Evidência: `ssm:GetParameter` em `/prod/payroll/api_key` registrado no report/audit.

## Erros, intervenções e motivos
- Erro: ferramentas SSM inexistentes no Tool Registry impediam ações após `assume_role`.
  - Intervenção: adicionar `ssm_list_parameters` e `ssm_read_parameter` ao Tool Registry
    e ao executor real (com placeholders seguros), destravando o dry_run.
  - Motivo: garantir que a superfície SSM seja tratada como classe real de path.

## Soluções arquiteturais exercitadas
- `path_score` + lookahead para ranquear pivôs.
- `failed_assume_roles` + action shaping para forçar backtracking.
- camada de tools declarativas para nova superfície (SSM).

## Descoberta principal
O backtracking generaliza para SSM Parameter Store quando a superfície é instrumentada
com ferramentas declarativas equivalentes.

## Interpretação
- Provado: a política de backtracking funciona em SSM com dois pivôs competitivos.
- Provado: validação em AWS real no lab local.

## Implicações arquiteturais
- Novas superfícies exigem ferramentas declarativas mínimas para não bloquear o loop.
- A lógica de backtracking é independente da superfície desde que o toolchain exista.

## Ameaças à validade
- Validação real ainda depende de um lab controlado (não ambiente cliente).
- Sinais competitivos ainda são sintéticos.

## Conclusão
H1 confirmada. H2 confirmada em AWS real. O engine generaliza backtracking para SSM
quando a superfície é instrumentada com tools compatíveis.

## Próximos experimentos
- Avançar para novos perfis com pivôs competitivos (expansão multi-branch).
