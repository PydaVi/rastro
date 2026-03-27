# PLAN.md — Rastro

Rastro é um agente de red team autônomo para ambientes cloud e Linux.
Não lista vulnerabilidades — raciocina sobre elas, as encadeia, e constrói
o caminho completo de comprometimento.

Este documento é o plano de desenvolvimento vivo do projeto.
Atualizado a cada fase concluída.

---

## Estado atual

**Fase 0 — COMPLETA**

O loop central funciona. O MVP sintético prova que a arquitetura é viável:
o agente enumera um ambiente IAM, seleciona ações, passa pelo Scope Enforcer,
executa, atualiza o attack graph, e produz relatório auditável.

O que foi construído:
- Loop bounded: `enumerate → plan → validate → execute → observe → graph`
- Planner interface abstraída (mock determinístico no MVP, LLM plugável na Fase 1)
- Scope Enforcer obrigatório — nenhuma ação executa sem validação
- Audit Logger append-only JSONL
- Attack Graph em networkx com export Mermaid
- Report Engine: Markdown + JSON estruturado
- CLI: `rastro run --fixture ... --objective ... --scope ...`
- Fixture sintético IAM com caminho de escalada determinístico
- Suite de testes com pytest, sem dependências externas

O que não foi construído ainda (intencionalmente):
- LLM real no Planner
- Ferramentas ofensivas reais (boto3, nmap, nuclei)
- Acesso a ambientes reais
- MITRE ATT&CK mapping no relatório

---

## Fase 1 — LLM Planner + MITRE Mapping

**Pré-requisito:** Fase 0 completa. ✓

**Objetivo:** Substituir o mock planner por um agente LLM real. O agente passa
a raciocinar sobre o estado do ataque em vez de seguir uma sequência
determinística.

### Decisão de design: nenhum vendor obrigatório

Rastro é open source. Depender de uma API proprietária como requisito cria
barreira de entrada, gera custo para contribuidores, e viola o princípio de
soberania operacional — especialmente relevante para uso em ambientes sensíveis
onde mandar contexto de ataque para uma API externa é inaceitável.

O backend de LLM é configurável via `scope.yaml`. O padrão recomendado é
**Ollama** (self-hosted, sem internet, sem custo). APIs externas são suportadas
como opção, nunca como requisito.

```
src/planner/
  interface.py           # contrato estável — não muda
  mock_planner.py        # determinístico — já existe, para testes
  ollama_planner.py      # padrão recomendado — self-hosted
  openai_planner.py      # compatível com qualquer API OpenAI-like
  claude_planner.py      # Anthropic API — opcional
```

Qualquer modelo rodando via Ollama funciona: Llama 3.1, Qwen2.5, Mistral,
Phi-3. Para ambientes air-gapped ou pentests em infraestrutura sensível,
Ollama local é a única opção que faz sentido operacionalmente.

Configuração no `scope.yaml`:

```yaml
planner:
  backend: ollama          # ollama | openai | claude
  model: llama3.1:8b       # qualquer modelo suportado pelo backend
  base_url: http://localhost:11434  # para ollama
  # api_key: $ENV_VAR      # para backends externos — nunca hardcoded
```

---

### 1.1 — Ollama Planner (padrão)

Implementar `ollama_planner.py` usando a API REST do Ollama
(`/api/chat` com `stream: false`). O Planner recebe:

- Estado atual do attack graph serializado
- Ações disponíveis com pré-condições
- Objetivo da sessão
- Histórico de decisões anteriores (últimos N steps)

E retorna uma `Decision` com:
- Ação escolhida (estruturada — não texto livre)
- Raciocínio explícito no campo `reason`

O output do LLM é JSON estruturado. O Planner valida o schema antes de
retornar — se o LLM alucinar um formato inválido, o step é abortado com
log de erro, não com execução de ação incorreta.

DONE WHEN:
- `rastro run --planner ollama` executa com Ollama local
- Raciocínio do LLM aparece no audit log e no relatório
- Mock planner continua funcionando para testes sem Ollama instalado

---

### 1.2 — OpenAI-compatible Planner

Implementar `openai_planner.py` usando o SDK `openai` com `base_url`
configurável. Funciona com: OpenAI, Groq, Together AI, Mistral API,
e qualquer provider com API OpenAI-compatible.

DONE WHEN:
- `rastro run --planner openai` funciona com `OPENAI_API_KEY` no ambiente
- Mesma interface, mesmo comportamento esperado do Ollama Planner

---

### 1.3 — Claude Planner (opcional)

Implementar `claude_planner.py` para quem preferir usar Anthropic API.
Não é o padrão, não é recomendado para ambientes sensíveis.

DONE WHEN:
- `rastro run --planner claude` funciona com `ANTHROPIC_API_KEY` no ambiente

---

### 1.4 — MITRE ATT&CK Mapping

Cada técnica no Tool Registry precisa de mapeamento explícito para MITRE
ATT&CK Cloud Matrix. Isso é o que dá credibilidade ao relatório e base para
publicação acadêmica.

Adicionar ao domain model:

```python
class Technique(BaseModel):
    mitre_id: str        # ex: T1548
    mitre_name: str      # ex: Abuse Elevation Control
    tactic: str          # ex: privilege-escalation
    platform: str        # ex: AWS
```

Relatório passa a incluir seção MITRE com técnicas usadas, IDs e links
para a base de conhecimento oficial.

DONE WHEN:
- Todas as ações do MVP têm `Technique` associada
- Relatório Markdown inclui tabela MITRE
- JSON output inclui campo `mitre_techniques`

---

### 1.5 — Tool Registry (base)

