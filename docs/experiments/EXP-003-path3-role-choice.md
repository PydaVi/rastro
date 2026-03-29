# EXP-003 — Escolha de Pivô entre Roles Concorrentes em AWS Real

## Identificação
- ID: EXP-003
- Fase: 3
- Pré-requisito: EXP-001 e EXP-002 concluídos
- Status: hipótese principal refutada nas etapas 2–4 / confirmada na etapa 5

## Contexto
Os Paths 1 e 2 validaram:

- executor AWS real
- auditoria e sanitização
- uso de `MockPlanner` e `OllamaPlanner`
- caminhos simples e lineares em IAM, STS e S3

Eles deixaram em aberto um problema mais difícil: escolha entre pivôs concorrentes.

O Path 3 foi desenhado para elevar essa dificuldade:

- duas roles assumíveis
- apenas uma leva ao objetivo final
- uma role distratora parece válida, mas não fecha o path

Esse foi o primeiro experimento em que o planner precisou escolher entre pivôs concorrentes.

## Hipóteses
H1: se o planner já navega Paths 1 e 2, modelo local pequeno consegue escolher corretamente entre duas roles concorrentes.

H2: se o planner escolher errado, o engine atual consegue se recuperar.

## Desenho experimental

### Variável independente
- `MockPlanner`
- `OllamaPlanner` com `phi3:mini`
- `OpenAIPlanner` com `gpt-4o-mini` sem mecanismos adicionais
- `OpenAIPlanner` com `gpt-4o-mini` após memória mínima e guidance
- `OpenAIPlanner` com `gpt-4o-mini` após `action shaping`

### Ambiente
- AWS real autorizada
- duas roles assumíveis:
  - `AuditRole`
  - `BucketReaderRole`
- um bucket sensível
- um bucket distrator

### Critério de sucesso
- escolher a role correta
- explorar o branch correto
- enumerar o bucket correto
- acessar o objeto final
- registrar o path no report e no audit

## Resultados por etapa

### Etapa 1 — MockPlanner
O Path 3 real passou.

Isso provou:

- o ambiente estava correto
- o executor real estava correto
- o report e o attack graph estavam corretos
- existia um path real válido com roles concorrentes

### Etapa 2 — OllamaPlanner (`phi3:mini`)
O Path 3 real falhou.

Comportamento observado:

- escolheu a role errada (`BucketReaderRole`)
- reconheceu a role distratora no texto, mas ainda assim a selecionou
- não convergiu para o objetivo final

Causa isolada:

- falha de planejamento, não de infraestrutura

### Etapa 3 — OpenAIPlanner (`gpt-4o-mini`) sem mecanismos adicionais
O Path 3 real falhou.

Comportamento observado:

- não escolhia um pivô
- repetia `iam_list_roles`
- ficava preso em discovery

Causa isolada:

- framing do planner ainda favorecia enumeração excessiva mesmo quando o espaço de decisão já tinha informação suficiente para abrir um branch

### Etapa 4 — OpenAIPlanner com memória mínima e guidance
O Path 3 real ainda falhou.

O que melhorou:

- o planner saiu do loop de discovery
- passou a enumerar
- assumiu a role correta

O que ainda falhou:

- depois abriu a role distratora
- voltou a assumir roles repetidamente
- não explorava o branch ativo

### Etapa 5 — OpenAIPlanner com action shaping
O Path 3 real passou.

Comportamento observado:

1. `iam_list_roles`
2. `iam_passrole` para a role correta
3. `s3_list_bucket`
4. `s3_read_sensitive`

O que desbloqueou a convergência:

- uma camada geral de `action shaping`
- policy layer suficiente para organizar o espaço de ações antes da decisão do LLM

## Erros, intervenções e motivos

### Erro 1 — role errada sem recuperação útil
Sintoma:

- o `OllamaPlanner` escolheu `BucketReaderRole`
- depois o engine não oferecia um caminho de recuperação suficiente
- o run podia ficar preso em repetição de enumeração

Intervenção:

- preservar ações de recuperação no fixture do Path 3
- manter assumíveis alternativas mesmo após um pivô errado

Motivo:

- um agente que não pode errar e tentar de novo não tem como demonstrar aprendizado operacional

### Erro 2 — sanitização colapsando roles distintas
Sintoma:

- `AuditRole` e `BucketReaderRole` podiam aparecer como o mesmo `<REDACTED_ROLE>`
- isso enfraquecia a leitura do experimento

Intervenção:

- sanitização com aliases estáveis e distintos por role

Motivo:

- sem observabilidade correta, a leitura do branch escolhido versus branch rejeitado fica ambígua

### Erro 3 — memória zero de hipóteses
Sintoma:

- o planner tratava cada passo quase isoladamente
- não havia noção explícita de pivôs testados e pivôs falhos

Intervenção:

- adicionar ao estado:
  - `tested_assume_roles`
  - `failed_assume_roles`

Motivo:

