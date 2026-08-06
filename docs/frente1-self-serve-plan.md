# Rastro — plano de produto self-serve e banco de ambientes de teste

Documento de trabalho para incorporar ao PLAN.md / roadmap do Rastro. Duas iniciativas paralelas: (1) o pacote comercial self-serve "Attack Path Snapshot", (2) um banco de ambientes AWS simulados para gerar prova estatística e dataset de treino.

---

## 1. Contexto

O Rastro precisa de um caminho de monetização que não dependa de outreach ativo (consultoria de venda fria já é a Frente 2, tratada em outro documento). Este plano cobre a Frente 1: um produto fechado, preço fixo, self-serve, com onboarding automatizado. A segunda iniciativa (banco de ambientes simulados) alimenta tanto a credibilidade desse produto (estatísticas verificáveis) quanto a evolução técnica do próprio engine.

---

## 1.1 Estado atual e marco de lançamento (checagem em 2026-08-05)

Antes de investir em qualquer parte comercial deste plano, alinhar com o estado real do engine, não com a intenção.

**O que já sustenta o produto:** Blocos 1–9, 12, 14 e 15 estão DONE. A parte mais difícil, provar caminho via mutação real com rollback (não só teorizar), já funciona — showcase `acme_showcase` com 6 chains simultâneos provados.

**O que ainda bloqueia vender o pacote self-serve, e por quê:**

- **Bloco 11 (Governança Real) segue em andamento.** SCP herdado de OU/root, `Condition` de trust policy e cross-account real ainda não entram completamente no cálculo do `CapabilityGraph`. O risco relevante para um produto pago não é falso positivo no relatório (a prova vem de execução real, que falha sozinha se a AWS bloquear) — é falso negativo: o relatório dizer "nenhum caminho encontrado" numa conta que na verdade tem exposição não coberta pelo grafo ainda. Vender essa garantia incompleta contradiz o próprio posicionamento de prova auditável.
- **Onboarding automatizado de conta AWS não existe ainda** — está listado como tal no próprio README. O fluxo de checkout, CFN quick-create e verificação de assume-role (Seção 3 deste documento) é construção nova, não ajuste. Não depende do Bloco 11 e pode ser trabalhado em paralelo.
- **Falta validação externa.** O único showcase público hoje é um laboratório construído pelo próprio autor do engine. Antes de cobrar de alguém, rodar contra uma fatia pequena de ambientes de terceiros (Camadas A e B da Seção 4, ~10–15 ambientes) serve como portão de qualidade: confirma que as correções do Bloco 11 generalizam fora do ambiente que o inspirou, em vez de só parecerem ter fechado a lacuna.

**Ordem de trabalho recomendada:** fechar Bloco 11 → construir onboarding automatizado em paralelo (não bloqueado por nada acima) → rodar a fatia pequena de validação externa → só então lançar o Attack Path Snapshot.

Ver Seção 6 para o plano de seriedade e confiança que sustenta esse gate por outro ângulo: lá é sobre o que fica visível pra fora, aqui é sobre o que precisa estar correto por dentro antes.

---

## 2. Produto: "Attack Path Snapshot"

Pacote único no lançamento, não uma grade de planos. Nome já comunica o limite: uma foto pontual, não monitoramento contínuo.

### 2.1 Escopo — o que entra

- Uma conta AWS por execução (não Organization, não multi-conta).
- Teto fixo de profundidade de BFS e de tempo de execução, definido por engenharia antes do lançamento, para limitar custo de compute por execução.
- Modo determinístico por padrão (raciocínio via LLM desligado). Ativar LLM reasoning é upsell futuro ("Deep Analysis"), não faz parte do preço base.
- Relatório em PDF gerado 100% por template automático, sem revisão humana.
- Prova de rollback incluída no relatório (parte central do diferencial do Rastro).
- Suporte assíncrono por e-mail, sem SLA contratual, sem call.

### 2.2 Escopo — o que fica de fora (e por quê)

- Re-execução ou monitoramento contínuo → isso é o Produto 02 (API de CI/CD), modelo de cobrança recorrente separado.
- Relatório revisado por humano → reintroduz custo de mão de obra que o modelo existe para eliminar.
- Implementação de correção/remediação → vira engajamento de consultoria, com escopo e preço próprios.
- Call de onboarding ou escopo customizado → quebra o self-serve.
- Superfícies fora do que o engine cobre hoje (K8s, rede, outras nuvens) → aguardam roadmap.

