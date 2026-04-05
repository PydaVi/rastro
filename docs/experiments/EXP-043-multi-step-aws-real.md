# EXP-043 - Multi-Step AWS Real

- ID: EXP-043
- Fase: Prioridade 3 - promocao AWS real do segundo nivel
- Data: 2026-04-03
- Status: concluida

## Contexto

Quarta promocao real do bloco de generalizacao ofensiva, apos:
- compute pivot real
- external entry real

Objetivo:
- validar uma chain mais profunda em AWS real, sem depender de cross-account
- provar a sequencia:
  - superficie publica de compute
  - pivô para role anexada
  - `assume_role` para broker intermediario
  - `assume_role` para role de dado
  - leitura real de segredo em Secrets Manager

Lab efemero planejado:
- 1 EC2 `t3.micro` com IP publico
- IMDS com `HttpTokens=optional`
- 1 `instance profile` com role publica
- 1 role broker intermediaria
- 1 role final de dado
- 1 secret em Secrets Manager

## Hipoteses

- H1: o executor real consegue combinar `external entry` com dois pivôs STS no mesmo run.
- H2: o engine progride por uma chain de quatro passos ofensivos sem ficar preso ao pivô inicial.
- H3: o mesmo loop central continua suficiente para um path multi-step mais profundo em AWS real.

## Desenho experimental

- Variavel independente:
  - lab AWS real efemero em `terraform_local_lab/multi_step_real/`
- Criterio:
  - `objective_met = true`
  - evidência real de:
    - `ec2:DescribeInstances`
    - `iam:GetInstanceProfile`
    - `ec2:DescribeIamInstanceProfileAssociations`
    - `sts:AssumeRole`
    - `iam:SimulatePrincipalPolicy`
    - `secretsmanager:GetSecretValue`

## Resultado por etapa

### Etapa R1 - run real inicial

Resultado:
- `objective_met = false`
- o pivô de compute funcionou
- a chain travou no primeiro `assume_role`
- o erro real foi:
  - `AccessDenied` em `sts:AssumeRole`
  - caller efetivo: `arn:aws:iam::550192603632:user/brainctl-user`
  - role desejada: `arn:aws:iam::550192603632:role/AnalyticsBrokerRole`

Artefatos:
- `outputs_real_exp43_multi_step_openai/report.md`
- `outputs_real_exp43_multi_step_openai/audit.jsonl`

### Etapa R2 - rerun apos correcao geral de executor

Resultado:
- `objective_met = false`
- o run continuou falhando, mas agora com erro semanticamente correto:
  - `reason = missing_actor_credentials`
  - ator afetado: `arn:aws:iam::550192603632:role/PublicPayrollAppRole`

Interpretacao da etapa:
- a correcao eliminou o fallback silencioso para as credenciais base
- o produto agora falha de forma rigorosa quando uma chain tenta prosseguir sem credenciais reais da identidade alcançada

### Etapa R3 - tentativa de rerun com surrogate credential acquisition

Resultado:
- rerun bloqueado antes da execução do path
- falha de infraestrutura do lab:
  - colisao de nomes IAM com o lab de `external entry`
  - segredo ainda em janela de delecao agendada no Secrets Manager

Erros observados:
- `EntityAlreadyExists` para `PublicPayrollAppRole`
- `InvalidRequestException` para `prod/finance/warehouse-api-key` agendado para delecao

Classificacao:
- infraestrutura
- nao revelou nada novo sobre o engine

### Etapa R4 - rerun final com nomes isolados e surrogate credential acquisition

Resultado:
- `objective_met = true`
- chain completa validada em `5` steps
- sequência real observada:
  - enumerate IAM
  - pivô de compute com `assume_role_surrogate`
  - `assume_role` para broker
  - `assume_role` para role final de dado
  - `secretsmanager:GetSecretValue`

Artefatos:
- `outputs_real_exp43_multi_step_openai/report.md`
- `outputs_real_exp43_multi_step_openai/audit.jsonl`

