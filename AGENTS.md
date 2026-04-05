# AGENTS.md — Rastro

Contrato de desenvolvimento para agentes de IA que trabalham neste repositório.
Leia completamente antes de implementar qualquer código.

---

## O que é o Rastro

Rastro é um engine de simulação adversarial autônoma focado em cloud.

O objetivo é:
- raciocinar sobre caminhos de comprometimento
- validar esses caminhos de forma controlada quando autorizado
- produzir evidência auditável passo a passo

Rastro não é scanner de vulnerabilidades.
Rastro prova attack paths completos.

---

## Direção estratégica do produto

Rastro possui um engine central e dois produtos:

### Produto 01 — Validação de Exposição (prioridade atual)
- execução em AWS real autorizado
- evidência real com ARNs, timestamps e respostas de API
- relatório técnico e executivo com MITRE mapping

### Produto 02 — Attack Path em CI/CD (futuro próximo)
- análise de Terraform plan antes do deploy
- bloqueio de merge se houver attack path crítico
- simulação sem deploy real

---

## Ordem estratégica obrigatória

1. AWS primeiro
2. Produto 01 antes do Produto 02
3. profundidade antes de expansão
4. Kubernetes somente após maturidade AWS

O agente deve respeitar essa ordem. Não implementar Kubernetes real.
Não iniciar Produto 02 antes de Produto 01 estar estável.

---

## Régua permanente de direção do produto

Toda implementação, experimento, correção e bloco de roadmap deve ser avaliado
contra dois polos explícitos:

### Polo 1 — `campaign validator`

O Rastro se comporta mais como `campaign validator` quando depende
principalmente de:
- profiles fixos como verdade anterior ao raciocínio
- heurísticas lexicais simples
- alvos pré-modelados
- scopes já quase prontos para o caminho correto
- harness sintético excessivamente curado
- expansão de bundles sem contrapartida de inferência
- correções específicas para um fixture sem ganho arquitetural reutilizável

### Polo 2 — `generalista ofensivo`

O Rastro se aproxima do polo `generalista ofensivo` quando aumenta:
- inferência estrutural
- selection por expressividade ofensiva
- competição entre paths concorrentes
- reachability real
- modelagem explícita de credential acquisition
- robustez em mixed environments
- robustez com naming desfavorável ou obfuscado
- separação entre `identity reached` e `credentials acquired`
- capacidade de escolher e provar caminhos fora de campanhas IAM-first puras

### Critérios obrigatórios de avaliação

Toda mudança relevante deve ser julgada por quanto:
- reduz dependência de profiles fixos
- reduz dependência de heurísticas lexicais simples
- reduz dependência de alvos pré-modelados
- reduz dependência de harness sintético excessivamente curado
- aumenta inferência estrutural
- aumenta selection por expressividade ofensiva
- aumenta competição entre paths concorrentes
- aumenta reachability real
- aumenta modelagem explícita de credential acquisition
- aumenta robustez em mixed environments
- aumenta robustez com naming desfavorável ou obfuscado

### Regra operacional obrigatória

Melhorias operacionais são válidas e necessárias, mas não podem substituir por
muitos blocos consecutivos o avanço em generalização ofensiva.

Se os blocos recentes aumentaram principalmente:
- CLI
- runner
- reporting
- orchestration
- bundles
- execução de campaigns conhecidas

então o próximo bloco deve preferencialmente recuperar avanço em:
- mixed benchmarks
- inferência estrutural
- reachability
- compute / external entry / cross-account / multi-step
- credential acquisition

Quando o projeto já tiver alta robustez em:
- benchmarks estruturados
- fixture sets
- mixed environments sintéticos
- campaigns reais previamente modeladas

o próximo passo preferencial deve ser um experimento `blind` que maximize
revelação arquitetural nova, mesmo que tenha maior chance de falha.

O agente não deve escolher automaticamente o próximo bloco mais seguro,
incremental ou operacional se existir um experimento `blind` com maior valor
epistemológico para medir generalização ofensiva real.

Benchmark sintético, fixture set e harness são meios de maturação.
Não podem virar substitutos permanentes da prova `blind real`.

### Regra permanente para `blind real`

Em modo `blind real`, o agente deve presumir que qualquer dependência residual
de:
- `fixture_path`
- `execution_fixture_set`
- `scope_template_path`
- resolver sintético por archetype

é uma suspeita arquitetural séria, e não uma conveniência aceitável.