### 2.3 Precificação

Calcular o custo real de uma execução (minutos de compute do ambiente efêmero + infraestrutura auxiliar) e aplicar margem de 3 a 5x nos primeiros meses, até haver dado real de volume mensal. Faixa de referência do mercado (self-serve, sem revisão humana): TurboPentest cobra USD 99/alvo; com revisão humana leve, XBOW cobra a partir de USD 4.000; Budget Security cobra a partir de €849 com escopo definido pelo cliente. O Rastro deveria ficar perto da ponta barata desse espectro (USD 149–299) para diferenciação de entrada.

### 2.4 Tradução de findings em linguagem de impacto

O relatório não pode parar em achado técnico cru (`iam:AttachRolePolicy` provado). Pra virar valor de negócio pro cliente, cada chain precisa de uma frase de impacto em linguagem acessível antes do detalhe técnico, gerada por template determinístico, não escrita à mão por execução (isso quebraria o modelo de custo da Seção 2.1).

**Taxonomia de consequência.** Cada chain provada é classificada numa categoria de negócio, não só na action técnica: controle administrativo da conta, exposição de dados, colheita de credencial, persistência/backdoor, fraude de billing, interrupção de serviço.

**A fonte do dado já existe no engine.** O Capability Graph (Bloco 7) já computa `assumable_by`, `mutable_by`, `readable_by` por recurso, e o Bloco 4b já calcula privilege score por blast radius. A frase de impacto ("se isso fosse explorado, o atacante alcançaria X") é preenchida com esse dado já calculado, não é análise nova por relatório.

**Exemplo de formato**, aplicado a um chain do showcase:
> Se um atacante comprometesse as credenciais de `acme-cicd-agent`, ele conseguiria assumir controle administrativo de `acme-ops-role`, o que dá acesso a [N recursos alcançáveis, computados pelo grafo]. Isso foi provado com uma ação real, revertida automaticamente em seguida.

**Régua de intensidade por `evaluation_tier`.** A força da linguagem tem que ser proporcional ao que foi de fato comprovado, nunca ao que soa mais assustador — é o que protege o posicionamento de honestidade da Seção 6. Chain com execução real e rollback confirmado (`evaluated`, provado) recebe frase afirmativa ("um atacante conseguiria X"). Hipótese ainda não executada (`structural`) recebe frase condicional e contida ("a análise de política sugere que seria possível X, ainda não testado"). Misturar os dois tons no mesmo relatório é o erro a evitar.

**Fronteira com o upsell.** O modo determinístico com template cobre a tradução essencial no preço base. Narrativa mais rica, cruzando o achado com contexto específico do cliente (ex. inferir produção vs. staging pelo nome dos recursos), fica reservada para o "Deep Analysis" com LLM já definido como upsell na Seção 2.1 — não introduz mecanismo novo, usa o que já está no plano.

---

## 3. Onboarding automatizado

### 3.1 Fluxo

**Etapa 1 — Checkout.** Cliente paga preço fixo via Stripe Payment Link, sem negociação, sem conta a criar previamente.

**Etapa 2 — Geração de acesso.** Webhook do Stripe dispara geração de um `ExternalId` único para essa compra e monta o link de quick-create do CloudFormation (URL do console com `templateURL` e `param_ExternalId` pré-preenchidos).

**Etapa 3 — Cliente aplica o template.** Cliente clica no link, revisa a stack no console, confirma criação, copia o `RoleArn` do Output e cola em um formulário curto (nome da conta/região opcional).

**Etapa 4 — Verificação de acesso.** Backend tenta `sts:AssumeRole` com o ARN e o ExternalId recebidos antes de iniciar qualquer execução real. Falha dispara e-mail automático com diagnóstico (causas mais comuns: propagação de IAM ainda não concluída, ExternalId incorreto).

**Etapa 5 — Execução isolada.** Rastro roda em ambiente efêmero e isolado por cliente, com timeout e teto de custo definidos na etapa de engenharia (ver 2.1).

**Etapa 6 — Geração do relatório.** PDF montado por template fixo a partir do output bruto da execução, sem edição manual.

