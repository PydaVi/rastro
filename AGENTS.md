# AGENTS.md

Este arquivo define o contrato de desenvolvimento para agentes de IA (Codex,
Claude, ou qualquer outro) que trabalham neste repositório.

Leia este arquivo completamente antes de escrever qualquer linha de código.

---

## O que é o Rastro

Rastro é um agente de red team autônomo para ambientes cloud e Linux.
O objetivo é raciocinar sobre caminhos de comprometimento — não executar
ataques reais.

É um projeto open source com pretensão de uso em pesquisa acadêmica e
segurança defensiva. Isso tem implicações diretas nas decisões de design.

---

## Estado atual do projeto

**Fase 0 — completa.** Loop central com fixture sintético funcionando.

**Fase 1 — completa.** OllamaPlanner validado, Tool Registry YAML,
MITRE mapping, dry-run funcional. OpenAIPlanner e ClaudePlanner
implementados, pendentes de validação end-to-end com credenciais reais.

**Fase 2 — completa para o primeiro corte AWS real.** Executor AWS real,
Paths 1 e 2 validados com MockPlanner e OllamaPlanner, artefatos
sanitizados automáticos.

**Fase 3 — em progresso.** Path 3 validado com MockPlanner em AWS real.
Path 3 com OllamaPlanner falhou — documentado em EXP-003. Path 3 com
OpenAIPlanner passou após introdução de memória mínima e action shaping.
O engine agora possui: memória de tentativa, prompting orientado por busca,
e policy layer de action shaping. Próximos experimentos: reavaliar
OllamaPlanner após as mudanças (EXP-004), e backtracking estruturado
com candidate path tracking explícito (EXP-005).

Consulte `PLAN.md` para o detalhamento completo de cada item.

---

## Decisões de design já tomadas — não reverter

## Metodologia científica — regra permanente

Todo experimento, path ou descoberta que revele mudança real de
entendimento sobre o engine deve ser documentado em
`docs/experiments/EXP-NNN-nome.md` com a seguinte estrutura:

- Identificação (ID, fase, data, status)
- Contexto
- Hipóteses
- Desenho experimental (variável independente, ambiente, critério de sucesso)
- Resultados por etapa (cada planner/configuração separado)
- Erros, intervenções e motivos (quando aplicável)
- Descoberta principal
- Interpretação
- Implicações arquiteturais
- Ameaças à validade
- Conclusão
- Próximos experimentos

Decisões arquiteturais relevantes viram ADR em `docs/adr/`.

Resultados negativos têm a mesma obrigatoriedade de documentação que
resultados positivos. Um experimento que falha e isola uma causa é mais
valioso do que um que passa sem revelar nada.

O Codex não espera instrução explícita para criar esses documentos.
Sempre que um path ou validação revelar algo relevante, o documento
é criado como parte da tarefa em andamento.

### 1. Nenhum vendor de LLM é obrigatório

O backend de LLM é configurável. **Ollama é o padrão recomendado** —
self-hosted, sem internet, sem custo.

```
src/planner/
  interface.py           # contrato estável — NÃO MODIFICAR a assinatura
  mock_planner.py        # determinístico — para testes, já funciona
  ollama_planner.py      # padrão — self-hosted via Ollama
  openai_planner.py      # OpenAI e qualquer API OpenAI-compatible
  claude_planner.py      # Anthropic — opcional, não é o padrão
```

A factory `get_planner(backend="ollama", ...)` em `src/planner/__init__.py`
é o ponto de entrada. O resto do código usa a interface `Planner` — nunca
importa um planner concreto diretamente.

**Não adicione dependência hard em nenhum provider de LLM.**
Se precisar de um novo backend, crie um novo arquivo seguindo o mesmo padrão.

### 2. A interface Planner é estável

```python
class Planner(ABC):
    @abstractmethod
    def decide(self, snapshot, available_actions: List[Action]) -> Decision:
        ...
```

Não altere essa assinatura. Todos os backends implementam exatamente isso.

### 3. Scope Enforcer é obrigatório e inviolável

Toda ação passa pelo `ScopeEnforcer` antes de executar.
Não existe bypass. Não existe modo de debug que pule essa camada.
Não adicione flags como `--unsafe`, `--skip-scope`, ou similares.

### 4. Audit Logger é append-only

O log em `audit.jsonl` nunca é sobrescrito ou deletado durante um run.
Não adicione lógica de rotação, limpeza ou truncamento automático.