- o primeiro passo para sair de agente reativo e registrar tentativas

### Erro 4 — discovery loop
Sintoma:

- o `OpenAIPlanner` repetia `iam_list_roles`
- mesmo depois de já conhecer as roles candidatas

Intervenção:

- reforçar o prompt com:
  - `enumeration_sufficient`
  - `should_commit_to_pivot`
  - `candidate_roles`
  - `failed_assume_roles`

Motivo:

- discovery não pode dominar o run quando já existem hipóteses suficientes para pivotar

### Erro 5 — troca de pivô sem explorar branch ativo
Sintoma:

- o planner assumia a role correta
- depois abria a role distratora
- voltava a assumir roles
- não chegava em `s3_list_bucket`

Intervenção:

- expor no estado:
  - `active_assumed_roles`
  - `active_branch_action_count`
- reforçar o prompt com `should_explore_current_branch`

Motivo:

- era preciso ensinar o planner a reconhecer que um branch promissor já estava aberto

### Erro 6 — prompt-only ainda insuficiente
Sintoma:

- mesmo com guidance melhor, o planner ainda podia trocar de pivô em vez de descer a árvore

Intervenção:

- introduzir uma camada geral de `action shaping`
- quando existe branch ativo com progresso possível:
  - priorizar ações desse branch
  - adiar a abertura de pivôs concorrentes naquela rodada

Motivo:

- o problema já não era apenas de linguagem; era de organização do espaço de busca
- isso continua sendo uma capacidade geral do engine, não um script do Path 3

### Erro 7 — bug de sanitização durante a iteração
Sintoma:

- `IndexError` em `src/core/sanitizer.py`
- causa: regex de STS sem grupos capturados, mas o código usava `group(1)` e `group(2)`

Intervenção:

- corrigir a regex para capturar role e session

Motivo:

- manter os artefatos sanitizados gerados automaticamente durante os experimentos reais

## Soluções arquiteturais introduzidas

### 1. Estado com memória mínima
- `tested_assume_roles`
- `failed_assume_roles`
- `active_assumed_roles`
- `active_branch_action_count`

### 2. Prompting orientado por busca
- `enumeration_sufficient`
- `should_commit_to_pivot`
- `should_explore_current_branch`
- `candidate_roles`

### 3. Policy layer antes do LLM
- `action shaping`

Regra geral:

- se existe branch ativo com ações de progresso, o planner decide primeiro dentro desse subconjunto

### 4. Melhor observabilidade experimental
- sanitização com aliases distintos
- report com `candidate_roles`, `selected_role`, `rejected_roles`
- Mermaid mostrando branch distrator

## Descoberta principal
O problema raiz não é o modelo. O problema raiz é representação de estado e framing do planner.

O Path 3 mostrou uma divisão útil entre três camadas:

- qualidade do modelo
- estrutura do prompt
- policy de busca do engine

Modelo melhor sem policy de busca ainda falha. Policy de busca com modelo menor pode ser suficiente para convergir.

## Interpretação
O experimento provou:

- Paths 1 e 2 validaram executor, enforcement e planner em fluxos lineares
- o Path 3 introduziu o problema de escolha entre pivôs concorrentes
- memória mínima melhorou o comportamento, mas não resolveu sozinha
- prompting melhorou o comportamento, mas não resolveu sozinho
- `action shaping` geral foi suficiente para transformar um planner oscilante em um planner convergente neste cenário

O experimento não provou:

- que qualquer modelo local pequeno passará após as mudanças
- que `action shaping` simples substitui backtracking estruturado
- que o mesmo comportamento já generaliza para espaços de decisão mais profundos

## Implicações arquiteturais
- `candidate path tracking`
- `branch failure memory`
- `backtracking`
- `path scoring`
- `recovery-oriented state`

## Ameaças à validade
- o Path 3 ainda tem espaço de decisão pequeno
- o experimento atual usa um único objetivo final em S3
- `action shaping` ainda é uma heurística simples, não um planejador completo
- `gpt-4o-mini` passou neste cenário, mas isso não garante desempenho igual em cenários mais profundos
- `OllamaPlanner` ainda precisa ser reavaliado após as mesmas mudanças

## Conclusão
H1 foi refutada nas etapas 2–4 e confirmada na etapa 5.

H2 foi refutada no engine inicial e parcialmente confirmada após as mudanças arquiteturais introduzidas.

O que orienta os próximos experimentos:

- melhorar a capacidade de busca do engine
- reavaliar planners locais após as mesmas mudanças
- evoluir de memória mínima e heurística de branch para backtracking mais explícito

## Próximos experimentos
EXP-004: reavaliar OllamaPlanner após action shaping — hipótese: o mesmo mecanismo que desbloqueou `gpt-4o-mini` é suficiente para `phi3:mini`?

EXP-005: backtracking estruturado — hipótese: com `candidate path tracking` explícito no estado, o planner evita revisitar branches failed sem depender de heurística de `action shaping`?
