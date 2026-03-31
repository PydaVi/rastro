# EXP-016 — Backtracking em Secrets Manager com pivô competitivo adicional

## Identificação
- ID: EXP-016
- Fase: 3
- Pré-requisito: EXP-014 e EXP-015 concluídos
- Status: hipótese principal confirmada

## Contexto
EXP-014/015 validaram backtracking com um pivô falso dominante. Faltava testar um cenário
com dois pivôs competitivos plausíveis antes do pivô correto, aumentando a ambiguidade
sem mudar a superfície (Secrets Manager).

## Hipóteses
H1: Com `path_score` + action shaping, o engine consegue abandonar dois pivôs competitivos
    e convergir para o pivô correto em Secrets Manager.
H2: O backtracking mantém sequência correta quando o pivô válido exige `enumerate -> analyze -> access_resource`.

## Desenho experimental

### Variável independente
- Adição de um pivô competitivo extra (`RoleB`) mantendo o restante do cenário.

### Ambiente
- Quatro roles concorrentes (`RoleA`, `RoleB`, `RoleM`, `RoleQ`).
- `RoleA` e `RoleB` apresentam sinais competitivos (listagem com payroll), mas não liberam acesso.
- `RoleM` exige `enumerate -> analyze -> access_resource` para chegar ao segredo.
- `RoleQ` é distrator.

### Critério de sucesso
- Pivot inicial errado, seguido de backtracking por pelo menos dois pivôs.
- Execução de `RoleM` com `enumerate -> analyze -> access_resource`.
- Flag `secret_compromised` registrada no report/audit.

## Resultados por etapa

### Etapa 1 — OpenAIPlanner (dry_run, gpt-4o-mini)
- Resultado: passou em 9 passos.
- Comportamento observado: `RoleA -> enumerate` (sinal competitivo), pivot para `RoleB -> enumerate`
  (sinal competitivo), depois convergência em `RoleM` com `enumerate -> analyze -> access_resource`.

## Erros, intervenções e motivos
- Nenhuma intervenção adicional necessária. O cenário foi endurecido apenas pela inclusão de `RoleB`.

## Soluções arquiteturais exercitadas
- `path_score` com sinais de lookahead.
- `failed_assume_roles` e action shaping para priorizar progresso no branch ativo.
- backtracking explícito após pivôs competitivos sem avanço.

## Descoberta principal
O backtracking permanece robusto mesmo quando dois pivôs competitivos apresentam sinais fortes
antes do caminho correto.

## Interpretação
- Provado: backtracking suporta ambiguidade maior em Secrets Manager sem regressão.
- Não provado: generalização em AWS real com o pivô competitivo adicional (ainda não validado).

## Implicações arquiteturais
- Cenários com múltiplos sinais competitivos continuam resolvíveis com o estado atual do engine.
- A necessidade de etapas intermediárias (`analyze`) não interfere no backtracking correto.

## Ameaças à validade
- Apenas um run em dry_run; variância do planner não foi testada.
- Sinais competitivos ainda são sintéticos e podem não refletir política IAM real.

## Conclusão
H1 confirmada. H2 confirmada em dry_run. O engine mantém convergência mesmo com dois pivôs competitivos.

## Próximos experimentos
- EXP-017: portar o padrão para SSM Parameter Store e validar em AWS real se houver sinal novo.
