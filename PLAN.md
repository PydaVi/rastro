# PLAN.md — Rastro

Rastro é um engine de simulação adversarial autônoma focado em provar
caminhos reais de comprometimento em ambientes cloud.

Não lista vulnerabilidades — raciocina sobre elas, as encadeia,
e valida o caminho completo com evidência auditável.

Este documento define o roadmap vivo do projeto.

---

## Direção estratégica do produto

Rastro é um **engine central de raciocínio sobre attack paths**, sobre o qual
existem dois produtos:

### Produto 01 — Validação de Exposição (prioridade atual)

Execução controlada em ambiente AWS real autorizado.

Entrega:
- attack paths reais, não teóricos
- evidência auditável (ARNs, timestamps, respostas de API)
- grafo de ataque interativo
- mapping MITRE
- remediação por path

### Produto 02 — Attack Path em CI/CD (futuro próximo)

Simulação de attack paths sobre o estado resultante de IaC (Terraform).

Entrega:
- análise no PR antes do deploy
- bloqueio de merge se houver attack path crítico
- evidência contextualizada na mudança que causou o risco

---

## Ordem estratégica do projeto

1. AWS primeiro
2. profundidade antes de expansão
3. Produto 01 antes do Produto 02
4. Kubernetes entra somente após maturidade AWS

---

## Estado atual

### Fase 0 — completa
Loop central validado com fixture sintético.

### Fase 1 — completa
- OllamaPlanner funcional e validado
- OpenAIPlanner e ClaudePlanner implementados
- Tool Registry YAML com MITRE mapping
- Dry-run completo

### Fase 2 — completa (primeiro corte AWS real)
- Executor AWS real com boto3
- Paths 1 e 2 validados em conta autorizada
- Scope enforcement obrigatório com autorização explícita
- Artefatos sanitizados automáticos

### Fase 3 — em progresso
Multi-branch backtracking validado, path scoring em evolução,
diversificação de attack paths em andamento.

17 experimentos concluídos — ver seção de histórico experimental abaixo.

---

## Histórico experimental — Fase 3

Cada experimento tem documento em `docs/experiments/`.
Resultados negativos têm a mesma obrigatoriedade de documentação
que resultados positivos.

| ID      | Hipótese central                                  | Resultado         |
|---------|---------------------------------------------------|-------------------|
| EXP-001 | Loop real em AWS preserva controles               | confirmada        |
| EXP-002 | Descoberta dinâmica via s3:ListBucket             | confirmada        |
| EXP-003 | Escolha de pivô entre roles concorrentes          | 5 etapas / parcial|
| EXP-004 | OllamaPlanner após action shaping                 | confirmada        |
| EXP-005 | Backtracking estruturado primeiro corte           | confirmada        |
| EXP-006 | Backtracking com 3 pivôs concorrentes             | confirmada        |
| EXP-007 | Permutação de ordem e rótulos                     | confirmada        |
| EXP-008 | Path scoring — primeiro corte                     | parcial           |
| EXP-009 | Path scoring com evidência observada              | parcial           |
| EXP-010 | Path scoring com lookahead signals                | confirmada        |
| EXP-011 | Branch profundo com lookahead                     | confirmada        |
| EXP-012 | Secrets Manager como superfície nova              | confirmada        |
| EXP-013 | Branch profundo em Secrets Manager                | confirmada        |
| EXP-014 | Backtracking em Secrets Manager (dry-run)         | confirmada        |
| EXP-015 | Backtracking em Secrets Manager (AWS real)        | confirmada        |
| EXP-016 | Backtracking com pivô competitivo adicional       | confirmada        |
| EXP-017 | Backtracking em SSM Parameter Store (AWS real)    | confirmada        |
| EXP-018 | Path scoring com evidencia ruidosa               | confirmada        |

Descobertas arquiteturais principais acumuladas:
- problema raiz de escolha de pivô era representação de estado, não modelo
- prompt-only não basta — policy layer antes do LLM é necessária
- cenário semânticamente fácil mascara ausência de backtracking real
- order sensitivity é propriedade do engine, não do modelo
- lookahead-aware scoring resolve order sensitivity no benchmark atual
- simulador precisa diferenciar transições por parameters para suportar
  branch profundo
- ANALYZE no executor real deve ser no-op para não bloquear branch correto
- backtracking permanece robusto com dois pivôs competitivos antes do caminho correto
- backtracking generaliza para SSM quando o toolchain minimo existe

---

# Eixo 1 — AWS (prioridade máxima)

---

## Curto prazo — AWS

### Objetivo
Fechar maturidade do engine como sistema de validação real.

