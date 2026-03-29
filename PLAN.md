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
- Planner metadata por step no audit e no report (backend, modelo, raw response quando aplicável)
- Attack Graph em estrutura própria com export Mermaid
- Report Engine: Markdown + JSON estruturado
- CLI: `rastro run --fixture ... --objective ... --scope ...`
- Fixture sintético IAM com caminho de escalada determinístico
- Suite de testes com pytest, sem dependências externas

O que não foi construído ainda (intencionalmente):
- Ferramentas ofensivas reais (boto3, nmap, nuclei)
- Acesso a ambientes reais

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

Status: **completa**

---

### 1.2 — OpenAI-compatible Planner

Implementar `openai_planner.py` usando o SDK `openai` com `base_url`
configurável. Funciona com: OpenAI, Groq, Together AI, Mistral API,
e qualquer provider com API OpenAI-compatible.

DONE WHEN:
- `rastro run --planner openai` funciona com `OPENAI_API_KEY` no ambiente
- Mesma interface, mesmo comportamento esperado do Ollama Planner

Status: **implementada no código; pendente validação end-to-end com credenciais**

---

### 1.3 — Claude Planner (opcional)

Implementar `claude_planner.py` para quem preferir usar Anthropic API.
Não é o padrão, não é recomendado para ambientes sensíveis.

DONE WHEN:
- `rastro run --planner claude` funciona com `ANTHROPIC_API_KEY` no ambiente

Status: **implementada no código; pendente validação end-to-end com credenciais**

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

Status: **completa**

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

Status: **completa**

---

**Fase 1 completa quando:**
1. `rastro run --planner ollama` executa com LLM local
2. `rastro run --planner openai` executa com API externa
3. `rastro run --planner claude` executa com API externa
4. Relatório inclui raciocínio do agente + mapping MITRE
5. Tool Registry tem estrutura YAML funcional
6. Todos os testes da Fase 0 continuam passando sem dependências externas

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

Status atual:
- `target=aws` já valida autorização explícita
- fixture AWS local com ARNs, `sts:GetCallerIdentity`, `iam:ListRoles`, `sts:AssumeRole` e `s3:GetObject` simulados
- `execution_policy` agora aparece no report e no audit
- mismatch entre `fixture`/`objective`/`scope` falha cedo antes do loop
- ambiente dry-run filtra ações por `allowed_services`, `allowed_regions`, `aws_account_ids` e `allowed_resources`
- ambiente dry-run rejeita execução direta fora da política com motivos explícitos de negação
- executor AWS real mínimo implementado para `iam_list_roles`, `iam_passrole` e `s3_read_sensitive`
- execução real ainda é gated por `RASTRO_ENABLE_AWS_REAL=1`
- `boto3` entrou como dependência opcional
- o Path 1 AWS real já foi validado em conta autorizada
- o Path 1 já foi executado com `MockPlanner` e com `OllamaPlanner`
- o Path 2 AWS real, com descoberta intermediária via `s3:ListBucket`, já foi validado com `MockPlanner` e com `OllamaPlanner`
- artefatos sanitizados agora são gerados automaticamente para runs reais

Status: **concluída para o primeiro corte AWS real**

---

## Fase 3 — AWS Attack Paths Reais

**Pré-requisito:** Fase 2 completa. ✓

**Objetivo:** Expandir AWS de um único demo real para múltiplos caminhos
reais de comprometimento, ainda concentrados em IAM, STS e S3.

Base já preparada:
- suporte a `s3_list_bucket` no executor AWS e no dry-run
- fixture e exemplos para um segundo path com descoberta de objetos S3 antes do acesso final
- fixture e exemplos para um terceiro path com múltiplas roles assumíveis,
  role distratora e escolha explícita de pivô

Princípio da fase:
- Rastro não cresce por integração solta de serviço, e sim por
  **attack paths completos**
- cada adição deve ir do ponto de entrada ao objetivo final
- o planner precisa começar a escolher entre mais de um caminho possível
- a partir do Path 3, fica explicito que o engine precisa evoluir de
  planner reativo para um sistema com memoria de branches e recuperacao

