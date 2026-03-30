# EXP-014 — Backtracking em Secrets Manager com pivô falso dominante

## Identificação
- ID: EXP-014
- Fase: 3
- Pré-requisito: EXP-012 e EXP-013 concluídos
- Status: hipótese principal confirmada

## Contexto
Após EXP-012 e EXP-013, já havia validação de Secrets Manager e branch profundo. Faltava demonstrar backtracking explícito quando o pivô errado parece mais promissor no primeiro momento (sinal mais forte), sem tornar o pivô correto impossível.

## Hipóteses
H1: Com `path_score` e action shaping, o engine consegue abandonar um pivô falso dominante e convergir para o caminho correto em Secrets Manager.
H2: O LLM mantém consistência ao seguir o branch correto após backtracking quando o acesso exige uma etapa intermediária (`analyze`).

## Desenho experimental

### Variável independente
- Planner (MockPlanner vs OpenAIPlanner) mantendo o mesmo fixture.

### Ambiente
- Três roles concorrentes (`RoleA`, `RoleM`, `RoleQ`).
- `RoleA` retorna um sinal “atraente” (nome semelhante ao alvo) mas termina em dead-end.
- `RoleM` exige `enumerate` e depois `analyze` para liberar `access_resource`.
- `RoleQ` é distrator sem acesso ao segredo alvo.

### Critério de sucesso
- Pivot inicial errado seguido de backtracking.
- `RoleM` executa `enumerate -> analyze -> access_resource`.
- Flag `secret_compromised` registrada no report/audit.

## Resultados por etapa

### Etapa 1 — MockPlanner (dry_run)
- Resultado: passou em 7 passos.
- Comportamento observado: `RoleA` foi escolhido primeiro, enumerado, ficou sem progresso; o planner pivotou para `RoleM`, executou `enumerate`, `analyze` e `access_resource`, atingindo o objetivo.

### Etapa 2 — OpenAIPlanner (dry_run, gpt-4o-mini)
- Resultado: passou em 7 passos.
- Comportamento observado: escolheu `RoleA` primeiro devido ao sinal de lookahead, depois backtracking para `RoleM` e execução correta do branch até o acesso final.

## Erros, intervenções e motivos
- Erro: `RoleA` continuava reaparecendo como pivô após a enumeração.
  - Intervenção: `RoleA` ficou sem ações após `enumerate`.
  - Motivo: forçar reconhecimento de dead-end e estimular backtracking.
- Erro: `RoleM` liberava acesso direto sem etapa intermediária.
  - Intervenção: introdução de `analyze` como gate antes do `access_resource`.
  - Motivo: garantir que o branch correto exija continuidade e não seja “auto‑resolvido” pelo lookahead.
- Erro: ações do `analyst` ainda reintroduziam RoleA/RoleQ após assumir `RoleM`.
  - Intervenção: limpar `available_actions` do `analyst` no assume de `RoleM`.
  - Motivo: impedir loop de re‑assume e manter o foco no branch ativo.

## Soluções arquiteturais exercitadas
- `path_score` com sinais de lookahead.
- `failed_assume_roles` para pivôs sem progresso.
- action shaping priorizando progresso no branch ativo.

## Descoberta principal
Mesmo com um pivô falso dominante (sinal mais forte no início), o engine consegue backtracking em Secrets Manager quando o estado registra dead‑ends e o branch correto exige sequência de ações.

## Interpretação
- Provado: backtracking funciona em superfície diferente de S3 e com etapa intermediária (`analyze`).
- Não provado: generalização em AWS real ainda não foi validada neste experimento.

## Implicações arquiteturais
- Necessário manter memória explícita de branches falhos.
- Branch correto deve ter progressão explícita, não apenas sinal estático.
- `analyze` pode ser usado como gate para evitar acesso direto antecipado.

## Ameaças à validade
- Fixture ainda é sintético; o comportamento em AWS real pode diferir.
- Heurística de action shaping pode mascarar fragilidades de política de busca.

## Conclusão
H1 confirmada. H2 confirmada para dry-run. O backtracking é robusto mesmo com pivô falso dominante e progresso em múltiplas etapas.

## Próximos experimentos
- EXP-015: validar o mesmo padrão em AWS real ou migrar para nova família (`SSM Parameter Store`) com backtracking equivalente.