**Etapa 7 — Entrega.** E-mail automático com o PDF anexado/linkado, instrução (ou botão) para o cliente destruir a stack CloudFormation, e um link de upgrade para consultoria/engajamento maior — esse é o gancho que conecta o funil self-serve de volta à Frente 2 (consultoria).

### 3.2 Template CloudFormation (esqueleto de referência)

Estrutura mínima: trust policy restrita à conta do Rastro com `Condition: sts:ExternalId`, `MaxSessionDuration` curto (ex. 3600s), `PermissionsBoundary` como teto de dano mesmo que a policy principal tenha erro, e a lista de actions **gerada a partir do código real do engine** (grep das chamadas de SDK usadas pelo discovery e pelo executor de mutação, alimentado no `policy_sentry` da Salesforce para produzir least-privilege por ARN e nível de acesso — não usar wildcard de serviço inteiro). Publicar essa policy no próprio repositório como prova de transparência é diferenciação de marketing legítima frente a concorrente que esconde isso atrás de sales call.

### 3.3 Stack técnica sugerida

Step Functions orquestrando Lambdas (webhook do Stripe → verificação de assume-role → disparo da execução → geração do PDF), SES para e-mail, S3 para armazenar relatórios. Reaproveita a mesma disciplina de infraestrutura já usada profissionalmente, e a implementação em si vira prova pública de competência.

---

## 4. Iniciativa 2 — banco de ambientes AWS simulados

Objetivo duplo: (a) gerar estatística verificável para uso comercial ("testado contra N ambientes simulados, chain encontrada em X% dos casos vulneráveis, Y% de falso positivo em ambientes seguros"), e (b) gerar dataset rotulado para evolução do próprio engine via ML.

### 4.1 Princípio de independência

O requisito central do usuário foi "o mais independente possível, sem forçar algo só pra funcionar" — ou seja, evitar viés de confirmação. Duas práticas resolvem isso:

- Congelar a metodologia de geração dos ambientes **antes** de rodar o Rastro contra eles. Não ajustar retroativamente os ambientes para melhorar o resultado.
- Separar quem gera os ambientes de quem desenvolve o engine sempre que possível, ou pelo menos manter um subconjunto "held-out" nunca visto durante o desenvolvimento, usado só na hora de gerar a estatística final.

### 4.2 Composição da amostra (evitar 100 ambientes escritos à mão)

**Camada A — labs vulneráveis já existentes e mantidos por terceiros (não escritos pelo autor do Rastro).** Reutilizar e adaptar projetos open source consolidados: CloudGoat (Rhino Security Labs, 8 cenários cobrindo privesc de IAM e outras superfícies), IAM Vulnerable (Bishop Fox, focado especificamente em privilege escalation via IAM), TerraGoat (Bridgecrew, misconfigurations gerais), AWSGoat (INE Labs, infraestrutura mais próxima de aplicação real). Usar esses como estão, sem adaptar para favorecer o Rastro, é o que dá credibilidade de independência: não foram desenhados por quem construiu a ferramenta sendo testada.

**Camada B — baselines seguros de referência.** Módulos amplamente usados como `terraform-aws-modules` e referências do AWS Well-Architected. Servem para medir taxa de falso positivo: um ambiente seguro que o Rastro marca como comprometível é sinal de bug, não de sucesso. Essa camada é tão importante para a credibilidade quanto a Camada A.

**Camada C — geração combinatória/randomizada.** Um gerador que compõe módulos (VPC, IAM roles/policies, Lambda, EC2, S3, RDS) com parâmetros sorteados aleatoriamente (flags de risco ligadas/desligadas ao acaso, políticas e trust relationships variadas), produzindo a maior parte do volume de forma sistemática em vez de autoria manual ambiente por ambiente. É o equivalente a fuzzing aplicado a infraestrutura, e é a camada que efetivamente escala até 100+ sem trabalho manual repetitivo.

Distribuição sugerida para atingir 100+: ~15–20 da Camada A, ~15–20 da Camada B, ~60–70 da Camada C.

### 4.3 Metodologia de teste

Cada ambiente sobe em conta AWS isolada e descartável (orçamento com alarme de billing), roda via pipeline de CI, e é destruído ao final. Métricas capturadas por execução: chain encontrada (booleano), profundidade da chain, tempo até primeira prova, nós explorados no BFS, falso positivo (só relevante na Camada B), sucesso do rollback. Números agregados só são publicados depois que a metodologia estiver congelada, nunca antes.

