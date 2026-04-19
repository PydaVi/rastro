# Rastro

> O problema da segurança em cloud não é detectar risco.
> É entender quais riscos se conectam em um caminho real de comprometimento —
> e provar isso com evidência auditável.

**Rastro** é um engine de simulação adversarial autônoma para AWS.
Não lista vulnerabilidades — raciocina sobre o ambiente, formula hipóteses de
encadeamento, testa cada cadeia e prova o caminho completo de comprometimento.

![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Tests](https://img.shields.io/badge/tests-288%20passing-brightgreen)
![Campaigns](https://img.shields.io/badge/campaigns%20proved-20%2F20%20(100%25)-brightgreen)
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

**Rastro** → LLM raciocina sobre permissões reais → hipóteses → mutação real → prova auditável

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
| **Bloco 6d — SSM + S3 + CreateAccessKey** | **3/3 labs (100%)** | **Pivot via qualquer fonte de credencial** |

### Capacidade atual

O engine entra em qualquer conta AWS, mapeia a superfície de ataque e prova chains completas:

```
conta AWS → discovery autônomo → privilege scoring por blast radius
  → hipóteses por entrada (LLM + determinístico)
    → mutação real → prova auditável → rollback automático
```

#### Classes de privesc provadas em AWS real

**IAM direto:**
- `iam:CreatePolicyVersion` — cria versão admin em customer-managed policy
- `iam:AttachRolePolicy` — anexa AdministratorAccess a role alvo
- `sts:AssumeRole` — role chaining até role privilegiado
- `iam:PassRole` — passa role para serviço com execução privilegiada

**Identity pivot via fonte de credencial:**
- Secrets Manager → credencial extraída do JSON do secret → assume role
- SSM Parameter → credencial extraída do valor do parâmetro → assume role
- S3 Object → credencial extraída do conteúdo do objeto → assume role
- `iam:CreateAccessKey` em user alvo → nova identidade → assume role (com rollback da key)

### Demonstração: Full Account Scan

5 usuários, conta empresarial simulada (sem naming conventions), zero configuração manual de alvos:

```
ops-deploy-user    → platform-admin-role (3 vetores: role-chain, attach, create-policy-version)
data-engineer-user → data-pipeline-role  (role-chaining)
readonly-audit-user → audit-readonly-role (role-chaining)
```

O engine selecionou `platform-admin-role` (score 8400, `iam:*`) como alvo principal
sem nenhuma dica de naming convention — apenas pelo blast radius real das permissões.

### Demonstração: Identity Pivot Chain

Chain de 2 passos provada em AWS real:

```
asset-manifest-user
  → s3:GetObject (mesh-artifacts/bootstrap.json) [credencial extraída]
    → extracted://bootstrap.json
      → sts:AssumeRole → delivery-broker-role  [objetivo alcançado]
```

---

## Arquitetura

```
                    ┌─────────────────────────────┐
                    │      StrategicPlanner        │
                    │  (OpenAI / Ollama / Mock)    │
                    │  raciocina sobre policy docs │
                    │  → AttackHypotheses          │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │         RASTRO CORE          │
                    │                              │
                    │  Planner ──▶ Tool Executor   │
                    │  (LLM executa hipóteses)     │
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

O LLM é componente de raciocínio — não o orquestrador. Nenhuma lógica de
controle ou segurança depende do modelo de linguagem.

### Discovery enriquecido

O snapshot de discovery contém documentos reais de policy por principal:

```json
{
  "resource_type": "identity.user",
  "identifier": "arn:aws:iam::ACCOUNT:user/ops-deploy-user",
  "metadata": {
    "policy_permissions": [
      {
        "source": "DeployPolicy",
        "statements": [
          {"Effect": "Allow", "Action": "iam:AttachRolePolicy", "Resource": "*"}
        ]
      }
    ]
  }
}
```

E recursos de dados expõem quem pode acessá-los:

```json
{
  "resource_type": "secret.ssm_parameter",
  "identifier": "arn:aws:ssm:us-east-1:ACCOUNT:parameter/svc/runtime/bootstrap",
  "metadata": {
    "readable_by": ["arn:aws:iam::ACCOUNT:user/queue-indexer-user"]
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
pytest                 # 288 testes, sem dependências externas
pytest -m integration  # requer AWS ou Ollama
```

**Assessment discovery-driven:**

```bash
RASTRO_ENABLE_AWS_REAL=1 python -m app.main assessment run \
  --bundle aws-iam-heavy \
  --target examples/target_aws_foundation.local.json \
  --authorization examples/authorization_aws_foundation.local.json \
  --out outputs \
  --max-steps 9 \
  --discovery-driven
```

**CLI operacional:**

```bash
python -m app.main profile list
python -m app.main target validate --target examples/target_aws_foundation.local.json
python -m app.main preflight validate --scope examples/scope_aws_role_choice_openai.json
python -m app.main discovery run --scope ...
python -m app.main assessment run --bundle aws-iam-heavy --discovery-driven ...
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
| **7 — Capability Graph** | Discovery computa grafo de capacidades sem anotação manual | próximo |
| 8 — Tool Effects Declarativos | Tool YAML declara o que produz; executor para de crescer | planejado |
| 9 — Graph Traversal Hypotheses | BFS substitui zoo de funções `_derive_*` hardcoded | planejado |
| 10 — Execução por Caminho | Executor segue paths; profile deixa de ser repositório de ataque | planejado |

O objetivo dos Blocos 7–10 é um engine verdadeiramente cego: dado qualquer ambiente AWS,
entra, constrói o grafo, encontra caminhos por traversal e executa — sem adaptação de código
para cada novo cenário.

---

## O que não existe ainda

- Binário instalado `rastro ...` — CLI via Python por ora
- Interface gráfica ou dashboard
- Produto SaaS ou API hospedada
- Onboarding automatizado de conta AWS
- Suporte a Kubernetes (AWS first)
- Produto 02 (attack path em CI/CD) — aguarda maturidade do Produto 01

---

## Contribuindo

Leia o [PLAN.md](PLAN.md) para o estado atual e direção,
e o [AGENTS.md](AGENTS.md) para o contrato de desenvolvimento.

O foco atual é o **Bloco 7**: fazer o discovery computar automaticamente o grafo
de capacidades (quem pode fazer o quê sobre cada recurso) a partir dos documentos
de policy IAM reais — eliminando a necessidade de anotação manual de fixtures.

---

## Licença

[Apache 2.0](LICENSE)

*Use Rastro somente em ambientes com autorização explícita.*
