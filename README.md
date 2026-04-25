# Rastro

> O problema da segurança em cloud não é detectar risco.
> É entender quais riscos se conectam em um caminho real de comprometimento —
> e provar isso com evidência auditável.

**Rastro** é um engine de simulação adversarial autônoma para AWS.
Não lista vulnerabilidades — raciocina sobre o ambiente, formula hipóteses de
encadeamento, testa cada cadeia e prova o caminho completo de comprometimento.

![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Tests](https://img.shields.io/badge/tests-341%20passing-brightgreen)
![Status](https://img.shields.io/badge/status-engine%20R%26D-orange)

---

## O que é

A hipótese central: se ataques se tornam raciocínio automatizado, a defesa
precisa de raciocínio automatizado do mesmo nível.

Não um scanner de misconfigurations. Não um playbook de ataques conhecidos.
Um engine que descobre o ambiente real, raciocina sobre caminhos de ataque
possíveis, e prova o que funciona com mutação real e rollback automático.

### Diferença de abordagem

**CSPM** (Wiz, Prisma) → mostra grafos teóricos, não prova explorabilidade  
**BAS** → testa ataques conhecidos, não raciocina sobre o ambiente  
**Pentest manual** → não escala com a velocidade de mudança do IAM  

**Rastro** → BFS determinístico + LLM opcional raciocinam sobre permissões reais → hipóteses → mutação real → prova auditável

---

## Estado atual

| Bloco | Resultado | O que mudou |
|-------|-----------|-------------|
| Bloco 1 — StrategicPlanner | 6–10 paths identificados/run | LLM entra como estrategista antes das campanhas |
| Bloco 2 — Mutação real | 1/3 campanhas provadas | `iam:AttachRolePolicy` real + rollback automático |
| Bloco 3 — Execução IAM completa | 7/7 campanhas provadas | 3 classes de privesc sem SimulatePrincipalPolicy |
| Bloco 4 — Deep IAM Reasoning | 6/6 campanhas provadas | Policy documents reais; planner raciocina sobre Action/Resource/Condition |
| Bloco 4b/4c — Scoring + Determinismo | 3/3 em conta sem naming convention | Privilege score por blast radius; derived targets sem LLM |
| Bloco 5 — Full Account Scan | 5/5 (100%) | 5 usuários, 0 configuração manual, 0 falhas |
| Bloco 6a — Discovery Multi-Serviço | +15 testes | Secrets, SSM, S3 como entidades de 1ª classe com `readable_by` |
| Bloco 6b — Credential Access Passivo | +12 testes | Entry user lê secret diretamente → `credential_extracted` provado |
| Bloco 6c — Identity Pivot Mid-Chain | +18 testes | Secret → credencial extraída → nova identidade → assume role |
| Bloco 6d — SSM + S3 + CreateAccessKey | 3/3 labs (100%) | Pivot via qualquer fonte de credencial |
| Bloco 7 — Capability Graph | grafo derivado de policy docs | `createkey_by`, `assumable_by`, `mutable_by` computados automaticamente |
| Bloco 8 — Tool Effects Declarativos | zero crescimento do executor | Tool YAML declara `produces:`; executor aplica sem código custom |
| **Bloco 9 — Graph Traversal Hypotheses** | **6/6 chains provadas em AWS real** | **BFS substitui funções `_derive_*` hardcoded; hipóteses determinísticas independentes de LLM** |

### Capacidade atual

O engine entra em qualquer conta AWS, mapeia a superfície de ataque e prova chains completas:

```
conta AWS → discovery autônomo → capability graph (BFS sobre policy docs)
  → hipóteses determinísticas (+ enriquecimento LLM opcional)
    → mutação real → prova auditável → rollback automático
```

#### Classes de ataque provadas em AWS real

**IAM PrivEsc:**
- `iam:CreatePolicyVersion` — cria versão admin em customer-managed policy
- `iam:AttachRolePolicy` — anexa AdministratorAccess a role alvo
- `sts:AssumeRole` — role chaining até role privilegiado
- `iam:PassRole` — passa role para serviço com execução privilegiada

**Identity pivot via fonte de credencial:**
- Secrets Manager → credencial extraída do JSON do secret → assume role
- SSM Parameter → credencial extraída do valor do parâmetro → assume role
- S3 Object → credencial extraída do conteúdo do objeto → assume role
- `iam:CreateAccessKey` em user alvo → nova identidade → assume role (com rollback da key)

### Demonstração: acme_showcase — 6 chains simultâneos

Lab com 5 entry identities e 6 vetores de ataque distintos, todos convergindo em `acme-admin-role`:

```
acme-cicd-agent    → iam:AttachRolePolicy(acme-ops-role)       → provado  [PrivEsc]
acme-cicd-agent    → iam:CreatePolicyVersion(acme-cicd-ops-policy) → provado  [PrivEsc]
acme-log-collector → secretsmanager:GetSecretValue             → deploy-svc creds → provado  [Secret pivot]
acme-batch-runner  → s3:GetObject(internal/svc-creds.json)     → ops-agent creds  → provado  [S3 pivot]
acme-param-reader  → ssm:GetParameter(/acme/prod/deploy-key)   → api-relay creds  → provado  [SSM pivot]
acme-health-probe  → iam:CreateAccessKey(acme-deploy-svc)      → deploy-svc creds → provado  [CreateKey pivot]
```

Zero configuração de alvos ou fixtures — o engine descobriu e provou todos os 6 paths
partindo apenas das credenciais dos 5 entry users.

---

## Arquitetura

```
                    ┌─────────────────────────────┐
                    │      CapabilityGraph BFS     │
                    │  (sempre roda, determinístico)│
                    │  can_read / can_assume /      │
                    │  can_mutate / can_create_key  │
                    └──────────────┬──────────────┘
                                   │ hipóteses det.
                    ┌──────────────▼──────────────┐
                    │     StrategicPlanner (LLM)   │
                    │  (opcional — enriquece BFS)  │
                    │  OpenAI / Ollama / Mock       │
                    └──────────────┬──────────────┘
                                   │ hipóteses merged
                    ┌──────────────▼──────────────┐
                    │         RASTRO CORE          │
                    │                              │
                    │  Planner ──▶ Tool Executor   │
                    │      ▲           │           │
                    │      │           ▼           │
                    │  Attack Graph ◀ Tool Registry│
                    │  + Candidate Paths           │
                    │  + Branch Memory             │
                    │  + Rollback Tracker          │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                     ▼
       Report Engine         Scope Enforcer        Audit Logger
     (MD + JSON + HTML)       (obrigatório)        (append-only)
```

O LLM é componente opcional de enriquecimento — não o orquestrador. Nenhuma lógica de
controle ou segurança depende do modelo de linguagem. O BFS determinístico sempre roda
e já é suficiente para provar a maioria dos chains.

### Discovery enriquecido

O snapshot de discovery contém documentos reais de policy por principal:

```json
{
  "resource_type": "identity.user",
  "identifier": "arn:aws:iam::ACCOUNT:user/acme-cicd-agent",
  "metadata": {
    "policy_permissions": [
      {
        "source": "inline:acme-cicd-agent-privesc",
        "statements": [
          {"Effect": "Allow", "Action": "iam:AttachRolePolicy", "Resource": "arn:aws:iam::ACCOUNT:role/acme-ops-role"}
        ]
      }
    ]
  }
}
```

E recursos de dados expõem quem pode acessá-los (Capability Graph):

```json
{
  "resource_type": "secret.secrets_manager",
  "identifier": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:acme/svc/deploy-creds",
  "metadata": {
    "readable_by": ["arn:aws:iam::ACCOUNT:user/acme-log-collector"]
  }
}
```

---

## Como executar

```bash
git clone https://github.com/PydaVi/rastro
cd rastro
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Testes (sem LLM, sem AWS):**

```bash
pytest                 # 341 testes, sem dependências externas
pytest -m integration  # requer AWS ou Ollama
```

**Assessment discovery-driven:**

```bash
RASTRO_ENABLE_AWS_REAL=1 python -m app.main assessment run \
  --bundle aws-iam-heavy \
  --target examples/target_acme_showcase.json \
  --authorization examples/authorization_aws_blind_real_iamheavy.json \
  --out outputs \
  --max-steps 10 \
  --discovery-driven
```

---

## Autorização

Rastro só executa dentro do escopo definido. Em ambiente real, o scope exige
autorização explícita documentada — sem isso, o run não inicia:

```yaml
aws_account_ids:
  - "123456789012"
allowed_services: [iam, sts, s3, secretsmanager]
authorized_by: "nome completo"
authorized_at: "2026-01-01"
authorization_document: "docs/authorization.pdf"
```

**Não execute Rastro em ambientes sem autorização explícita do dono.**

---

## Roadmap

| Bloco | Objetivo | Estado |
|-------|----------|--------|
| ~~1 — StrategicPlanner~~ | ~~LLM raciocina antes de gerar campanhas~~ | DONE |
| ~~2 — Mutação real~~ | ~~Prova paths com iam:AttachRolePolicy real~~ | DONE |
| ~~3 — IAM completo~~ | ~~3 classes de privesc provadas em AWS real~~ | DONE |
| ~~4 — Deep IAM Reasoning~~ | ~~Policy documents reais no discovery~~ | DONE |
| ~~5 — Full Account Scan~~ | ~~5/5 campanhas, 5 usuários, 0 configuração manual~~ | DONE |
| ~~6 — Chains multi-serviço~~ | ~~Secrets, SSM, S3, CreateAccessKey como elos de pivot~~ | DONE |
| ~~7 — Capability Graph~~ | ~~Discovery computa grafo de capacidades sem anotação manual~~ | DONE |
| ~~8 — Tool Effects Declarativos~~ | ~~Tool YAML declara o que produz; executor para de crescer~~ | DONE |
| ~~9 — Graph Traversal Hypotheses~~ | ~~BFS substitui zoo de funções `_derive_*` hardcoded~~ | DONE |
| **10 — Execução por Caminho** | Executor segue paths do grafo; profile deixa de ser repositório de ataque | próximo |

O objetivo do Bloco 10 é um engine verdadeiramente guiado por grafo: dado qualquer ambiente AWS,
entra, constrói o grafo, encontra caminhos por traversal e executa cada aresta como uma ação —
sem adaptação de código para cada novo cenário de ataque.

---

## O que não existe ainda

- Binário instalado `rastro ...` — CLI via Python por ora
- Onboarding automatizado de conta AWS
- Suporte a Kubernetes (AWS first)
- Produto 02 (attack path em CI/CD) — aguarda maturidade do Produto 01

---

## Contribuindo

Leia o [PLAN.md](PLAN.md) para o estado atual e direção,
e o [AGENTS.md](AGENTS.md) para o contrato de desenvolvimento.

O foco atual é o **Bloco 10**: fazer o executor seguir diretamente os caminhos
do grafo de capacidades, eliminando a dependência de profiles de ataque como
repositórios de lógica hardcoded.

---

## Licença

[Apache 2.0](LICENSE)

*Use Rastro somente em ambientes com autorização explícita.*