Se um assessment discovery-driven em AWS real recair nesses mecanismos, isso
deve ser tratado como bloqueio estrutural do produto.

Em `blind real`, dependencia residual de:
- `fixture_path`
- `execution_fixture_set`
- `scope_template_path`
- resolver sintetico por archetype

nao e conveniencia aceitavel. E evidencia de que o produto ainda esta
funcionando como `campaign validator`.

### Regra permanente para estados de prova

O agente deve tratar como falha estrutural, e não ajuste pontual, quando:
- um achado `validated` depende apenas de `target_observed`
- o runtime real não consegue representar ações intermediárias da classe ofensiva
- o produto mede `sucesso` por campaigns passadas sem medir:
  - unicidade
  - prova mínima
  - coverage por classe

Nesses casos, a correção deve priorizar:
- modelo explícito de estados de prova
- evidência mínima por classe ofensiva
- separação entre descoberta, reachability, credencial obtida e impacto validado

Estados minimos a perseguir quando o dominio exigir prova progressiva:
- `observed`
- `reachable`
- `credentialed`
- `exploited`
- `validated_impact`

### Regra permanente para ambientes IAM-heavy

Em ambientes IAM-heavy, o agente não deve interpretar subcobertura como
simples falta de benchmark.

Ele deve investigar explicitamente:
- desalinhamento de portfolio
- pobreza de discovery IAM
- ranking de exploitability
- ausência de action space real
- overclaim no reporting
- contaminação residual do harness sintético

Se esses fatores aparecerem, o próximo bloco deve ser de reestruturação do
núcleo, não apenas de expansão incremental de profiles.

Em ambiente IAM-heavy, subcobertura nao deve ser explicada automaticamente por
`faltou benchmark` ou `faltou mais um profile`.

O agente deve primeiro testar a hipotese mais dura:
- portfolio ofensivo desalinhado
- discovery IAM estrutural pobre
- ranking de exploitability fraco
- absence de action space real intermediario
- overclaim no reporting
- contaminacao residual do modo blind por harness sintetico

### Pergunta interna obrigatória antes do próximo passo

Antes de propor o próximo passo, o agente deve responder internamente:

- `isso aumenta generalização ofensiva real ou só melhora execução de campaigns conhecidas?`
- `existe um experimento blind com maior poder de revelação arquitetural do que o bloco incremental atual?`

Se a resposta for principalmente a segunda, o agente deve procurar o próximo
bloco com maior leverage para deslocar o produto na direção do polo
`generalista ofensivo`, sem violar a ordem estratégica macro.

### Regra permanente para `external entry`

Sempre que um path for classificado como `external entry`, o agente deve
distinguir explicitamente:

- se ha apenas superficie publica declarada
- se ha reachability de rede comprovada ate o workload
- se ha aquisicao de credenciais comprovada
- se ha exploracao completa ate o dado final

Esses niveis nao podem ser colapsados em um unico estado conceitual.

### Regra permanente de linguagem para `external entry`

O agente nao deve descrever um path `external entry` como:

- `explorável da internet`
- `internet to data proved`
- ou formula equivalente

quando o sistema so tiver provado:

- exposicao estrutural
- pivô credenciado controlado
- path ao dado

Nesses casos, a formulacao correta deve separar:

- `public exposure structurally linked to privileged path`
de
- `public exploit path proved end-to-end`

Se a prova de reachability real de rede ate o workload nao existir, isso deve
ser dito explicitamente.

---

## Prioridades atuais

O agente deve priorizar nesta ordem:

**1. Robustez do engine**
- backtracking sólido
- path scoring consistente
- branch memory sem loops
- action shaping geral

**2. Attack paths AWS completos**
- IAM / STS / S3 / Secrets Manager / SSM
- sempre chains completas do ponto de entrada ao objetivo
- nunca features isoladas

**3. Produto 01 — Validação de Exposição**
- contrato de integração AWS (ver seção abaixo)
- relatório auditável e sanitizado
- evidência clara por step

**4. Base do Produto 02 (apenas quando Produto 01 estiver estável)**
- parser de `terraform show -json`
- projeção de estado resultante

---

## Regra de transição por prioridade (obrigatória)

Cada prioridade do `PLAN.md` deve ser fechada com um bloco de experimentos
planejado. Quando o bloco for concluído, o agente deve:

1. Registrar a conclusão no `PLAN.md`
2. Planejar o próximo bloco de experimentos da prioridade seguinte
3. Avançar automaticamente para essa prioridade, sem pedir orientação