### 5. Testes não dependem de serviços externos

A suite `pytest` roda sem AWS, sem Ollama, sem internet.
LLM planners são testados com mocks que simulam respostas estruturadas.
Se um teste precisar de serviço externo, ele vai para `tests/integration/`
e é marcado com `@pytest.mark.integration` — nunca na suite padrão.

---

## Estrutura do projeto

```
src/
  app/           — CLI e orquestração do loop principal
  core/          — domain models, attack graph, audit, state, fixture
  execution/     — scope enforcer, executor
  planner/       — interface + backends (mock, ollama, openai, claude)
  reporting/     — geração de relatório MD e JSON

fixtures/        — ambientes sintéticos para testes
tools/           — plugins YAML do Tool Registry (Fase 1)
examples/        — exemplos de scope.yaml e objective.json
tests/           — suite pytest sem dependências externas
docs/            — arquitetura e ADRs
```

---

## Regras de implementação

**Ao implementar um novo Planner backend:**
- Implemente a interface `Planner` de `planner/interface.py`
- O output do LLM deve ser JSON estruturado — nunca texto livre
- Valide o schema retornado antes de construir um `Decision`
- Se o LLM retornar ação inválida: fallback seguro + log, não exception
- Dependências do backend (httpx, openai, anthropic) são imports tardios
  dentro da classe — não no topo do módulo — para não quebrar quem não usa

**Ao adicionar ao domain model (`src/core/domain.py`):**
- Use Pydantic BaseModel
- Campos novos são opcionais com default quando possível
- Não quebre modelos que já existem — adicione, não substitua

**Ao adicionar uma Tool ao Tool Registry:**
- Crie o YAML em `tools/<plataforma>/<nome>.yaml`
- Inclua: `mitre_id`, `preconditions`, `postconditions`, `safe_simulation`
- A implementação Python vai em `tools/<plataforma>/<nome>.py`
- Adicione fixture sintético correspondente para testes

**Ao modificar o loop principal (`src/app/main.py`):**
- O loop tem max_steps. Não remova esse limite.
- A ordem é sempre: enumerate → plan → validate → execute → observe → graph
- Não adicione lógica de negócio no app — ela pertence aos módulos de core
- Validações antecipadas de segurança podem falhar antes do loop se `scope`,
  `fixture` e `objective` forem incompatíveis

**Ao modificar o ambiente AWS dry-run:**
- Continue 100% local — nenhuma chamada real a AWS nesta fase
- Preserve `execution_mode=dry_run` e `real_api_called=false`
- Respeite `allowed_services`, `allowed_regions`, `aws_account_ids` e `allowed_resources` tanto na enumeração quanto na execução
- Qualquer endurecimento novo precisa de teste cobrindo regressão

**Ao modificar o executor AWS real:**
- Imports opcionais do SDK devem continuar tardios
- Toda chamada real deve respeitar `allowed_services`, `allowed_regions`,
  `aws_account_ids` e `allowed_resources`
- O gate `RASTRO_ENABLE_AWS_REAL=1` não deve ser removido sem decisão explícita
- Testes da suite padrão continuam sem depender de AWS
- Artefatos reais compartilháveis devem sair das versões sanitizadas, nunca dos
  reports/audits brutos

---

## O que não fazer

- Não implemente novas superfícies reais fora de AWS antes do roadmap permitir
- Não adicione dependências de LLM como requisito obrigatório do projeto
- Não remova o mock_planner — ele é necessário para a suite de testes
- Não altere a interface `Planner` sem atualizar todos os backends
- Não escreva testes que chamam APIs externas sem marcar como integration
- Não adicione flags que bypassem o Scope Enforcer
- Não faça commit de API keys, mesmo em exemplos

---

## Quando terminar uma tarefa

Antes de considerar uma implementação completa, verifique:

1. `pytest` passa sem erros e sem dependências externas
2. O mock planner continua funcionando normalmente
3. Nenhuma interface existente foi quebrada
4. Se adicionou dependência nova, está em `pyproject.toml` como opcional
5. O novo código tem ao menos um teste unitário
6. Se uma etapa/fase foi concluída, atualize `PLAN.md`, `README.md` e `AGENTS.md`

---

## Referências

- `PLAN.md` — roadmap detalhado com critérios de conclusão por fase
- `docs/architecture.md` — visão geral dos componentes
- `docs/adr/` — decisões de arquitetura registradas
