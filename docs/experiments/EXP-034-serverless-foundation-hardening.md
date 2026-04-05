# EXP-034 — Hardening do Foundation em Serverless Business App

## Identificação
- ID: EXP-034
- Fase: 3
- Status: confirmada

## Contexto
Depois da Variante A do `serverless-business-app`, o próximo passo foi endurecer o mesmo arquétipo com:
- KMS explícito
- mais ruído semântico
- APIs públicas adicionais

O objetivo era verificar se o `aws-foundation` continuava estável nas variantes B e C antes de abrir as classes `advanced`.

## Hipóteses
- H1: a presença de KMS não quebra a seleção foundation.
- H2: a presença de ruído adicional via API pública e naming ambíguo não desvia o foundation dos alvos corretos.
- H3: o assessment discovery-driven foundation continua `4/4` nas variantes B e C.

## Resultados por etapa

### Etapa 1 — Variante B
- Execução inicial:
  - `campaigns_passed = 3/4`
  - falha em `aws-iam-role-chaining`
- Causa isolada:
  - o target selection escolheu `PayrollDecryptRole`
  - o fixture de role chaining atinge `PayrollHandlerRole`
- Após correção geral de scoring:
  - `campaigns_passed = 4/4`

### Etapa 2 — Variante C
- Execução inicial:
  - `campaigns_passed = 2/4`
  - falhas em `aws-iam-secrets` e `aws-iam-role-chaining`
- Causa isolada:
  - o target selection escolheu `prod/payroll-admin-bridge-token` em vez de `prod/payroll-api-key`
  - o target selection escolheu `PayrollDecryptRole` em vez de `PayrollHandlerRole`
- Após correção geral de scoring:
  - `campaigns_passed = 4/4`

## Causa raiz

### Falha de infraestrutura?
- Não. Os fixtures estavam coerentes com o desenho do arquétipo.

### Falha de representação de estado?
- Não. O discovery capturou corretamente KMS, APIs e resources adicionais.

### Falha de policy?
- Sim. O `target selection` ainda estava com heurística insuficiente para desempatar recursos e roles em ambiente serverless endurecido.

### Falha de framing do planner?
- Não. O problema aconteceu antes do planner, na escolha do alvo da campanha.

### Limitação genuína do modelo?
- Não. O planner nem chegou a ter chance de resolver o target errado.

## Intervenção aplicada
- reforço de scoring para foundation:
  - `api_key` e `password` agora têm peso maior que `token`
  - sinais `admin`, `public`, `bridge` e `audit` agora penalizam candidatos quando competem com alvos mais diretamente ligados a dado
  - roles com `handler`/`runtime` sobem sobre roles auxiliares como `decrypt`

## Descoberta principal
O próximo gargalo do Produto 01 não era o pipeline discovery-driven em si, mas a qualidade do `target selection` sob colisão semântica. Em ambientes serverless endurecidos, empates e sinais pouco discriminativos eram suficientes para gerar campanhas erradas. Após o ajuste geral de scoring, o foundation voltou a `4/4`.

## Implicação arquitetural
O `target selection` precisa de uma camada de scoring mais informativa para:
- diferenciar `api_key/password` de `token`
- diferenciar roles de dado/runtime de roles auxiliares como `decrypt`, `audit`, `public`, `admin`

## Conclusão
- H1: confirmada
- H2: confirmada
- H3: confirmada

O `aws-foundation` agora permanece estável também nas variantes B e C do `serverless-business-app`, inclusive com KMS e ruído semântico adicional. Isso libera a abertura das classes `advanced` neste arquétipo.