Formalizar o conceito de Tool como plugin declarativo. Cada tool tem:

```yaml
# tools/aws/iam_passrole.yaml
name: iam_passrole
description: Attempt privilege escalation via iam:PassRole
phase: privilege-escalation
mitre_id: T1548
platform: AWS
preconditions:
  - aws_credentials_valid
  - iam_passrole_permission_exists
postconditions:
  - elevated_role_assumed
implementation: tools/aws/iam_passrole.py
safe_simulation: true
```

O Planner usa pré/pós-condições para raciocinar sobre qual tool chamar —
não prompt livre. Comportamento previsível e auditável independente do
backend de LLM.

DONE WHEN:
- 3 tools AWS declaradas em YAML com MITRE mapping
- Planner seleciona tools por pré-condições
- Fixture sintético atualizado para refletir estrutura de tools

---

**Fase 1 completa quando:**
1. `rastro run --planner ollama` executa com LLM local
2. `rastro run --planner openai` executa com API externa
3. Relatório inclui raciocínio do agente + mapping MITRE
4. Tool Registry tem estrutura YAML funcional
5. Todos os testes da Fase 0 continuam passando sem Ollama instalado

---

## Fase 2 — AWS Real (ambiente autorizado)

**Pré-requisito:** Fase 1 completa.

**Objetivo:** Primeiro contato com infraestrutura real. O agente deixa de operar
em fixture sintético e passa a chamar AWS APIs reais — sempre dentro do escopo
definido, sempre com autorização documentada.

### Superfície alvo

IAM privilege escalation em conta AWS de laboratório dedicada:

- `iam:GetCallerIdentity` — identidade atual
- `iam:SimulatePrincipalPolicy` — permissões efetivas sem executar ação real
- `iam:PassRole` chains — caminhos de escalada
- `iam:CreatePolicyVersion` — escalada via criação de versão de policy
- `s3:ListBuckets` / `s3:GetObject` — validação de acesso pós-escalada

### Scope Enforcer para ambiente real

O `scope.yaml` passa a incluir campos obrigatórios de autorização:

```yaml
aws_account_ids:
  - "123456789012"
allowed_regions:
  - us-east-1
allowed_services:
  - iam
  - s3
dry_run: false
authorized_by: "nome completo"
authorized_at: "2026-01-01"
authorization_document: "docs/authorization.pdf"
```

Sem `authorized_by` e `authorization_document`, o run não inicia.
Isso está no código, não só aqui.

### Modo dry-run

`--dry-run` planeja o ataque completo sem executar nenhuma ação real.
O Planner raciocina, o grafo é construído, o relatório é gerado —
mas o Executor retorna simulação em vez de chamar a AWS.

DONE WHEN:
- `rastro run --planner ollama --target aws` opera em conta real de lab
- Scope Enforcer bloqueia qualquer ação fora do `scope.yaml`
- Modo `--dry-run` funcional
- Relatório inclui evidências reais (ARNs, timestamps, respostas da API)

---

## Fase 3 — Kubernetes Attack Paths

**Pré-requisito:** Fase 2 completa.

**Objetivo:** Expandir superfície para Kubernetes. O agente raciocina sobre
caminhos de comprometimento em clusters — RBAC abuse, container escape,
kubelet exploitation, lateral movement cloud → cluster.

Integração com `brain-chaos` como cluster de teste
(k3d + ArgoCD + Kyverno + Cilium já configurados).

Técnicas alvo:
- RBAC misconfiguration (T1078.004)
- Container escape via privileged pod (T1611)
- Secrets em etcd / environment variables (T1552.007)
- Lateral movement EC2 → cluster via kubeconfig exposto

DONE WHEN:
- `rastro run --target k8s` opera contra cluster de lab
- Attack graph conecta identidade AWS a recursos Kubernetes
- Primeiro paper submetido baseado em resultados das Fases 2 e 3

---

## Fase 4 — Linux + Ambiente Híbrido

**Pré-requisito:** Fase 3 completa.

Superfície Linux: privilege escalation local, SUID abuse, cron jobs,
sudo misconfiguration. Conectar com cloud: pivot de EC2 para VPC, movimento
via SSM Run Command, secrets em ambiente híbrido on-prem + cloud.

---

## Fase 5 — v1.0 + Dataset Público

Objetivo de longo prazo.

- AWS, GCP, Azure, Kubernetes, Linux — cobertura MITRE completa
- Neo4j substituindo networkx para persistência, Cypher queries e visualização
- Dataset público de attack graphs anonimizados para pesquisa
- Documentação de qualidade para contribuição externa
- Base sólida para submissão a editais FAPESP / GSI / MCTI

---

## Princípios que guiam o desenvolvimento

**Nenhum vendor obrigatório.** O backend de LLM é configurável. Ollama local
é o padrão recomendado. APIs externas são opção, nunca requisito.

**Autorização é inegociável.** Nenhuma execução contra ambiente real acontece
sem `scope.yaml` com campos de autorização preenchidos. Isso está no código.

**A interface do Planner é estável.** Mock, Ollama, OpenAI, ou qualquer
implementação futura plugam na mesma interface. O restante do pipeline não
sabe qual está rodando.

**Cada fase é publicável.** Resultados de cada fase geram material para paper
ou post técnico. O projeto cresce em visibilidade junto com a base de código.

**Testes sem dependências externas.** A suite roda localmente sem AWS, sem LLM,
sem rede. O mock planner cobre o comportamento esperado. LLM real é testado
com mocks que simulam respostas estruturadas.

**Não expandir escopo antes de completar a fase atual.** Cada fase é entregue
completa antes da próxima começar.
