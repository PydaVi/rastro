# PLAN.md — Rastro

Plano operacional vivo.

Este documento deve permanecer curto.
Ele existe para responder quatro perguntas:
- qual e a direcao atual do produto
- qual e o proximo bloco prioritario
- quais decisoes abertas importam agora
- o que ainda bloqueia o proximo reteste relevante

Referencias:
- `REGUA.md`: criterio permanente de generalizacao ofensiva vs operacionalizacao
- `HISTORY.md`: historico experimental completo e descobertas arquiteturais

---

## Direcao estrategica fixa

1. AWS primeiro
2. Produto 01 antes do Produto 02
3. profundidade antes de expansao
4. Kubernetes depois

O objetivo do Rastro nao e ser um bom executor de campaigns conhecidas.
O objetivo e caminhar, de forma honesta, para um engine ofensivo cada vez mais generalista.

---

## Estado atual

### O que foi realmente provado

- o engine central amadureceu em backtracking, path scoring e action shaping
- o Produto 01 ja roda em AWS real autorizado
- discovery-driven existe
- `blind real` inicial existe no `aws-foundation`
- `external entry` ganhou prova real de reachability em superficies controladas
- o produto ficou mais honesto ao expor parte da diferenca entre `observed` e `validated`

### O que nao foi provado

- generalizacao forte em ambiente AWS hostil real
- coverage ofensiva satisfatoria em IAM-heavy
- findings orientados a `distinct path` como unidade central de verdade
- runtime blind real suficientemente largo para chains hibridas app/network/cloud

### Correcao de narrativa obrigatoria

A leitura anterior do progresso estava otimista demais.

Parte do que vinha sendo lido como `generalizacao ofensiva` era, na pratica:
- melhoria de harness
- melhoria de orchestration
- melhoria de blind execution parcial
- melhoria de runtime
- melhoria de honestidade epistemologica

O reteste IAM-heavy e os findings por usuario reduziram a confianca na nota implicita de generalizacao do produto.

Julgamento atual:
- o nucleo ainda esta mais perto de `campaign validator` do que parecia
- isso nao invalida os avancos reais
- mas invalida leituras otimistas de generalizacao forte

---

## Proximo bloco prioritario

### Reestruturacao do nucleo para verdade de path e distinctness

Direcao do avanco: mais generalizacao ofensiva

#### Objetivo

Refazer os contratos centrais que hoje permitem ao produto parecer mais generalista no discurso do que no runtime e no reporting.

#### Por que este bloco vem agora

O maior risco de drift neste momento nao e falta de benchmark.
E autoengano arquitetural.

Os outputs atuais ainda permitem:
- `target_observed` como centro do contrato de sucesso
- findings inflados por multiplicidade de principal
- agregacao que mede melhor volume do que diversidade estrutural
- leitura falsa de coverage ofensiva

Rerodar IAM-heavy antes disso aumentaria ruido, nao conhecimento.

#### O que precisa parar imediatamente

1. tratar `campaigns_passed` como proxy de progresso ofensivo
2. tratar volume bruto de findings como sinal de coverage
3. tratar multiplicidade de principal contra o mesmo alvo como distinct path
4. abrir novos benchmarks vistosos antes de corrigir truthfulness e distinctness
5. aceitar `target_observed` como centro do contrato de verdade

#### O que precisa ser refeito no nucleo

1. reescrever o contrato de `objective/success`
2. separar explicitamente:
   - sucesso de campanha
   - estado de prova
   - impacto validado
3. redefinir findings por:
   - `distinct attack path`
   - `same path, multiple principals`
   - `same target, multiple proofs`
4. revisar agregacao e deduplicacao orientadas a path distinto
5. expor `finding_state` por item no output principal
6. revisar metricas de coverage para:
   - classe ofensiva
   - distinct path
   - multiplicidade separada

#### Critérios de saida

1. `validated` nao depende de `target_observed`
2. findings finais representam path distinto ou classe distinta justificada
3. `assessment_findings.md` mostra `finding_state` por item
4. volume bruto de findings nao conta como progresso
5. coverage passa a ser medida por classe ofensiva e `distinct path`

#### O que este bloco aproxima do polo generalista