Essa regra evita foco excessivo em minúcias e mantém o progresso alinhado
ao objetivo macro do eixo.

Além disso, ao fechar cada bloco, o agente deve registrar explicitamente
no `PLAN.md` qual foi a direção predominante do avanço:

- `mais generalização ofensiva`
- `mais operacionalização de campaigns conhecidas`

Essa marcação é obrigatória para evitar drift de produto.

Se um bloco aumentar principalmente:
- descoberta real
- target selection semântico
- redução de dependência em profiles fixos
- redução de heurísticas lexicais
- pivôs compute / external entry / cross-account
- chains multi-step menos pré-modeladas

então ele deve ser classificado como `mais generalização ofensiva`.

Se um bloco aumentar principalmente:
- CLI
- runner
- assessment orchestration
- relatórios
- bundle/profile execution
- campanhas derivadas ainda fortemente de profiles conhecidos

então ele deve ser classificado como `mais operacionalização de campaigns conhecidas`.

O agente deve preferir os próximos blocos que empurrem o produto na direção
de um `autonomous attacker-thinker` mais generalista, sem perder a disciplina
operacional do Produto 01.

Ao fechar cada bloco, o agente deve registrar explicitamente no `PLAN.md`:
- o que aproximou o projeto do polo `generalista ofensivo`
- o que permaneceu dependente de `campaign validator`
- qual é o próximo experimento com maior leverage para mover a régua

---

## Regra para correção após falha experimental (obrigatória)

Quando um experimento falhar:

1. Identificar a causa raiz (não o sintoma) e registrar o que o
   experimento revelou sobre o engine que ainda não estava provado.
2. Separar as causas possíveis:
   - falha de infraestrutura (fixture, executor, sanitização)
   - falha de representação de estado
   - falha de policy (action shaping / path scoring)
   - falha de framing do planner (prompt)
   - limitação genuína do modelo
3. Documentar a descoberta em `docs/experiments/` antes de implementar
   qualquer correção.
4. Implementar a correção mais geral possível — válida para cenários
   futuros, não apenas para o path atual.
5. Validar `pytest` e garantir que o MockPlanner continua funcionando.

---

## Separação de responsabilidades

```
Planner       → sugere próxima ação
Engine        → controla loop, candidatos, backtracking
Scope Enforcer → valida ação antes de executar
Executor      → executa ação validada
Reporting     → gera artefatos auditáveis
```

Nenhuma lógica de segurança depende do LLM.
O LLM é um componente de raciocínio — não o orquestrador.

---

## Decisões de design invioláveis

### 1. Nenhum vendor obrigatório
Ollama é padrão. Backends são plugáveis via factory `get_planner()`.
Nunca adicionar dependência hard a provider de LLM.

### 2. Interface Planner é estável
```python
class Planner(ABC):
    @abstractmethod
    def decide(self, snapshot, available_actions: List[Action]) -> Decision:
        ...
```
Não alterar assinatura. Todos os backends implementam exatamente isso.

### 3. Scope Enforcer é obrigatório
Toda ação passa pelo ScopeEnforcer antes de executar.
Sem exceção. Sem bypass. Sem flags como `--unsafe` ou `--skip-scope`.

### 4. Audit Logger é append-only
O log `audit.jsonl` nunca é sobrescrito ou deletado durante um run.
Não adicionar rotação, limpeza ou truncamento automático.

### 5. Testes sem dependência externa
pytest roda offline — sem AWS, sem Ollama, sem internet.
Testes de integração ficam em `tests/integration/` marcados com
`@pytest.mark.integration`. Nunca na suite padrão.

---

## Contrato de integração AWS

O Rastro acessa contas AWS via role assumível com trust policy
restrita ao ARN do executor. O processo tem três passos obrigatórios:

**1. Preflight**
Antes de iniciar o loop, validar que as permissões declaradas no
`scope.yaml` existem e são acessíveis na conta alvo.
Se o preflight falhar, o run não inicia — nunca silencia o erro.

**2. Execução**
Operar apenas dentro dos serviços, regiões e recursos definidos
no `scope.yaml`. O Scope Enforcer valida cada ação antes de executar.
Campos obrigatórios no scope para ambiente real:
- `authorized_by`
- `authorized_at`
- `authorization_document`

**3. Cleanup**
Nenhum recurso criado pelo Rastro permanece após o run.
Se o run criar algo (access key temporária, policy version),
o cleanup é responsabilidade do executor — não do operador.