## Erros, intervencoes e motivos

### Causa raiz

Falha geral de executor e semântica de credenciais:

1. o engine promoveu `PublicPayrollAppRole` como identidade ativa apos o pivô de compute
2. o executor real **nao** adquiriu credenciais para essa identidade
3. quando a ação seguinte tentou `iam_passrole`, o executor caiu silenciosamente para as credenciais base do operador
4. o AWS real rejeitou o `sts:AssumeRole` porque o trust do broker aceita `PublicPayrollAppRole`, nao `brainctl-user`

Isso revela um problema mais profundo do que o sintoma atual:
- hoje o Rastro sabe marcar uma identidade como alcançada
- mas ainda nao separa explicitamente:
  - `identity reached`
  - `credentials actually acquired`

### Separacao de causas possiveis

- Infraestrutura:
  - nao
  - o lab real funcionou como desenhado
- Representacao de estado:
  - sim
  - faltou distinguir identidade ativa de identidade credenciada
- Policy:
  - parcialmente
  - o loop liberou progresso a partir de uma identidade sem credenciais reais
- Framing do planner:
  - nao
  - o planner escolheu a chain correta
- Limitacao genuina do modelo:
  - nao

### Impacto arquitetural imediato

Esse problema também ameaça a validade da promocao real anterior de `external entry`:
- o dado final pode ter sido lido com as credenciais base do operador
- nao necessariamente com credenciais obtidas a partir da role anexada por compute

### Intervencao aplicada

Correcao geral implementada:
- o executor real agora exige credenciais explicitas quando `action.actor` nao e a identidade base do run
- se a identidade foi apenas alcancada, mas nao credenciada, o erro agora e:
  - `missing_actor_credentials`

Efeito:
- remove falso positivo potencial em paths que continuavam apos pivôs de compute/external entry
- preserva chains STS reais, onde credenciais sao de fato adquiridas

## Descoberta principal

O gap real nao é `multi-step` em si.

O gap é mais geral:
- o executor AWS real ainda nao modela `credential acquisition` como requisito duro para seguir uma chain apos pivôs de compute/external entry

## Interpretacao

Esse experimento foi valioso porque separou duas capacidades que antes estavam misturadas:
- provar a **estrutura** do pivô
- provar a **continuidade credenciada** da chain

O Produto 01 já tinha a primeira.
Ainda nao tinha a segunda de forma rigorosa para pivôs nao-STS.

## Implicacoes arquiteturais

- o executor real nao pode cair para credenciais base quando `action.actor` nao foi credenciado explicitamente
- o produto precisa de uma nocao persistente de `credentialed_identities`
- `external entry` e `compute pivot` reais so podem promover chains seguintes se houver aquisicao real de credenciais ou um mecanismo controlado e explicitamente marcado de surrogate credentialing

## Ameacas a validade

- o lab usa EC2 publica controlada como entrypoint estrutural
- nao modela exploit HTTP real; modela a relacao `public compute -> role -> sts chain -> secret`

## Conclusao

EXP-043 confirmou a hipótese apos o endurecimento correto da camada de credenciais.

Resultado final:
- `objective_met = true`
- evidência real de:
  - `ec2:DescribeInstances`
  - `iam:GetInstanceProfile`
  - `ec2:DescribeIamInstanceProfileAssociations`
  - `sts:AssumeRole` controlado para a role alcançada por compute
  - `sts:AssumeRole` para broker intermediario
  - `sts:AssumeRole` para role final
  - `iam:SimulatePrincipalPolicy`
  - `secretsmanager:GetSecretValue`

Descoberta principal consolidada:
- o problema nao era a chain multi-step
- o problema era a ausência de uma camada explícita de `credential acquisition`
- com essa camada, o loop central já suporta multi-step real profundo

## Proximos experimentos

- retomar `aws-cross-account-data` quando existir segunda conta controlada
- manter `assume_role_surrogate` como mecanismo controlado para labs de compute/external entry