- reduz autoengano do produto
- troca volume de campanha por verdade de path
- desloca a qualidade do sistema para distinctness estrutural e prova minima real

#### O que permanece dependente de campaigns conhecidas

- o portfolio ofensivo ainda sera aberto por classes conhecidas
- o runtime ainda continuara estreito em varios dominios ate novas expansoes
- a generalizacao forte continuara nao provada ate novo reteste real posterior

---

## Bloco subsequente ja definido

### Reestruturacao do nucleo para blind real IAM-heavy

Direcao do avanco: mais generalizacao ofensiva

Este bloco continua valido, mas agora vem **depois** de `truthfulness and path distinctness`.

Sem corrigir o contrato de verdade do produto, qualquer ampliacao de runtime IAM-heavy continuara sendo mal medida.

Foco desse bloco quando ele abrir:
- desacoplamento definitivo de `profile -> runtime`
- blind real puro sem `fixture_path`, `scope_template_path` ou `execution_fixture_set`
- evidence minima por classe ofensiva IAM
- portfolio IAM-privesc dedicado
- runtime real com acoes intermediarias alem de `AssumeRole`
- metricas de coverage e deduplicacao proprias para IAM-heavy

---

## Gate de medio prazo

### Blind Hybrid Challenge Readiness (`Wyatt` gate)

Direcao do avanco: mais generalizacao ofensiva

Esse gate nao e benchmark cosmetico.
E criterio epistemologico de medio prazo.

Ele so conta como sucesso se for executado em modo cego, sem embutir no produto conhecimento especifico do challenge.

O gate exige convergencia blind para uma chain hibrida do tipo:
- foothold inicial
- descoberta lateral relevante
- pivô via aplicacao
- aquisicao de credenciais de workload
- acesso final ao dado

Regra obrigatoria:
- walkthrough, write-up e memoria humana do challenge nao podem virar:
  - fixture
  - profile
  - objective
  - selection hack
  - scoring ad hoc

Dependencias antes de abrir esse gate:
1. fechar `Reestruturacao do nucleo para verdade de path e distinctness`
2. fechar `Reestruturacao do nucleo para blind real IAM-heavy`
3. runtime blind real com acoes intermediarias hibridas suficientes
4. findings agregados por `distinct path`, nao por volume bruto ou multiplicidade de principal

---

## Proximo reteste que volta a merecer confianca

Nao e agora.

O proximo reteste IAM-heavy so volta a ter leverage quando estes pre-requisitos estiverem fechados:
- runtime blind real puro
- `validated` sem dependencia central de `target_observed`
- findings por `distinct path`
- coverage por classe ofensiva
- multiplicidade de principal separada de diversidade estrutural

Ate la, reruns adicionam mais ruido do que informacao.

---

## Decisoes abertas

### 1. Contrato de verdade

Pergunta:
- o sucesso de campanha deve continuar existindo separado do estado de prova?

Leitura atual:
- sim, mas o contrato precisa deixar claro que `campaign passed` nao e sinonimo de impacto validado.

### 2. Unidade primaria de finding

Pergunta:
- o finding final deve ser `target-centric`, `path-centric` ou `class-centric`?

Leitura atual:
- deve ser primariamente `path-centric`, com agregacao secundaria por classe e por alvo.

### 3. Coverage

Pergunta:
- como medir coverage sem inflar leitura por volume?

Leitura atual:
- coverage deve ser medida por:
  - classe ofensiva
  - path distinto
  - evidencia minima
- e nao por volume bruto de campaigns ou findings.

### 4. Sequencia correta depois do core

Pergunta:
- apos o bloco de truthfulness/distinctness, o foco deve ir para IAM-heavy ou para blind hybrid readiness?

Leitura atual:
- primeiro IAM-heavy blind real puro
- depois o `Wyatt` gate

---

## Regra operacional deste documento

Ao fechar cada bloco, registrar apenas:
- o que aproximou o produto do polo generalista
- o que permaneceu dependente de campaigns conhecidas
- qual e o proximo experimento de maior leverage

Historico detalhado nao deve voltar para este arquivo.
Ele pertence a `HISTORY.md`.
