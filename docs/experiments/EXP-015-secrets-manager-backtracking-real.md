# EXP-015 — Backtracking em Secrets Manager (AWS real)

## Identificação
- ID: EXP-015
- Fase: 3
- Pré-requisito: EXP-014 concluído
- Status: hipótese principal confirmada após correção do executor real

## Contexto
EXP-014 validou o backtracking em Secrets Manager apenas em `dry_run`. Faltava provar que o mesmo padrão se mantém em AWS real, usando o gate `RASTRO_ENABLE_AWS_REAL=1` e um fixture local refletindo o ambiente provisionado via Terraform.

## Hipóteses
H1: O backtracking observado em `dry_run` generaliza para AWS real sem exigir mudanças no planner.
H2: A etapa intermediária `analyze` não bloqueia o caminho em AWS real quando tratada como no-op no executor.

## Desenho experimental

### Variável independente
- Modo de execução: `dry_run` (EXP-014) vs `real` (EXP-015), mantendo o mesmo padrão de fixture e planner.

### Ambiente
- Três roles concorrentes (`RoleA`, `RoleM`, `RoleQ`).
- `RoleA` fornece sinal inicial mais atrativo, mas leva a dead-end.
- `RoleM` exige `enumerate -> analyze -> access_resource`.
- `RoleQ` é distrator.
- Recurso final: Secrets Manager (`secretsmanager:GetSecretValue`).

### Critério de sucesso
- Escolha inicial do pivô errado, seguida de backtracking.
- Execução do branch correto com etapa `analyze` e acesso ao segredo.
- Flag `secret_compromised` registrada no report/audit.

## Resultados por etapa

### Etapa 1 — OpenAIPlanner (real, gpt-4o-mini)
- Resultado: passou em 7 passos.
- Comportamento observado: escolheu `RoleA`, enumerou segredos, pivotou para `RoleM`, executou `enumerate`, `analyze` (no-op real) e `access_resource`, atingindo o objetivo.

## Erros, intervenções e motivos
- Erro: `ActionType.ANALYZE` falhou em AWS real com `unsupported_aws_tool`.
  - Intervenção: adicionar suporte real a `ANALYZE` como no-op no executor AWS real (sem chamada de API, apenas transição do fixture).
  - Motivo: evitar bloqueio do path quando o branch correto exige etapa intermediária não mapeada a API real.

## Soluções arquiteturais exercitadas
- `failed_assume_roles` para registrar pivô sem progresso.
- action shaping priorizando branch ativo após pivot.
- `path_score` e sinais de lookahead para ranquear pivôs iniciais.

## Descoberta principal
O backtracking em Secrets Manager funciona em AWS real quando o executor trata `ANALYZE` como etapa sem API, preservando a sequência `enumerate -> analyze -> access_resource`.

## Interpretação
- Provado: a política de backtracking generaliza para AWS real em Secrets Manager.
- Provado: `ANALYZE` pode existir como etapa lógica sem dependência de API real.
- Não provado: generalização para novas superfícies AWS fora de Secrets Manager.

## Implicações arquiteturais
- Etapas lógicas do planner (ex.: `analyze`) precisam de suporte explícito no executor real, mesmo como no-op.
- Backtracking real exige coerência entre fixture e executor, não apenas no planner.

## Ameaças à validade
- Apenas um run real; variância do planner não foi amostrada.
- Fixture local ainda abstrai certas condições reais de política IAM.

## Conclusão
H1 confirmada. H2 confirmada após suporte a `ANALYZE` no executor real. O engine demonstrou backtracking em Secrets Manager em AWS real com pivô inicial incorreto.

## Próximos experimentos
- EXP-016: introduzir variação de backtracking dentro de Secrets Manager (novo pivot com sinal competitivo).
- EXP-017: migrar a mesma lógica para SSM Parameter Store e validar em AWS real.