DONE WHEN:
- existem múltiplos paths AWS reais auditados
- os paths compartilham a mesma política de execução e o mesmo report
- o planner consegue navegar entre alternativas válidas
- o engine registra hipoteses de pivô concorrentes
- o engine consegue marcar branches como falhos e tentar alternativas
- o engine possui backtracking explicito entre pontos de decisão
- o engine consegue recuperar de uma escolha errada sem cair em loop

Status: **em progresso**

Progresso atual:
- Path 3 em `dry_run` já validado com `MockPlanner`
- Path 3 em `dry_run` já validado com `OllamaPlanner`
- report e Mermaid agora mostram `candidate_roles`, `selected_role`,
  `rejected_roles` e a role distratora como caminho alternativo
- Path 3 em AWS real com MockPlanner: passou
- Path 3 em AWS real com OllamaPlanner (`phi3:mini`): falhou — ver EXP-003
- Path 3 em AWS real com OpenAIPlanner (`gpt-4o-mini`) após action shaping: passou
- engine agora possui: memória de tentativa, guidance de pivô, action shaping
- EXP-004: reavaliar OllamaPlanner após as mesmas mudanças
- EXP-005: backtracking estruturado com candidate path tracking
- Path 4 dry-run com MockPlanner: passou e fecha o objetivo após dead-end
- Path 4 dry-run com OpenAIPlanner: passou e demonstrou backtracking explicito
- Path 4 em AWS real com OpenAIPlanner: passou como validacao end-to-end, sem backtracking obrigatorio no run observado
- Path 4 endurecido para tornar o pivô errado inicialmente mais atraente sem tornar o pivô correto impossível
- ver `docs/path-3-role-choice-learning.md`
- ver `docs/experiments/EXP-003-path3-role-choice.md`
- ver `docs/experiments/EXP-005-backtracking-first-cut.md`

---

## Fase 4 — AWS Novos Objetivos e Superfícies

**Pré-requisito:** Fase 3 completa.

Objetivo: ampliar a cobertura AWS para novos objetivos finais e novos tipos
de recurso, ainda mantendo a lógica de attack paths completos.

Superfícies candidatas:
- Secrets Manager
- SSM Parameter Store
- KMS metadata / policy reasoning
- múltiplos alvos S3 e variação de objetivos de coleta

---

## Fase 5 — AWS Compute e Pivot

**Pré-requisito:** Fase 4 completa.

Objetivo: conectar identidade, permissões e superfícies de execução dentro
da AWS.

Superfícies candidatas:
- Lambda
- EC2
- SSM
- caminhos de pivot dentro da conta autorizada

---

## Fase 6 — AWS Multi-Path Autônomo

**Pré-requisito:** Fase 5 completa.

Objetivo: provar autonomia real em AWS com múltiplos caminhos concorrentes,
comparação entre alternativas e escolha estratégica do melhor encadeamento.

---

## Fase 7 — Maturidade AWS Antes de Expandir

**Pré-requisito:** Fase 6 completa.

Objetivo: estabelecer Rastro como produto interessante em AWS antes de sair
para novas superfícies.

Só depois desta fase faz sentido começar Kubernetes, Linux ou ambiente híbrido.

---

## Fase 8 — Kubernetes Attack Paths

**Pré-requisito:** Fase 7 completa.

Kubernetes só entra depois que AWS já tiver vários paths reais auditados e
o produto provar, em AWS, a tese central de raciocínio sobre caminhos de
comprometimento.

---

## Fase 9 — Linux + Ambiente Híbrido

**Pré-requisito:** Fase 8 completa.

Superfície Linux: privilege escalation local, SUID abuse, cron jobs,
sudo misconfiguration. Conectar com cloud: pivot de EC2 para VPC, movimento
via SSM Run Command, secrets em ambiente híbrido on-prem + cloud.

---

## Fase 10 — v1.0 + Dataset Público

Objetivo de longo prazo.

- AWS profundamente coberta antes da expansão lateral
- Kubernetes e Linux entram sobre base já madura
- Neo4j pode entrar para persistência, Cypher queries e visualização
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
