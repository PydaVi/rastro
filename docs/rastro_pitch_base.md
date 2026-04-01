# Rastro — Pitch Base

Este documento é a referência central para todos os pitches do Rastro.
Não é um pitch pronto — é o material bruto do qual se deriva cada versão
específica por stakeholder, canal, e contexto.

---

## Identidade do produto

**Nome:** Rastro
**Categoria:** Autonomous Attack Path Validation
**Vetores:** AWS (atual) · Kubernetes (próximo)
**Modelo:** open source (Apache 2.0) + dois produtos comerciais
**Repositório:** github.com/PydaVi/rastro

---

## A frase central

> O problema da segurança em cloud não é detectar risco.
> É entender quais riscos se conectam em um caminho real de comprometimento —
> e fazer isso na mesma velocidade que um atacante moderno.

---

## O problema em três camadas

### Camada 1 — Pentest não escala com cloud

Cloud muda diariamente. IAM é combinatório. Policies, roles e trust
relationships criam uma explosão de caminhos possíveis que nenhum humano
mapeia manualmente com a frequência necessária. Pentest pontual é uma
fotografia de um ambiente em movimento constante. Depende da qualidade
individual do testador, do quanto ele está atualizado, do tempo contratado.

**A consequência:** a maioria das empresas faz pentest uma vez por ano —
e o ambiente muda toda semana.

### Camada 2 — BAS é mecânico

Breach and Attack Simulation (BAS) valida se seus controles detectam
ameaças conhecidas. É útil — mas é um teste de assinatura. Não raciocina
sobre o ambiente específico do cliente. Não descobre que aquela combinação
de permissões naquela conta abre um caminho que nenhuma assinatura conhece.

**A consequência:** BAS confirma o que você já defende. Não encontra o
que você não sabe que está exposto.

### Camada 3 — CSPM mostra risco, não comprometimento

Wiz, Prisma, CrowdStrike — todos mostram findings isolados e grafos
teóricos de attack path. Nenhum prova que o caminho é realmente explorável.
Um finding de "role com permissões excessivas" fica na fila de remediação
indefinidamente porque parece abstrato — não tem evidência de que alguém
conseguiria realmente chegar a algum lugar.

**A consequência:** as organizações acumulam listas de findings que ninguém
sabe priorizar porque ninguém sabe o que é realmente crítico.

---

## A tese

Se ataques se tornam raciocínio automatizado — e já estão se tornando —
a defesa precisa de raciocínio automatizado do mesmo nível.

Um agente que:
- conhece o ambiente específico do cliente
- formula hipóteses de encadeamento
- testa cada cadeia com execução real
- descarta o que não funciona
- prova o que funciona com evidência auditável

Isso não é um scanner. Não é um playbook de ataques conhecidos.
É um engine que pensa sobre o ambiente da mesma forma que um atacante
competente pensaria.

---

## O que o Rastro faz — em linguagem simples

1. Recebe um objetivo de ataque e um escopo autorizado
2. Enumera o ambiente: identidades, permissões, recursos, relações de trust
3. Formula hipóteses: quais combinações podem criar um caminho de comprometimento?
4. Testa cada hipótese: executa o encadeamento, observa o resultado
5. Quando um caminho falha, descarta e tenta o próximo — sem loop, sem revisita
6. Quando encontra um caminho real, documenta cada passo com evidência
7. Entrega: grafo de ataque, relatório técnico, mapping MITRE, remediação

---

## O que o Rastro faz — em linguagem técnica

- Loop autônomo: `enumerate → plan → validate → execute → observe → graph`
- Candidate path tracking com status explícito (untested / failed / successful)
- Branch failure memory — não revisita dead-ends
- Action shaping — policy layer antes do LLM que organiza o espaço de busca
- Backtracking estruturado — retorna ao ponto de decisão após falha
- Path scoring com lookahead — prioriza candidatos por valor esperado
- Scope Enforcer obrigatório — toda ação validada antes de executar
- Audit Logger append-only — evidência imutável por step
- Artefatos sanitizados automáticos para compartilhamento seguro

---

## O que diferencia do mercado

| O que existe | Limitação central | Como o Rastro resolve |
|---|---|---|
| CSPM (Wiz, Prisma) | grafo teórico, sem execução | executa e prova |
| BAS (SafeBreach, AttackIQ) | ataques conhecidos, sem raciocínio | raciocina sobre o ambiente específico |
| Pentest tradicional | não escala, pontual, humano-dependente | autônomo, repetível, auditável |
| Pentera / Horizon3 | caro, caixa preta, rede-first | open source, auditável, cloud-native |
| PMapper / Cartography | estático, sem execução | executa e valida |

**O espaço que o Rastro ocupa:**
Attack Graph + Execution + Reasoning + Cloud-native + Open Source

Nenhuma ferramenta existente cobre essa interseção completa.

---

## Os dois produtos

### Produto 01 — Validação de Exposição AWS (consultoria)

**Para quem:** fintechs, seguradoras, healthtechs com AWS real e
obrigações regulatórias crescentes — sem budget para ferramentas enterprise.

**O que entrega:**
- Attack paths reais executados no ambiente do cliente
- Evidência auditável (ARNs, timestamps, respostas de API reais)
- Grafo de comprometimento interativo
- Relatório técnico + executivo com MITRE mapping
- Remediação priorizada por impacto real