Sem esses três passos implementados e validados,
o Produto 01 não está pronto para engajamento com cliente real.

---

## Regras de implementação

### Planner
- output JSON estruturado — nunca texto livre
- validar schema antes de construir Decision
- fallback seguro se LLM retornar formato inválido
- imports de dependências opcionais são tardios (dentro da classe)

### Domain model
- Pydantic BaseModel
- campos novos são opcionais com default
- não quebrar modelos existentes — adicionar, não substituir

### Tool Registry
- YAML declarativo em `tools/<plataforma>/<nome>.yaml`
- campos obrigatórios: `mitre_id`, `preconditions`, `postconditions`
- implementação Python em `tools/<plataforma>/<nome>.py`
- fixture sintético correspondente para testes

### Loop principal
Ordem obrigatória e imutável:
```
enumerate → plan → validate → execute → observe → graph
```
Não adicionar lógica de negócio no app — pertence aos módulos de core.
O loop tem `max_steps`. Não remover esse limite.

### Estado do engine
Campos de memória de tentativa obrigatórios:
- `tested_assume_roles`
- `failed_assume_roles`
- `active_assumed_roles`
- `active_branch_action_count`
- `candidate_paths` com status: untested / promising / failed / successful

---

## Regras de priorização arquitetural

Quando escolher o que implementar, priorizar o que:

1. fortalece o engine central (backtracking, scoring, memória)
2. melhora attack paths completos (chains reais do início ao fim)
3. aumenta auditabilidade (evidência, logs, sanitização)
4. é reutilizável entre os dois produtos
5. revela comportamento arquitetural novo

---

## O que não fazer

- Não implementar Kubernetes real (apenas modelar)
- Não expandir AWS sem fechar experimento atual
- Não criar scanner de misconfiguração isolada
- Não acoplar lógica de segurança ao LLM
- Não bypassar Scope Enforcer
- Não adicionar dependências obrigatórias externas
- Não fazer commit de API keys mesmo em exemplos
- Não remover mock_planner — necessário para suite de testes

---

## Metodologia científica — regra permanente

Todo experimento, path ou descoberta que revele mudança real de
entendimento sobre o engine deve gerar:

`docs/experiments/EXP-NNN-nome.md`

Com estrutura obrigatória:
- Identificação (ID, fase, data, status)
- Contexto
- Hipóteses
- Desenho experimental (variável independente, ambiente, critério)
- Resultados por etapa (cada planner/configuração separado)
- Erros, intervenções e motivos (quando aplicável)
- Descoberta principal
- Interpretação
- Implicações arquiteturais
- Ameaças à validade
- Conclusão
- Próximos experimentos

Resultados negativos têm a mesma obrigatoriedade que positivos.
Um experimento que falha e isola uma causa é mais valioso do que
um que passa sem revelar nada.

O agente não espera instrução explícita para criar esses documentos.
Sempre que um path ou validação revelar algo relevante, o documento
é criado como parte da tarefa em andamento.

Decisões arquiteturais relevantes viram ADR em `docs/adr/`.

---

## Regra de orientação antes de propor próximos passos

Antes de indicar o próximo passo, o agente deve ler o `PLAN.md` completo
e garantir que a proposta está alinhada ao objetivo macro do projeto,
evitando micro-otimizações que desviem o foco.

Essa leitura deve incluir uma avaliação explícita de:
- quanto o bloco atual aproximou o Rastro de generalização ofensiva
- quanto ainda o manteve dependente de campaigns AWS pré-estruturadas

Se houver dúvida entre dois próximos passos, o agente deve preferir o que:
- reduz dependência de profiles fixos
- reduz dependência de alvos pré-modelados
- reduz dependência de heurísticas lexicais simples
- aumenta descoberta real e seleção semântica
- abre compute pivots, external entry, cross-account e chains multi-step

---

## Quando terminar uma tarefa

Verificar antes de considerar completo:

1. `pytest` passa sem erros e sem dependências externas
2. mock planner continua funcionando normalmente
3. nenhuma interface existente foi quebrada
4. se adicionou dependência nova, está em `pyproject.toml` como opcional
5. novo código tem ao menos um teste unitário
6. se uma fase foi concluída, atualizar PLAN.md e AGENTS.md

---

## Regra final

Se a mudança não melhora a capacidade do Rastro de provar
attack paths reais com evidência auditável,
ela provavelmente não deve ser feita.
