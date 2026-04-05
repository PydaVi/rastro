# REGUA.md — Direcao Permanente do Produto

Documento permanente de referencia para julgar se o Rastro esta avancando em:
- `generalizacao ofensiva`
ou
- `operacionalizacao de campaigns conhecidas`

Este documento nao substitui `PLAN.md`.
Ele define a regua pela qual o plano deve ser lido.

## Polos explicitos

### Polo 1 — `campaign validator`

O produto esta mais perto de `campaign validator` quando depende principalmente de:
- profiles fixos como verdade anterior ao raciocinio
- bundles e families conhecidas como espinha principal do sistema
- heuristicas lexicais simples
- alvos pre-modelados
- `success_criteria` frouxo como `target_observed`
- harness sintetico excessivamente curado
- runtime estreito que so executa campaigns conhecidas
- crescimento de findings por volume bruto e nao por diversidade estrutural

### Polo 2 — `generalista ofensivo`

O produto se aproxima de `generalista ofensivo` quando aumenta:
- inferencia estrutural
- selection por expressividade ofensiva
- competicao entre paths concorrentes
- reachability real
- modelagem explicita de credential acquisition
- robustez em mixed environments
- robustez com naming desfavoravel ou obfuscado
- distinct path quality
- separacao entre `identity reached` e `credentials acquired`
- convergencia blind em ambiente AWS nao pre-modelado para o run

## Perguntas obrigatorias por bloco

Todo bloco relevante deve ser julgado por estas perguntas:

1. Isso reduz dependencia de profiles fixos?
2. Isso reduz dependencia de heuristica lexical simples?
3. Isso reduz dependencia de alvos pre-modelados?
4. Isso reduz dependencia de harness sintetico curado?
5. Isso aumenta inferencia estrutural?
6. Isso aumenta competicao entre paths concorrentes?
7. Isso aumenta truthfulness de findings e distinctness de path?
8. Isso aumenta reachability real ou credential acquisition real?
9. Isso aumenta robustez do runtime em ambiente blind?
10. Isso aumenta coverage ofensiva real, e nao apenas volume de campaigns?

Se a resposta principal for `nao`, o bloco nao deve ser promovido como generalizacao ofensiva forte.

## Sinais de progresso real

Contam como progresso real quando acompanhados de prova adequada:
- menos `profile-first`
- menos metadata curada
- mais inferencia por relationships
- mais mixed benchmarks com competicao real
- mais separacao entre `observed`, `reachable`, `credentialed`, `exploited`, `validated_impact`
- mais blind execution sem contaminacao de fixture
- mais coverage por classe ofensiva
- mais findings por path distinto, nao por multiplicidade de principal
- mais promotion-to-real fora de IAM-first puro
- mais app/network/cloud pivot com prova progressiva

## Sinais de inflacao de confianca

Devem ser tratados como alerta, nao como progresso:
- bundles crescendo mais rapido que a inferencia
- novos profiles sem benchmark ou reteste relevante correspondente
- heuristicas lexicais crescendo sem contrapartida estrutural
- volume bruto de findings crescendo mais do que diversidade estrutural
- multiplicidade de principal sendo tratada como proxy de coverage ofensiva
- `campaigns_passed` sendo usada como proxy de generalizacao
- `validated` coexistindo com sucesso upstream frouxo
- benchmark/harness mais maduro sendo confundido com autonomia ofensiva

## Regras permanentes duras

1. `target_observed` nao pode continuar como centro do contrato de verdade do produto.
2. `validated` exige prova minima explicita por classe ofensiva.
3. Multiplicidade de principal contra o mesmo alvo nao conta como coverage ofensiva.
4. Findings finais precisam distinguir:
   - path distinto
   - mesmo path com principals diferentes
   - mesma classe com variacao ofensiva relevante
5. Em `blind real`, qualquer dependencia residual de:
   - `fixture_path`
   - `scope_template_path`
   - `execution_fixture_set`
   - resolver sintetico por archetype
   e suspeita arquitetural seria.
6. Melhorias operacionais sao validas, mas nao podem dominar por muitos blocos consecutivos o roadmap sem contrapartida de generalizacao ofensiva.
7. Quando um ambiente IAM-heavy expuser subcobertura, a primeira hipotese deve ser problema do nucleo, nao `faltou benchmark`.

## Como registrar no plano

Ao fechar cada bloco em `PLAN.md`, registrar obrigatoriamente:
- direcao do avanco
- o que aproximou do polo generalista
- o que permaneceu dependente de campaigns conhecidas
- qual e o proximo experimento de maior leverage

## Gate atual de medio prazo

O criterio de medio prazo mais forte hoje e:
- `Blind Hybrid Challenge Readiness (Wyatt gate)`

Esse gate so conta como progresso se for executado em modo cego, sem embutir no produto conhecimento previo especifico do challenge.
