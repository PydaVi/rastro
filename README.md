# Rastro

**Agente de red team autônomo para ambientes cloud e Linux.**

Rastro não lista vulnerabilidades. Ele raciocina sobre elas, as encadeia,
e constrói o caminho completo de comprometimento — do ponto de entrada ao
objetivo final.

A diferença real de ferramentas de assessment estático: enquanto scanners
identificam findings isolados, um atacante competente *pensa* — conecta uma
permissão IAM excessiva com um bucket público com uma Lambda mal configurada
até chegar onde quer. Rastro faz o mesmo, de forma autônoma e auditável.

```
analyst → [assume AuditRole] → [access sensitive_bucket] → objetivo atingido

attack path gerado em 2 passos
scope enforcer: 0 ações bloqueadas
audit log: completo
```

---

## Status

**Fase 0 completa.** Loop central funcionando com fixture sintético IAM.
Scope Enforcer, Audit Logger, Attack Graph e Report Engine implementados.

**Fase 1 em progresso.** `OllamaPlanner` validado end-to-end com modelo local.
`OpenAIPlanner` e `ClaudePlanner` já estão implementados no código, mas ainda
pendem de validação com credenciais reais.

**MITRE mapping no MVP já está implementado** (techniques no fixture + relatório).
**Tool Registry base já está implementado** (YAML + pré-condições).
**Fase 2 dry-run já começou** com cenário AWS local, autorização obrigatória,
política explícita no report/audit e enforcement por `allowed_services`,
`allowed_regions` e `aws_account_ids`.

Ver [PLAN.md](PLAN.md) para roadmap completo.

---

## Backend de LLM — sem vendor obrigatório

Rastro é open source. Nenhuma API proprietária é requisito.

O backend é configurável no `scope.yaml`. O padrão recomendado é
**Ollama** — self-hosted, sem internet, sem custo, compatível com
qualquer modelo local (Llama, Qwen, Mistral, Phi).

Para ambientes sensíveis onde mandar contexto de ataque para uma API
externa é inaceitável, Ollama local é a única opção que faz sentido
operacionalmente.

```yaml
# scope.yaml
planner:
  backend: ollama             # ollama | openai | claude
  model: llama3.1:8b
  base_url: http://localhost:11434
```

Backends disponíveis:

| Backend | Quando usar |
|---------|-------------|
| `ollama` | padrão — self-hosted, air-gapped, sem custo |
| `openai` | OpenAI, Groq, Together AI, qualquer API OpenAI-compatible |
| `claude` | Anthropic API — opcional |
| `mock` | testes determinísticos sem LLM |

---

## O que o Rastro faz (hoje)

- Recebe um objetivo de ataque e um escopo definido em YAML
- Carrega um ambiente alvo (fixture sintético no MVP, AWS dry-run na Fase 2)
- Executa o loop: `enumerate → plan → validate → execute → observe → graph`
- Cada ação é validada pelo Scope Enforcer antes de executar
- Cada decisão é logada no audit trail append-only
- Cada step registra backend do planner, motivo da decisão e resposta bruta do LLM quando aplicável
- O attack graph é construído em tempo real
- Ao final: relatório Markdown + JSON com o caminho de comprometimento

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Executar com mock planner (sem LLM necessário):

```bash
python -m app.main \
  --fixture fixtures/iam_lab.json \
  --objective examples/objective.json \
  --scope examples/scope.json \
  --out outputs \
  --max-steps 5
```

Executar com Ollama (requer `ollama serve` rodando localmente):

Use `examples/scope_ollama.json` (modelo leve recomendado: `phi3:mini`).

```bash
python -m app.main \
  --fixture fixtures/iam_lab.json \
  --objective examples/objective.json \
  --scope examples/scope_ollama.json \
  --out outputs
```

Executar o fluxo AWS em `dry-run` (sem chamadas reais):

```bash
python -m app.main \
  --fixture fixtures/aws_dry_run_lab.json \
  --objective examples/objective_aws_dry_run.json \
  --scope examples/scope_aws_dry_run.json \
  --out outputs
```

Outputs gerados:

```
outputs/
  audit.jsonl        # log append-only de cada decisão e ação
  report.md          # relatório narrativo com attack path
  report.json        # dados estruturados para integração
  attack_graph.mmd   # grafo de comprometimento em Mermaid
```

No `report.json`, cada item de `steps` inclui `planner_metadata` com:
- `planner_backend`
- `planner_model` quando houver
- `raw_response` para planners LLM

