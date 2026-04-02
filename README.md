# Rastro

> O problema da segurança em cloud não é detectar risco.
> É entender quais riscos se conectam em um caminho real de comprometimento —
> e fazer isso na mesma velocidade que um atacante moderno.

**Rastro** é um engine de simulação adversarial autônoma para ambientes cloud.
Não lista vulnerabilidades — raciocina sobre elas, as encadeia, e prova o
caminho completo de comprometimento com evidência auditável em cada passo.

> ⚠️ **Estado atual:** Produto 01 em MVP operacional inicial. O engine central
> já foi validado em AWS real no bundle `aws-foundation`, com CLI básica,
> preflight, campaigns, assessments discovery-driven e artefatos executivos
> iniciais. Ainda não existe produto final, UI, onboarding automatizado,
> nem discovery/target selection maduros para todo o portfólio AWS.
> O foco atual continua sendo maturidade do engine e operacionalização segura.

![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Status](https://img.shields.io/badge/status-engine%20R%26D-red)

---

## O que é

Rastro é uma pesquisa aplicada sobre como construir um agente que raciocina
sobre caminhos de comprometimento em cloud — da mesma forma que um atacante
competente pensaria.

A hipótese central: se ataques se tornam raciocínio automatizado, a defesa
precisa de raciocínio automatizado do mesmo nível. Não um scanner de
misconfigurations. Não um playbook de ataques conhecidos. Um engine que
conhece o ambiente específico, formula hipóteses de encadeamento, testa
cada cadeia, descarta o que não funciona, e prova o que funciona.

Esse engine está sendo construído e validado experimentalmente aqui.

---

## O que já existe

O engine central está funcional, já validado em AWS real autorizado, e o
Produto 01 possui um primeiro corte operacional. O que foi construído e
provado até agora:

**Loop de raciocínio:**
`enumerate → plan → validate → execute → observe → graph`

**Capacidades do engine validadas experimentalmente:**
- candidate path tracking — hipóteses de pivô com status explícito
- branch failure memory — dead-ends marcados, sem revisita inútil
- backtracking estruturado — retorno ao ponto de decisão após falha
- action shaping — policy layer antes do LLM que organiza o espaço de busca
- path scoring com lookahead — priorização de candidatos por valor esperado

**Infraestrutura de controle:**
- Scope Enforcer obrigatório em cada ação — sem bypass
- Audit Logger append-only por step com raciocínio do planner
- Artefatos sanitizados automáticos para compartilhamento seguro
- Autorização explícita documentada obrigatória para execução real
- Preflight obrigatório antes do loop em AWS real

**Camada operacional inicial (Produto 01):**
- CLI básica via `python -m app.main`
- `profile list`
- `target validate`
- `preflight validate`
- `campaign run`
- `assessment run`
- `assessment run --discovery-driven`

**Pipeline discovery-driven já implementado:**
- `discovery run`
- `target-selection run`
- `campaign-synthesis run`
- geração automática de campaigns a partir do ambiente descoberto

**Saída técnica e executiva inicial:**
- `report.json` e `report.md` por run
- `assessment.json` e `assessment.md`
- `assessment_findings.json` e `assessment_findings.md`
- grafo de ataque em HTML interativo

**Backends de LLM plugáveis:**
Ollama self-hosted (padrão), OpenAI-compatible, Anthropic, mock determinístico.

**32 experimentos documentados** com hipótese, metodologia, resultado e
implicações arquiteturais — incluindo resultados negativos.

---

## O que não existe ainda

Para ser explícito sobre o que este repositório **não é**:

- Sem binário instalado tipo `rastro ...` — a CLI atual ainda roda via Python
- Sem runner containerizado
- Sem interface gráfica ou dashboard
- Sem produto SaaS ou API hospedada
- Sem onboarding automatizado de conta AWS
- Sem documentação de usuário final madura
- Sem suporte a Kubernetes (apenas AWS)
- Sem cobertura de Linux ou ambiente híbrido

O que existe hoje é um MVP técnico-operacional do Produto 01. A distância
entre isso e um produto pronto para cliente ainda existe, mas a camada
operacional básica já começou e o `aws-foundation` já roda ponta a ponta.

---

## Por que este problema importa

As abordagens atuais de segurança em cloud têm limitações estruturais:

**Pentest** não escala com cloud. IAM é combinatório. Policies, roles e
trust relationships criam uma explosão de caminhos que nenhum humano mapeia
manualmente com a frequência que o ambiente muda.

**BAS (Breach and Attack Simulation)** testa ataques conhecidos — mas não
raciocina sobre o ambiente específico do cliente. Não descobre o que nenhuma
assinatura conhece.

**CSPM** (Wiz, Prisma, CrowdStrike) mostra grafos teóricos mas não prova que
o caminho é realmente explorável. Um finding de "role com permissões excessivas"
fica na fila indefinidamente porque parece abstrato — sem evidência de impacto
real.

O espaço que o Rastro investiga:
**raciocínio autônomo + execução validada + cloud-native + auditável.**

---

## Como executar (desenvolvimento)

A CLI atual ainda é invocada via Python. Isso é intencional neste estágio
do MVP enquanto o contrato operacional estabiliza.

```bash
git clone https://github.com/PydaVi/rastro
cd rastro

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Run individual — mock planner, sem LLM, sem AWS:**

```bash
python -m app.main \
  --fixture fixtures/iam_lab.json \
  --objective examples/objective.json \
  --scope examples/scope.json \
  --out outputs \
  --max-steps 5
```

**Ollama local** (requer `ollama serve` rodando):

```bash
python -m app.main \
  --fixture fixtures/iam_lab.json \
  --objective examples/objective.json \
  --scope examples/scope_ollama.json \
  --out outputs
```

**AWS dry-run** (sem chamadas reais):

```bash
python -m app.main \
  --fixture fixtures/aws_dry_run_lab.json \
  --objective examples/objective_aws_dry_run.json \
  --scope examples/scope_aws_dry_run.json \
  --out outputs
```

**AWS real** (requer credenciais e autorização explícita documentada):

```bash
pip install -e ".[aws]"

RASTRO_ENABLE_AWS_REAL=1 python -m app.main \
  --fixture fixtures/aws_dry_run_lab.json \
  --objective examples/objective_aws_dry_run.json \
  --scope examples/scope_aws_real.json \
  --out outputs
```

**Testes:**

```bash
pytest                    # suite padrão — sem dependências externas
pytest -m integration     # requer AWS ou Ollama
```

**CLI operacional atual:**

```bash
python -m app.main profile list
python -m app.main target validate --target examples/target_aws_foundation.local.json
python -m app.main preflight validate --scope examples/scope_aws_role_choice_openai.json
```

**Assessment discovery-driven do foundation:**

```bash
RASTRO_ENABLE_AWS_REAL=1 python -m app.main assessment run \
  --bundle aws-foundation \
  --target examples/target_aws_foundation.local.json \
  --authorization examples/authorization_aws_foundation.local.json \
  --out outputs_assessment_aws_foundation_discovery_openai \
  --max-steps 9 \
  --discovery-driven
```

---

## Autorização

Rastro só executa dentro do escopo definido. Em ambiente real, o `scope.yaml`
exige autorização explícita — sem isso, o run não inicia:

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

O projeto segue metodologia científica — cada experimento tem hipótese,
metodologia, resultado e implicações arquiteturais. Resultados negativos
têm a mesma obrigatoriedade de documentação que positivos.

32 experimentos concluídos em `docs/experiments/` — do loop real em AWS
até discovery-driven assessment em ambientes sintéticos maiores.

---

## Arquitetura do engine

```
┌──────────────────────────────────────────────────────┐
│                    RASTRO CORE                        │
│                                                       │
│   Planner ─────────────────▶ Tool Executor            │
│   (ollama/openai/mock)       (scope-gated)            │
│       ▲                           │                   │
│       │ estado enriquecido        ▼                   │
│   Attack Graph ◀──────────── Tool Registry            │
│   + Candidate Paths           (YAML plugins)          │
│   + Branch Memory                                     │
│   + Path Scoring                                      │
└──────────────────────────────────────────────────────┘
              │
              ▼
   Report Engine      Scope Enforcer      Audit Logger
   (MD + JSON + HTML)  (obrigatório)      (append-only)
```

O LLM é um componente de raciocínio — não o orquestrador. O engine controla
o loop, rastreia hipóteses, aplica política de busca, e executa backtracking.
Nenhuma lógica de segurança depende do modelo de linguagem.

---

## Contribuindo

Leia o [PLAN.md](PLAN.md) para entender o estado atual e a direção,
e o [AGENTS.md](AGENTS.md) para o contrato de desenvolvimento.

Issues e discussões técnicas são bem-vindas. O foco atual é validação
de engine em AWS — contribuições alinhadas com isso têm mais chance
de serem incorporadas.

---

## Licença

[Apache 2.0](LICENSE)

*Use Rastro somente em ambientes que você tem autorização explícita para testar.*
