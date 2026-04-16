# EXP-089 - Root Cause Analysis da falha em IAM-heavy simples

- ID: EXP-089
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-04
- Status: concluida

## Contexto

O problema central atual nao e mais teorico.

Foi feito um reteste contra um ambiente AWS IAM-heavy com dezenas de falhas
simples de privilege escalation IAM.

O resultado observado continua fraco:
- o Rastro nao convergiu para o espaco ofensivo esperado do ambiente
- o output final ficou concentrado em duas familias:
  - `aws-iam-s3`
  - `aws-iam-role-chaining`
- o assessment por usuario inflou findings sem aumentar diversidade estrutural

Isso obriga uma pergunta mais dura:

- a falha e superficial?
- ou a falha e estrutural?

## Hipoteses

- H1: parte da falha e superficial:
  - bundle inadequado
  - portfolio curto
  - ranking IAM fraco
  - runtime IAM intermediario estreito
- H2: parte da falha e estrutural:
  - o nucleo ainda transforma pouco discovery real em path ofensivo distinto
  - o contrato de sucesso/evidencia continua frouxo
  - o sistema continua mais apto a validar campaigns conhecidas do que a
    descobrir e provar chains novas
- H3: o problema principal precisa ser isolado antes de qualquer novo reteste
  ou novo benchmark vistoso

## Desenho experimental

- Variavel independente:
  - releitura dos artefatos reais mais recentes do reteste IAM-heavy
  - releitura do output per-user
  - releitura do nucleo:
    - `blind_real_runtime`
    - `campaign_synthesis`
    - `service`
    - `target_selection`
    - `reporting`
- Ambiente:
  - mesmo produto atual
  - sem expandir runtime nem selection nesta etapa
- Criterio:
  - isolar onde a cadeia quebra:
    - discovery
    - selection
    - synthesis
    - runtime
    - evidence
    - aggregation

## Resultados observados

### 1. Discovery ja nao e o gargalo principal

O discovery ve o ambiente.

No reteste IAM-heavy, o produto observou:
- dezenas de roles e users IAM
- sinais de trust e policy
- inventario suficiente para mostrar que o ambiente nao estava invisivel

Conclusao:
- a falha principal nao e `o sistema nao viu o ambiente`

### 2. Selection tambem ja nao e o gargalo principal

O selection e fraco, mas nao cego.

Ele escolheu dois candidatos finais:
- um objeto S3 de terraform state
- uma role IAM do lab

Isso e ruim como coverage.
Mas mostra que o problema principal nao e ausencia total de ranking.

Conclusao:
- o selection contribui para a subcobertura
- mas nao explica sozinho o fracasso

### 3. O bundle atual continua estreito demais para o tipo de ambiente

O `aws-foundation` continua limitado a:
- `aws-iam-s3`
- `aws-iam-secrets`
- `aws-iam-ssm`
- `aws-iam-role-chaining`

Em um lab IAM-privesc-heavy, isso e cobertura insuficiente por definicao.

Conclusao:
- existe componente superficial claro: bundle e portfolio inadequados

### 4. O runtime IAM-heavy continua superficial demais

Mesmo depois dos ajustes recentes, o `BlindRealRuntime` continua curto.

Ele hoje se apoia demais em:
- `iam:SimulatePrincipalPolicy`
- `AssumeRole`
- acesso final a dado

Isso ainda esta longe de representar, de forma ofensivamente convincente:
- abuse real de policy version
- attach policy com consequencia observavel
- update assume-role-policy
- abuso real de user/group
- passrole com criacao/alteracao de recurso intermediario relevante

Conclusao:
- existe falha superficial importante de portfolio/runtime

### 5. O output per-user provou inflacao de resultado

No output:
- `campaigns_total = 84`
- `campaigns_passed = 84`
- `findings_total = 84`
- `42` findings de `aws-iam-s3`
- `42` findings de `aws-iam-role-chaining`

Isso nao representa 84 paths distintos.

Representa:
- 2 plans
- multiplicados por 42 users

Conclusao:
- o sistema mede melhor multiplicidade de principal sobre o mesmo alvo do que
  distinct path

### 6. `target_observed` continua contaminando a semantica do produto

Esse e o principal erro estrutural.

Enquanto o objective upstream continuar frouxo, o sistema segue vulneravel a:
- campaign passada sem exploracao forte
- finding volumoso sem diversidade estrutural
- mistura entre observacao, reachability e impacto validado

Conclusao:
- o problema nao e so coverage
- o problema e truthfulness do nucleo

### 7. Julgamento final da causa

A falha atual e mista.

#### Parte superficial
- bundle inadequado
- portfolio IAM curto
- runtime IAM intermediario estreito
- ranking IAM ainda fraco

#### Parte estrutural
- `target_observed` continua frouxo demais
- distinct path nao e unidade primaria do produto
- findings continuam inflaveis por multiplicidade de principal
- `campaign passed` continua perto demais de `verdade ofensiva`

O segundo grupo e mais grave.

Se ele nao for corrigido, qualquer ampliacao de portfolio continuara mal medida.

## Descoberta principal

O fracasso no IAM-heavy simples nao pode ser lido como:
- `faltou mais profile`

Tambem nao pode ser lido como:
- `faltou rerodar`

A leitura correta e:
- existe falha superficial de coverage/runtime
- mas ha um erro estrutural mais serio no contrato de verdade do produto

Sem corrigir o erro estrutural, qualquer ganho superficial continuara inflando a
aparencia de progresso.

## Interpretacao

Hoje o produto falha em um teste que deveria ser mais facil do que o gate
futuro `Wyatt`.

Isso significa:
- o problema imediato e basico
- o produto ainda nao esta bom nem para o IAM-heavy simples
- portanto, o `Wyatt` faz sentido como gate futuro exatamente para impedir
  autoengano

Mas o proximo passo nao e correr para `Wyatt`.

O proximo passo e:
- isolar e corrigir por que o produto falhou no IAM-heavy simples

## Implicacoes arquiteturais

1. `Core truthfulness and path distinctness` vira bloco imediatamente superior a
   qualquer novo benchmark vistoso
2. ampliacao de portfolio IAM-heavy continua necessaria, mas subordinada ao
   conserto do contrato de verdade
3. novos reruns IAM-heavy sem esse bloco fechado produzem mais ruido do que
   conhecimento
4. `Wyatt` continua como gate correto de medio prazo, mas nao como proximo passo
   imediato

## Ameaças à validade

- este diagnostico nao substitui a ampliacao de runtime IAM-heavy
- ele nao mede ainda quantos challenges do lab poderiam ser cobertos apos
  ampliar portfolio
- ele tambem nao prova que todo o problema esta no core

Mas ele prova algo suficiente para reordenar o roadmap:
- o erro estrutural atual e grande o bastante para invalidar leituras otimistas
  de coverage

## Conclusao

O fracasso no IAM-heavy simples e ao mesmo tempo:
- superficial, porque o portfolio/runtime continuam estreitos
- estrutural, porque o nucleo ainda nao mede path distinto e verdade ofensiva
  com rigor suficiente

Entre os dois, o problema estrutural e o mais perigoso.

## Proximos experimentos

1. fechar `Reestruturacao do nucleo para verdade de path e distinctness`
2. so depois abrir ampliacao de runtime/portfolio IAM-heavy
3. rerodar IAM-heavy simples com metricas por:
   - distinct path
   - classe ofensiva
   - evidencia minima
4. usar `Wyatt` apenas depois desse baseline estar epistemicamente confiavel