### 4.4 Uso para machine learning

A saída de prova do próprio Rastro (chain provada ou não, junto com o grafo de capability) já é o rótulo — não é necessário anotar manualmente. Isso transforma cada execução em um par (estado do ambiente, resultado) pronto para treino supervisionado. Aplicação mais realista no curto prazo, dado que 100 ambientes é uma base pequena para deep learning: um modelo simples de ranking que prioriza quais caminhos candidatos do BFS são mais promissores, reduzindo o espaço de busca e o tempo/custo de execução — o que alimenta diretamente a sustentabilidade de preço do pacote self-serve (Bloco 2.3). Modelos mais ambiciosos (scoring de risco de configuração) ficam para quando o corpus crescer além de centenas de execuções.

### 4.5 Riscos e cuidados

- Custo de rodar dezenas/centenas de contas repetidamente, mesmo efêmeras — usar conta sandbox dedicada com alarme de orçamento, considerar LocalStack para os ciclos de desenvolvimento antes de validar em conta real.
- Overfitting: o engine não deve ser ajustado contra o mesmo conjunto usado para gerar a estatística de venda — manter um held-out set.
- Licença: os projetos da Camada A são open source (majoritariamente MIT/Apache), mas conferir os termos de cada um antes de redistribuir ou embutir no pipeline público do Rastro.

---

## 5. Sequenciamento sugerido

**Atualizado em 2026-08-05 — ver `PLAN.md`, seção "Bloco 16 — Cobertura Ampla
Validada por Variação Máxima".** Uma sessão de trabalho no engine revelou que
o gate de maturidade original (só "fechar Bloco 11") era necessário mas não
suficiente: uma auditoria rápida achou que cobertura de serviço além de IAM/
S3/Secrets/SSM é, em grande parte, andaime desconectado (tools com YAML mas
sem execução real ligada a nenhum caminho, `CapabilityGraph` sem arestas pra
Lambda/KMS/EC2). A promessa "aponte pra sua conta AWS de produção e receba
resultado confiável" depende de três coisas fechando juntas, não uma:

1. **Governança (Bloco 11)** — SCP herdado de OU/root e cross-account real.
   `Condition` de trust policy já fechado (2026-08-05).
2. **Amplitude de serviço validada (Bloco 16, novo)** — cada serviço novo
   (EC2, Lambda, KMS, RDS) só conta como coberto com capability graph +
   execução por caminho + executor completo + validação contra as Camadas
   A/B/C abaixo, não só "tem YAML".
3. **Validação contra variação (Camadas A/B/C desta seção)** — deixa de ser
   um gate final aplicado uma vez e passa a rodar em loop junto com cada
   fatia de cobertura nova (Bloco 16.2) — "apanhar o máximo possível" cedo,
   não no fim.

Sequenciamento revisado:

1. Bloco 11 (governança) e Bloco 16 (amplitude + validação contínua) andam
   **em paralelo** — nenhum dos dois sozinho fecha a promessa de "qualquer
   conta de produção", então não faz sentido serializar um atrás do outro.
2. Onboarding automatizado (Seções 2 e 3 deste documento) segue como trilha
   de engenharia separada, sem depender de 1 — mas **não é mais o próximo
   passo natural**: construir a loja antes do produto que ela vende estar
   confiável em qualquer conta real inverteria a prioridade que esta mesma
   seção definiu desde o início.
3. Estatística pública e lançamento comercial só depois de 1 e 2 fechados —
   critério de saída completo no Bloco 16 do `PLAN.md`.
4. Canal de aquisição (Seção 7) não é uma etapa depois das três acima — a
   parte de conteúdo já começa junto do Bloco 16.2, porque é o mesmo
   artefato (labs testados) servindo dois propósitos. Só o lançamento de
   pico da Seção 7.5 espera o gate comercial completo.

---

## 6. Seriedade e confiança

Objetivo: dar ao projeto credibilidade que resista a auditoria (plano prático) e credibilidade que se sente antes mesmo de auditar (plano subjetivo). Os dois já têm base real no projeto hoje, o trabalho é deixar isso visível em vez de enterrado no código.

### 6.1 Plano prático

