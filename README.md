# Rastro

> O problema da segurança em cloud não é detectar risco.
> É entender quais riscos se conectam em um caminho real de comprometimento —
> e fazer isso na mesma velocidade que um atacante moderno.

**Rastro** é um engine de simulação adversarial autônoma para ambientes cloud.
Não lista vulnerabilidades — raciocina sobre elas, as encadeia, e prova o
caminho completo de comprometimento com evidência auditável em cada passo.

> ⚠️ **Estado atual:** pesquisa e desenvolvimento de engine. Não existe CLI,
> runner, produto, ou interface de usuário. O que existe é o engine central
> sendo validado experimentalmente — loop de raciocínio, backtracking,
> path scoring, e execução controlada em AWS real. Tudo ainda é invocado
> diretamente via Python. Contribuições e discussões são bem-vindas, mas
> expectativas de produto pronto não se aplicam ainda.

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

O engine central está funcional e sendo validado em ambiente AWS de laboratório
autorizado. O que foi construído e provado até agora:

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

**Backends de LLM plugáveis:**
Ollama self-hosted (padrão), OpenAI-compatible, Anthropic, mock determinístico.

**15 experimentos documentados** com hipótese, metodologia, resultado e
implicações arquiteturais — incluindo resultados negativos.

---

## O que não existe ainda

Para ser explícito sobre o que este repositório **não é**:

- Sem CLI de usuário final
- Sem runner containerizado
- Sem interface gráfica ou dashboard
- Sem produto SaaS ou API hospedada
- Sem onboarding automatizado de conta AWS
- Sem documentação de usuário final
- Sem suporte a Kubernetes (apenas AWS, apenas IAM/S3/Secrets Manager/SSM)
- Sem cobertura de Linux ou ambiente híbrido

O que existe é o engine sendo validado em laboratório. A distância entre
isso e um produto utilizável é substancial e intencional — qualidade do
engine antes de qualquer camada de produto.

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

Não existe CLI. A invocação é direta via Python. Isso é intencional
enquanto o engine está sendo validado — a interface de usuário vem depois.

```bash
git clone https://github.com/PydaVi/rastro
cd rastro

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Mock planner — sem LLM, sem AWS:**

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

15 experimentos concluídos em `docs/experiments/` — de validação do loop
real em AWS até backtracking com roles concorrentes em Secrets Manager.

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
