# Rastro

> O problema da segurança em cloud não é detectar risco.
> É entender quais riscos se conectam em um caminho real de comprometimento —
> e provar isso com evidência auditável.

**Rastro** é um engine de simulação adversarial autônoma para AWS.
Não lista vulnerabilidades — raciocina sobre o ambiente, formula hipóteses de
encadeamento, testa cada cadeia e prova o caminho completo de comprometimento.

![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Tests](https://img.shields.io/badge/tests-224%20passing-brightgreen)
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

Benchmark contra [iam-vulnerable](https://github.com/BishopFox/iam-vulnerable)
(31 paths de privilege escalation conhecidos, conta AWS real):

| Bloco | Resultado | O que mudou |
|-------|-----------|-------------|
| Bloco 1 — StrategicPlanner | 6–10 paths identificados/run | LLM entra como estrategista antes das campanhas |
| Bloco 2 — Mutação real | 1/3 campanhas provadas | `iam:AttachRolePolicy` real + rollback automático |
| Bloco 3 — Execução IAM completa | 7/7 campanhas provadas | 3 classes de privesc com mutação real sem SimulatePrincipalPolicy |
| Bloco 4 — Deep IAM Reasoning | **6/6 campanhas provadas** | Policy documents reais no discovery; planner raciocina sobre Action/Resource/Condition |
| Bloco 4b — Sintese deterministica | 62 hipoteses sem LLM | `derived_attack_targets` pre-computados; recall 100% para principals com permissoes |
| Bloco 4c — Privilege Scoring | Targets por blast radius | Engine ranqueia roles por permissoes reais; elimina dependencia de naming convention |

### Capacidade atual

O engine parte de um IAM user com permissões restritas e prova chains completas:

```
discovery (real AWS) → LLM raciocina sobre policy documents reais
  → AttackHypotheses (entry, target, attack_steps, confidence)
    → campanha gerada → LLM executa → mutação IAM real
      → objetivo provado → rollback automático → finding auditável
```

Classes de privesc provadas em AWS real:
- `iam:CreatePolicyVersion` — cria versão admin em customer-managed policy
- `iam:AttachRolePolicy` — anexa AdministratorAccess a role alvo
- `sts:AssumeRole` — role chaining até role privilegiado
- `iam:PassRole` — passa role para serviço com execução privilegiada

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

### Discovery enriquecido (Bloco 4)

O snapshot de discovery agora contém documentos reais de policy por principal:

```json
{
  "resource_type": "identity.user",
  "identifier": "arn:aws:iam::ACCOUNT:user/privesc1-user",
  "metadata": {
    "policy_permissions": [
      {
        "source": "privesc1-CreateNewPolicyVersion",
        "statements": [
          {"Effect": "Allow", "Action": "iam:CreatePolicyVersion", "Resource": "*"}
        ]
      }
    ]
  }
}
```

O `StrategicPlanner` raciocina sobre `Action/Resource/Condition` reais — não sobre
heurísticas de nome de policy.

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
pytest                 # 224 testes, sem dependências externas
pytest -m integration  # requer AWS ou Ollama
```

**Assessment discovery-driven com strategic planner:**

```bash
RASTRO_ENABLE_AWS_REAL=1 python -m app.main assessment run \
  --bundle aws-iam-heavy \
  --target examples/target_aws_foundation.local.json \
  --authorization examples/authorization_aws_foundation.local.json \
  --out outputs \
  --max-steps 9 \
  --discovery-driven
```

O `strategic_planner` é configurado via `authorization.json` com `planner_config`
apontando para o backend LLM desejado (OpenAI, Ollama, ou qualquer OpenAI-compatible).

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

## Experimentos documentados

Experimentos em `docs/experiments/` — do primeiro loop real em AWS até o
benchmark iam-vulnerable. Metodologia: hipótese, metodologia, resultado e
implicações arquiteturais. Resultados negativos têm documentação igual aos positivos.

---

## Roadmap

| Bloco | Objetivo |
|-------|----------|
| ~~1 — StrategicPlanner~~ | ~~LLM raciocina antes de gerar campanhas~~ |
| ~~2 — Mutação real~~ | ~~Prova paths com iam:AttachRolePolicy real~~ |
| ~~3 — IAM completo~~ | ~~3 classes de privesc provadas em AWS real~~ |
| ~~4 — Deep IAM Reasoning~~ | ~~Policy documents reais no discovery~~ |
| 5 — Entry Points Reais | EC2 SSRF, Lambda env vars, S3 exposto → chain completa |
| 6 — Outros serviços como objetivos | Engine infere chains multi-serviço sem templates |

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

O foco atual é o Bloco 5: privilege scoring recursivo (roles que podem assumir
roles admin herdam score) e entry points reais de internet (EC2 SSRF, Lambda,
S3 exposto) conectados ao IAM reasoning do Bloco 4 para chains completas.
Contribuições alinhadas com generalização ofensiva têm prioridade.

---

## Licença

[Apache 2.0](LICENSE)

*Use Rastro somente em ambientes com autorização explícita.*