- Fechar o Bloco 11 antes de qualquer lançamento comercial (repete o gate da Seção 1.1: confiança prática começa em não vender garantia que o engine ainda não sustenta).
- Publicar um `SECURITY.md` com política de disclosure: como reportar vulnerabilidade no próprio Rastro, prazo de resposta, o que acontece depois. Ausência disso sinaliza, mesmo sem querer, que segurança é discurso e não prática interna.
- Deixar o Bloco 15 (Auditor Offline Independente) visível no produto, não só no código. O engine já reverifica escopo, objetivo, rollback e nível de avaliação sem confiar no self-report do próprio run — ativo raro, a maioria das ferramentas de segurança pede que se acredite no relatório que elas mesmas geraram. Cada Attack Path Snapshot deveria declarar explicitamente isso no relatório entregue.
- Publicar os números do banco de ambientes (Seção 4) com a taxa de erro incluída, não só os acertos: não é só "encontramos X% de chains", é "encontramos X%, e no conjunto de baselines seguros o falso positivo foi Y%". Mostrar a taxa de erro de propósito é o tipo de honestidade que não se finge.
- Termos claros e curtos no produto: o que acontece com o `RoleArn` depois da execução, quanto tempo os dados ficam retidos, o que é feito com o relatório do cliente. Não precisa ser contrato longo, precisa ser específico o suficiente pra não gerar pergunta.

### 6.2 Plano subjetivo

- Continuar praticando o que o README já faz bem: nomear o que ainda não existe (seção "O que não existe ainda"). Repetir essa prática na landing page e no relatório entregue ao cliente — projeto que só mostra vitória soa a propaganda.
- Pessoa real e verificável por trás do produto, não empresa anônima: nome, link do LinkedIn, uma linha curta de credencial (certificações, experiência em produção) em algum canto discreto da landing page ou do README. Não é vaidade, é "aqui está quem eu sou, verifique se quiser".
- Tom consistente em todo lugar que alguém for olhar: repositório, landing page, relatório PDF, resposta a issue no GitHub. Inconsistência de tom entre lugares diferentes mina confiança de um jeito sutil, mesmo quando ninguém consegue nomear o porquê.
- Responder issue e contato em horas, não semanas, nas primeiras semanas depois de qualquer lançamento — comunica projeto vivo, pesa mais na decisão de confiar do que qualquer texto de marketing.
- Zero prova social fabricada, sempre: nenhum logo de cliente que não existe, nenhum número arredondado pra cima, nenhuma citação inventada. Uma mentira pequena descoberta destrói mais confiança do que cem verdades constroem.

---

## 7. Canal de aquisição — antes do lançamento, sem investimento pago

Todo o resto deste documento resolve "o produto está pronto" (Seções 1–3) e "como provar isso" (Seções 4 e 6). Falta a pergunta que nenhuma seção anterior responde: como alguém chega na landing page pra comprar. Sem isso, o preço (Seção 2.3) e o onboarding automatizado (Seção 3) não têm o que processar.

Restrição deliberada desta seção: **zero mídia paga**. Não por princípio — porque o produto ainda não tem taxa de conversão medida pra justificar gasto, e pagar por tráfego antes de saber quanto dele vira venda é queimar caixa no escuro que o projeto não tem. Cada tática abaixo custa tempo, não dinheiro.

### 7.1 Conteúdo é o único ativo que o projeto já tem de graça

O banco de ambientes da Seção 4 já é, por desenho, uma fábrica de conteúdo verificável — cada execução contra CloudGoat/IAM Vulnerable/TerraGoat gera um caso concreto ("achamos X em Y minutos, aqui está o audit trail completo"). Não é marketing escrito depois do fato: é o mesmo artefato técnico que a Seção 4 já planeja gerar pra estatística pública, reaproveitado como prova antes mesmo do número agregado estar pronto.

Cada chain provado contra um lab de terceiro (não construído pelo autor) vira um post técnico curto: ambiente, hipótese, execução real, rollback, evidência. É o tipo de conteúdo que profissional de segurança lê e compartilha porque é verificável — qualquer um pode baixar o mesmo lab e reproduzir — ao contrário de "top 10 dicas de cloud security".

### 7.2 Canais comunitários existentes — audiência emprestada, custo zero

Nenhum canal aqui pertence ao Rastro; todos já têm audiência formada, o trabalho é merecer o espaço:

- **r/netsec, r/aws, r/devsecops, r/cybersecurity** — post técnico com link pro repositório, nunca "compre meu produto". A régua da comunidade é ferramenta/pesquisa, não anúncio, e ela pune quem tenta vender direto.
- **Show HN** — um único lançamento bem preparado, não recorrente (ver 7.5), timed pra quando o gate comercial da Seção 1.1 estiver fechado e o showcase tiver pelo menos um lab de terceiro provado, não só `acme_showcase` próprio.
- **Awesome-lists do GitHub** (`awesome-cloud-security`, `awesome-pentest`, `awesome-incident-response`) — PR de inclusão é gratuito e gera descoberta orgânica de cauda longa, ao contrário do pico de um lançamento único.
- **Newsletters de segurança com curadoria editorial** (tl;dr sec, Last Week in AWS, newsletters de cloud security) — não são canal pago; aceitam submissão de ferramenta por critério editorial do curador. Ser citado ali é prova social genuína porque quem inclui não recebe nada por isso.

### 7.3 Seeding direto — dar de graça pra quem constrói confiança de volta

Antes do checkout automatizado cobrar de um estranho, oferecer um número pequeno (5–10) de execuções gratuitas do Attack Path Snapshot pra pessoas com credibilidade já estabelecida na comunidade de cloud security, em troca de feedback público — não de pagamento. Custo real: tempo de suporte e compute de algumas execuções, não dinheiro. Resolve direto o que a Seção 6 já nomeia como princípio ("zero prova social fabricada, sempre"): cada feedback vem de alguém que existe e pode ser verificado, mesma disciplina que rejeita logo de cliente fictício.

### 7.4 Mercado doméstico primeiro — vantagem que o autor já tem e o plano ainda não usa

O autor fala português e tem acesso natural à comunidade de segurança brasileira (BSides locais, encontros de comunidade, CFPs de conferência regional) — um mercado onde a concorrência direta (Wiz, Pentera, Horizon3) disputa menos agressivamente que nos EUA, e onde uma apresentação presencial custa zero além do tempo e gera confiança que nenhum post online replica sozinho. Validar com uma fatia de early adopters domésticos antes do lançamento internacional dá uma segunda tentativa com o aprendizado do primeiro ciclo, em vez de apostar tudo num único lançamento em inglês.

### 7.5 O único evento de pico — lançamento coordenado, não recorrente

Show HN + Product Hunt + post técnico em LinkedIn/X + submissão às newsletters da 7.2, todos no mesmo dia, uma vez. Expectativa honesta: pico de tráfego alto, conversão baixa — segurança é decisão lenta, e pedir `sts:AssumeRole` de um projeto solo é fricção real mesmo com preço baixo. O valor do pico não é a venda do dia — é o link permanente que continua sendo achado via busca e via awesome-lists (7.2) meses depois. Não repetir o lançamento; reforçar com conteúdo novo (7.1) sempre que o banco de ambientes produzir um caso novo.

### 7.6 O que fica de fora, deliberadamente

- Mídia paga (Google Ads, LinkedIn Ads, patrocínio de newsletter) — sem dado de conversão pra justificar, é gasto às cegas.
- Growth hacking (cold DM em massa, automação de outreach) — quebra a mesma credibilidade que a Seção 6 constrói, e é o tipo de tática que profissional de segurança reconhece e penaliza.
- Venda ativa fria — já é a Frente 2 (consultoria), tratada em outro documento; misturar os dois funis confunde o posicionamento "self-serve, sem call".

### 7.7 Métricas honestas — mesma régua da Seção 6

Medir sem inflar: visitas → cliques em "iniciar checkout" → checkouts completos → verificação de acesso bem-sucedida (Etapa 4 da Seção 3) → relatório entregue. A maior queda esperada é entre visita e checkout — é aí que a fricção de confiança age. Não comparar contra benchmark de SaaS genérico (produto de segurança pedindo acesso de conta converte estruturalmente pior); comparar mês contra mês do próprio produto.

### 7.8 Quando isso começa

Não depende de Bloco 11/16 fechados. A 7.1 (conteúdo) pode e deve começar durante a validação contínua do Bloco 16.2 — cada lab novo testado já é matéria-prima de post, mesmo antes do checkout existir. 7.2–7.4 (relação com comunidades, seeding, mercado doméstico) também correm em paralelo à engenharia. Só a 7.5 (lançamento de pico) espera o gate comercial completo (Seção 1.1) — lançar cedo demais gasta o único pico disponível num produto que ainda não sustenta a promessa.