**Por que não é pentest:**
Pentest entrega lista de findings. Validação de Exposição entrega prova
de comprometimento — "partindo dessa credencial, em X passos, chegamos aqui."

**Modelo de precificação:** por escopo de superfície testada
- Tier 1 — IAM + S3: R$ 8-15k
- Tier 2 — + Secrets Manager + SSM: R$ 18-30k
- Tier 3 — + Lambda + EC2 + cross-account: R$ 35-60k

### Produto 02 — Attack Path em CI/CD (API / SaaS)

**Para quem:** times de plataforma e DevSecOps que usam Terraform + AWS
e querem garantir que nenhum deploy abre attack path crítico.

**O que entrega:**
- Gate no PR antes do deploy
- Simulação do estado AWS resultante do Terraform plan
- Raciocínio sobre cadeias — não regras estáticas por resource
- Comentário no PR com evidência e remediação
- Bloqueio de merge configurável por severidade

**Por que não é Checkov:**
Checkov analisa resources isolados. Rastro API projeta o estado combinado
(novos recursos + estado atual da conta) e raciocina sobre cadeias —
encontra o que rules estáticas não encontram.

**Modelo de precificação:** mensalidade por organização
- Startup: R$ 990/mês (1 conta, 500 scans)
- Growth: R$ 2.500/mês (5 contas, ilimitado)
- Enterprise: sob consulta

---

## Os números que importam por stakeholder

### Para o CISO / Head de Segurança
- Custo médio de um breach em nuvem: US$ 4.45M (IBM 2023)
- Tempo médio para identificar um breach: 194 dias
- Rastro encontra o caminho antes que um atacante o use

### Para o CTO / Head de Engenharia
- Custo de correção pós-produção vs no PR: 100x maior
- Produto 02 bloqueia o problema na origem — no código, antes do deploy

### Para o CFO / CEO
- Alternativa enterprise (Pentera): R$ 150-300k/ano
- Rastro Produto 01: R$ 8-60k por engajamento, sem licença anual
- Rastro Produto 02: R$ 990-2.500/mês

---

## Objeções comuns e respostas

**"Já temos Wiz / CrowdStrike."**
CSPM mostra que o risco existe. Rastro prova se é explorável. São complementares
— mas só o Rastro responde "isso pode ser comprometido de verdade?"

**"Já fazemos pentest."**
Com que frequência? O ambiente muda toda semana. Rastro é repetível sempre
que você precisar — não uma vez por ano.

**"Como você garante que não causa dano no ambiente?"**
Scope Enforcer obrigatório. Autorização explícita documentada. Leitura
com credenciais mínimas. Nenhum recurso criado permanece. O engine valida
cada ação antes de executar — sem exceção, sem bypass.

**"É open source — como você monetiza?"**
O engine é open source. Os produtos (consultoria e API hospedada) são
o negócio. O mesmo modelo do Grafana, HashiCorp Terraform, e Metasploit.

**"Não conheço o Rastro — como sei que funciona?"**
O repositório tem 15 experimentos documentados com metodologia científica,
hipóteses, resultados e limitações. Você pode reproduzir cada um. Não é
marketing — é evidência verificável.

---

## Frases de impacto por contexto

**Para abrir conversa com engenheiro de segurança:**
"Você já se perguntou se aquela permissão IAM excessiva realmente cria
um caminho até os seus dados de produção — ou só parece que cria?"

**Para abrir conversa com CISO:**
"A maioria das ferramentas te diz o que está errado. Rastro te mostra
o que um atacante consegue fazer com o que está errado."

**Para abrir conversa com CTO / eng. plataforma:**
"Cada PR que modifica IAM ou políticas pode criar um attack path que
nenhum lint de Terraform detecta. Rastro valida isso antes do deploy."

**Para post / conteúdo:**
"Scanners listam. Atacantes exploram cadeias. O Rastro também."

---

## O nome — por que Rastro

Duas direções simultâneas que definem o produto:

**Seguir rastros** — o engine rastreia o caminho como um investigador.
Cada permissão, cada recurso, cada relação de trust é um rastro que aponta
para o próximo passo. O agente segue até onde o caminho leva.

**Deixar rastros** — cada execução deixa evidência imutável. O audit trail
é o rastro do ataque — o que aconteceu, em que ordem, com que resultado.
O cliente recebe o rastro do comprometimento, não uma estimativa.

Em português, com identidade própria, memorável num mercado de nomes
genéricos em inglês. E com profundidade semântica que o produto justifica.

---

## O que não dizer

- Não dizer "ferramenta de pentest" — limita o posicionamento
- Não dizer "scanner de vulnerabilidades" — é exatamente o que não é
- Não dizer "IA faz o pentest" — impreciso e cria expectativa errada
- Não prometer cobertura que ainda não existe (Kubernetes, Linux)
- Não comparar diretamente com Pentera como se fossem iguais —
  o diferencial do Rastro é cloud-native + open source + auditável

---

## Versões derivadas a criar

- Pitch para CISO / Head de Segurança (foco: risco e compliance)
- Pitch para CTO / Head de Engenharia (foco: custo de correção e pipeline)
- Pitch para CFO / CEO (foco: custo vs alternativas e ROI)
- Pitch para engenheiro de segurança (foco: técnico, como funciona)
- Pitch para investidor / fomento público (foco: mercado e inovação)
- Post LinkedIn — versão pública inicial
- One-pager para proposta comercial Produto 01
- Landing page resumida
