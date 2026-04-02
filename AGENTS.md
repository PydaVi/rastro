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
