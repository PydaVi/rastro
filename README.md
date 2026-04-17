# Rastro

> O problema da segurança em cloud não é detectar risco.
> É entender quais riscos se conectam em um caminho real de comprometimento —
> e provar isso com evidência auditável.

**Rastro** é um engine de simulação adversarial autônoma para AWS.
Não lista vulnerabilidades — raciocina sobre o ambiente, formula hipóteses de
encadeamento, testa cada cadeia e prova o caminho completo de comprometimento.

![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Tests](https://img.shields.io/badge/tests-211%20passing-brightgreen)
![Status](https://img.shields.io/badge/status-engine%20R%26D-orange)

---

## O que é

A hipótese central: se ataques se tornam raciocínio automatizado, a defesa
precisa de raciocínio automatizado do mesmo nível.

Não um scanner de misconfigurations. Não um playbook de ataques conhecidos.
Um engine que descobre o ambiente real, raciocina sobre caminhos de ataque
possíveis, e prova o que funciona.

### Diferença de abordagem

**CSPM** (Wiz, Prisma) → mostra grafos teóricos, não prova explorabilidade  
**BAS** → testa ataques conhecidos, não raciocina sobre o ambiente  
**Pentest manual** → não escala com a velocidade de mudança do IAM  

**Rastro** → LLM raciocina sobre o ambiente real → hipóteses → validação → prova

---

## Estado atual

O engine possui duas camadas funcionais:

### Camada estratégica — `StrategicPlanner` (Bloco 1, operacional)

O LLM entra como **estrategista** antes de gerar campanhas:

```
Discovery → LLM raciocina → AttackHypotheses → Campaigns → LLM executa
```

`AttackHypothesis` captura: entry identity, target, attack class (iam_privesc,
role_chain, credential_access...), sequência de passos, confidence e reasoning.

Backends disponíveis: `OpenAICompatibleStrategicPlanner` (OpenAI, Ollama, qualquer
OpenAI-compatible), `MockStrategicPlanner` para testes offline.

### Camada de execução — engine core (validado em AWS real)

Loop: `enumerate → plan → validate → execute → observe → graph`

- **candidate path tracking** — hipóteses de pivô com status explícito
- **branch failure memory** — dead-ends marcados, sem revisita
- **backtracking estruturado** — retorno ao ponto de decisão após falha
- **action shaping** — policy layer antes do LLM
- **path scoring com lookahead** — priorização de candidatos

### Infraestrutura de controle

- Scope Enforcer obrigatório em cada ação — sem bypass possível
- Audit Logger append-only com raciocínio do planner por step
- Artefatos sanitizados automáticos para compartilhamento
- Preflight obrigatório antes de qualquer execução real
- Autorização explícita documentada obrigatória

---

## Diagnóstico honesto

Benchmark contra [iam-vulnerable](https://github.com/BishopFox/iam-vulnerable)
(31 paths de privilege escalation conhecidos):

**Bloco 1 (StrategicPlanner) — concluído:**

- gpt-4o identifica 6–10 paths de privesc IAM por run, diretamente do discovery
- Exemplo: vê `attached_policy_names: ["privesc1-CreateNewPolicyVersion"]` → infere
  `iam:CreatePolicyVersion` → hipótese estruturada com `attack_steps` e `reasoning`
- 0 campanhas provaram o path — o executor ainda não muta estado (simula via policy)

**Próximo (Bloco 2):** ação de mutação IAM real — chamar `iam:AttachRolePolicy`,
verificar escalada, fazer rollback. O que fecha a cadeia de comprometimento com evidência.

---

## Como executar

```bash
git clone https://github.com/PydaVi/rastro
cd rastro
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Mock — sem LLM, sem AWS:**

```bash
python -m app.main \
  --fixture fixtures/iam_lab.json \
  --objective examples/objective.json \
  --scope examples/scope.json \
  --out outputs \
  --max-steps 5
```

**Assessment discovery-driven com strategic planner (OpenAI/Ollama):**

```bash
RASTRO_ENABLE_AWS_REAL=1 python -m app.main assessment run \
  --bundle aws-foundation \
  --target examples/target_aws_foundation.local.json \
  --authorization examples/authorization_aws_foundation.local.json \
  --out outputs \
  --max-steps 9 \
  --discovery-driven
```

O `strategic_planner` é configurado via `authorization.json` com `planner_config`
apontando para o backend LLM desejado.

**Testes:**

```bash
pytest                 # suite completa — sem dependências externas (211 testes)
pytest -m integration  # requer AWS ou Ollama
```

**CLI operacional:**

```bash
python -m app.main profile list
python -m app.main target validate --target examples/target_aws_foundation.local.json
python -m app.main preflight validate --scope examples/scope_aws_role_choice_openai.json
python -m app.main discovery run --scope ...
python -m app.main assessment run --bundle aws-foundation ...
python -m app.main assessment run --bundle aws-foundation --discovery-driven ...
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

## Arquitetura

```
                    ┌─────────────────────────────┐
                    │      StrategicPlanner        │
                    │  (OpenAI / Ollama / Mock)    │
                    │  raciocina sobre discovery   │
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
                    │  + Path Scoring              │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                     ▼
       Report Engine         Scope Enforcer        Audit Logger
     (MD + JSON + HTML)       (obrigatório)        (append-only)
```

O LLM é componente de raciocínio — não o orquestrador. Nenhuma lógica de
controle ou segurança depende do modelo de linguagem.

---

## Experimentos documentados

99 experimentos em `docs/experiments/` — do primeiro loop real em AWS até
o benchmark iam-vulnerable. Metodologia científica: hipótese, metodologia,
resultado e implicações arquiteturais. Resultados negativos têm documentação
obrigatória igual aos positivos.

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

O foco atual é o Bloco 2: ação de mutação IAM real para provar paths de privesc
identificados pelo `StrategicPlanner`. Contribuições alinhadas com generalização
ofensiva têm prioridade.

---

## Licença

[Apache 2.0](LICENSE)

*Use Rastro somente em ambientes com autorização explícita.*
