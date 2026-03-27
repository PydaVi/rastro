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

**Fase 1 em progresso.** LLM Planner real (Claude API) + MITRE ATT&CK mapping
+ Tool Registry declarativo.

Ver [PLAN.md](PLAN.md) para roadmap completo.

---

## O que o Rastro faz (hoje)

- Recebe um objetivo de ataque e um escopo definido em YAML
- Carrega um ambiente alvo (fixture sintético no MVP, AWS real na Fase 2)
- Executa o loop: `enumerate → plan → validate → execute → observe → graph`
- Cada ação é validada pelo Scope Enforcer antes de executar
- Cada decisão é logada no audit trail append-only
- O attack graph é construído em tempo real
- Ao final: relatório Markdown + JSON com o caminho de comprometimento

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Executar o demo com fixture sintético IAM:

```bash
rastro run \
  --fixture fixtures/iam_lab.json \
  --objective examples/objective.json \
  --scope examples/scope.json \
  --out outputs \
  --max-steps 5
```

Outputs gerados:

```
outputs/
  audit.jsonl        # log append-only de cada decisão e ação
  report.md          # relatório narrativo com attack path
  report.json        # dados estruturados para integração
  attack_graph.mmd   # grafo de comprometimento em Mermaid
```

---

## Arquitetura

```
┌─────────────────────────────────────────────────┐
│                 RASTRO CORE                      │
│                                                  │
│  Planner ──────────────▶ Tool Executor           │
│  (LLM / mock)           (scope-gated)            │
│      ▲                       │                   │
│      │ estado                ▼                   │
│  Attack Graph ◀──────── Tool Registry            │
│  (networkx)             (YAML plugins)           │
└─────────────────────────────────────────────────┘
         │
         ▼
  Report Engine    Scope Enforcer    Audit Logger
  (MD + JSON)      (obrigatório)     (append-only)
```

**Planner** — orquestrador LLM com memória de sessão. Recebe o estado atual
do grafo e decide qual ação executar em seguida. No MVP usa mock determinístico;
Fase 1 substitui por Claude API com tool use.

**Tool Registry** — cada técnica ofensiva é um plugin YAML com nome, fase
MITRE, pré-condições e pós-condições. O Planner seleciona tools por
pré-condições, não por prompt livre.

**Scope Enforcer** — toda ação passa por aqui antes de executar. Sem exceções.
Em ambiente real, requer campos de autorização no `scope.yaml`.

**Attack Graph** — grafo dirigido onde nós são estados de comprometimento e
arestas são técnicas executadas. Base do relatório final e de futuras
publicações acadêmicas.

**Audit Logger** — JSONL append-only com timestamp, decisão, ação, resultado
e raciocínio do Planner para cada step.

---

## Escopo e autorização

Rastro só executa ações dentro do escopo definido. Em ambiente real,
o `scope.yaml` exige autorização explícita:

```yaml
aws_account_ids:
  - "123456789012"
allowed_services:
  - iam
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
| 1 | LLM Planner real + MITRE mapping + Tool Registry | em progresso |
| 2 | AWS real (conta de lab autorizada) | pendente |
| 3 | Kubernetes attack paths | pendente |
| 4 | Linux + ambiente híbrido | pendente |
| 5 | v1.0 + dataset público + Neo4j | pendente |

---

## Cobertura MITRE ATT&CK (planejada)

| Técnica | ID | Fase | Alvo |
|---------|-----|------|------|
| Account Discovery | T1087.004 | Discovery | AWS IAM |
| Permission Groups Discovery | T1069.003 | Discovery | IAM policies |
| Abuse Elevation Control — PassRole | T1548 | Priv. Escalation | AWS |
| Create/Modify Cloud Credentials | T1098.001 | Persistence | AWS |
| Valid Accounts — Cloud | T1078.004 | Initial Access | AWS |
| Data from Cloud Storage | T1530 | Collection | S3 |
| Container Escape | T1611 | Priv. Escalation | Kubernetes |
| Lateral Movement via SSM | T1021 | Lateral Movement | EC2 |

---

## Stack

- **Python 3.12** — ecossistema de segurança ofensiva (boto3, impacket,
  kubernetes-client, nuclei-python)
- **Claude API** — Planner LLM com tool use estruturado (Fase 1)
- **networkx** — attack graph em memória; Neo4j na v1.0
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