No fluxo AWS dry-run, `report.json` e `audit.jsonl` também incluem:
- `execution_policy`
- `execution_mode`
- `real_api_called`
- evidências AWS sintéticas como `aws_identity`, `simulated_policy_result` e `evidence`

---

## Arquitetura

```
┌─────────────────────────────────────────────────┐
│                 RASTRO CORE                      │
│                                                  │
│  Planner ──────────────▶ Tool Executor           │
│  (ollama/openai/mock)   (scope-gated)            │
│      ▲                       │                   │
│      │ estado                ▼                   │
│  Attack Graph ◀──────── Tool Registry            │
│  (estrutura própria)    (YAML plugins)           │
└─────────────────────────────────────────────────┘
         │
         ▼
  Report Engine    Scope Enforcer    Audit Logger
  (MD + JSON)      (obrigatório)     (append-only)
```

**Planner** — orquestrador LLM com memória de sessão. Recebe o estado atual
do grafo e decide qual ação executar em seguida. Backend configurável:
mock, Ollama (padrão), qualquer API OpenAI-compatible, ou Anthropic.

**Tool Registry** — cada técnica ofensiva é um plugin YAML com nome, fase
MITRE, pré-condições e pós-condições. O Planner seleciona tools por
pré-condições, não por prompt livre.

**Scope Enforcer** — toda ação passa por aqui antes de executar. Sem exceções.
No fluxo AWS dry-run, o ambiente também filtra ações por `allowed_services`,
`allowed_regions` e `aws_account_ids`, e rejeita execução direta fora da política.

**Attack Graph** — grafo dirigido onde nós são estados de comprometimento e
arestas são técnicas executadas. Base do relatório final e de futuras
publicações acadêmicas.

**Audit Logger** — JSONL append-only com timestamp, decisão, ação, resultado,
raciocínio do Planner e política de execução aplicada.

---

## Escopo e autorização

Rastro só executa ações dentro do escopo definido. Em ambiente real,
o `scope.yaml` exige autorização explícita:

```yaml
aws_account_ids:
  - "123456789012"
allowed_services:
  - iam
  - sts
  - s3
authorized_by: "nome completo"
authorized_at: "2026-01-01"
authorization_document: "docs/authorization.pdf"
```

Sem `authorized_by` e `authorization_document`, o run não inicia.
Isso está no código. Não use Rastro sem autorização explícita do dono
do ambiente.

---

## Roadmap

| Fase | Objetivo | Status |
|------|----------|--------|
| 0 | Loop central + fixture sintético IAM | ✓ completa |
| 1 | LLM Planner plugável + MITRE mapping + Tool Registry | em progresso |
| 2 | AWS dry-run + preparação para conta real autorizada | em progresso |
| 3 | Kubernetes attack paths | pendente |
| 4 | Linux + ambiente híbrido | pendente |
| 5 | v1.0 + dataset público + Neo4j | pendente |

---

## Cobertura MITRE ATT&CK (planejada)

| Técnica | ID | Fase | Plataforma |
|---------|-----|------|------------|
| Account Discovery | T1087.004 | Discovery | AWS |
| Permission Groups Discovery | T1069.003 | Discovery | AWS |
| Abuse Elevation Control — PassRole | T1548 | Priv. Escalation | AWS |
| Create/Modify Cloud Credentials | T1098.001 | Persistence | AWS |
| Valid Accounts — Cloud | T1078.004 | Initial Access | AWS |
| Data from Cloud Storage | T1530 | Collection | AWS |
| Container Escape | T1611 | Priv. Escalation | Kubernetes |
| Lateral Movement via SSM | T1021 | Lateral Movement | AWS/Linux |

---

## Stack

- **Python 3.12** — ecossistema de segurança ofensiva (boto3, impacket,
  kubernetes-client, nuclei-python)
- **Ollama** — LLM self-hosted padrão; qualquer modelo local compatível
- **Estrutura própria** — attack graph em memória; Neo4j pode entrar na v1.0
- **pytest** — testes sem dependências externas

---

## Contribuindo

O projeto está em fase inicial. Se você quer contribuir, leia o
[PLAN.md](PLAN.md) para entender onde estamos e para onde vamos,
e o [AGENTS.md](AGENTS.md) para as restrições de desenvolvimento.

Issues e discussões são bem-vindas. PRs que adicionam ferramentas ofensivas
reais antes da Fase 2 estar completa serão fechados.

---

## Licença

Apache 2.0

---

*Use Rastro somente em ambientes que você tem autorização explícita para testar.*