### Prioridades

**1. Path scoring robusto**
- reduzir order sensitivity residual
- ranking consistente de pivôs
- estabilidade sob permutação

**2. Backtracking completo**
- branch memory sólida
- recuperação consistente
- evitar loops e revisitas inúteis

**3. Diversificação de attack paths**
- IAM / STS / S3 / Secrets Manager / SSM
- sempre chains completas, nunca features isoladas
- regra: 2-3 experimentos sintéticos → 1 validação real representativa

**4. Contrato de integração AWS**
- role assumível com trust policy restrita ao ARN do executor
- preflight obrigatório de validação de permissões
- escopo explícito em scope.yaml com autorização documentada
- cleanup: nenhum recurso criado permanece após o run
- após fechar este item, iniciar implementação das camadas operacionais
  (Target/Authorization/Profile/Campaign/Assessment) conforme
  `docs/architecture.md`.

**5. Qualidade do Produto 01**
- relatório técnico e executivo
- remediação por path
- evidência clara e auditável
- artefatos sanitizados prontos para compartilhamento

### Próxima sequência de experimentos

- EXP-016: backtracking em Secrets Manager com pivô competitivo adicional
- EXP-017: SSM Parameter Store — validado em AWS real (concluído)
  sinal novo
- Regra: levar para AWS real apenas o que adicionar sinal novo,
  não repetição operacional
- EXP-018: path scoring sob permutação com evidência ruidosa (concluído)

---

## Médio prazo — AWS

### Objetivo
Transformar o engine em produto utilizável — Produto 01 operacional.

### Prioridades

**1. Padronização operacional**
- onboarding de conta AWS via role cross-account
- execução via credenciais temporárias
- processo repetível e documentado

**2. Runner oficial**
- containerizado
- self-hosted
- independente do ambiente do operador

**3. Ampliação de superfícies (com disciplina)**
- Lambda
- EC2
- SSM
- Parameter Store
- KMS (quando relevante)

**4. Lab AWS oficial**
- bootstrap via IaC
- cenários versionados e reproduzíveis
- regressão de comportamento entre versões

**5. Início controlado do Produto 02**
- parser de `terraform show -json`
- projeção de estado AWS a partir do plan
- sem deploy real

---

## Longo prazo — AWS

### Objetivo
Fechar a tese do Rastro em AWS antes de expandir para novos vetores.

### Prioridades

**1. Maturidade de produto**
- histórico de runs comparável
- diff de exposição entre execuções
- dashboard para cliente

**2. Maturidade de engine**
- escolha estratégica entre paths concorrentes
- priorização por impacto real

**3. Persistência de grafo**
- Neo4j ou equivalente
- dataset anonimizado para pesquisa

**4. Consolidação dos dois produtos**
- Produto 01 operacional com clientes reais
- Produto 02 funcional em CI/CD

---

# Eixo 2 — Kubernetes (próximo vetor)

Kubernetes entra somente após maturidade AWS comprovada.

---

## Curto prazo — Kubernetes (apenas modelagem, sem implementação)

### Objetivo
Definir o modelo antes de qualquer implementação.

### Prioridades
- taxonomia de attack paths Kubernetes
- domain model conceitual
- Tool Registry conceitual
- desenho de laboratório (brain-chaos)

---

## Médio prazo — Kubernetes

### Objetivo
Primeiros paths reais em ambiente controlado.

### Prioridades
- RBAC abuse
- service account pivot
- secrets discovery
- privileged pod escape
- lateral movement AWS → cluster

---

## Longo prazo — Kubernetes

### Objetivo
Segundo vetor completo do Rastro.

### Prioridades
- integração AWS ↔ Kubernetes em attack paths híbridos
- reutilização completa do engine central
- Tool Registry Kubernetes completo

---

# Princípios fundamentais

**Nenhum vendor obrigatório.**
Ollama é padrão. Backends são plugáveis. APIs externas são opção.

**Autorização explícita obrigatória.**
Sem authorized_by e authorization_document, o run não inicia.

**Engine é independente do LLM.**
Planner sugere. Engine decide, valida, executa, observa.

**Cada fase é publicável.**
Resultados geram material técnico. Projeto cresce em visibilidade
junto com a base de código.

**Testes sem dependências externas.**
pytest roda offline. AWS e LLM testados com mocks.

**Não expandir escopo antes de fechar fase.**
Cada fase entregue completa antes da próxima começar.

---

# Regra central

Rastro não cresce adicionando integrações.

Rastro cresce provando attack paths completos,
com raciocínio, execução controlada e evidência auditável.
