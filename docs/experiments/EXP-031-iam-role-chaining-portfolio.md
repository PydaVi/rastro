# EXP-031 — IAM -> Role Chaining (Portfolio Foundation)

## Identificacao
- ID: EXP-031
- Fase: 3
- Pre-requisito: EXP-030 concluido
- Status: concluida

## Contexto
Quarta classe do portfólio foundation. Objetivo: validar chains com dois pivôs
de `assume_role`, separando o problema de role chaining da superfície final.

## Hipoteses
H1: o engine consegue executar uma cadeia de dois `assume_role` antes de
acessar o recurso final.
H2: o engine realiza backtracking quando o broker inicial escolhido nao fecha a
chain correta.

## Desenho experimental

### Variavel independente
- dois fixtures sinteticos: chain direta e chain com broker decoy
- planner OpenAI

### Ambiente
- usuario inicial
- roles intermediarias do tipo broker
- role final com acesso ao bucket sensivel

### Criterio de sucesso
- objective_met true em cada variante
- evidencia de dois `assume_role` antes do acesso final

## Resultados por etapa

### Etapa A — Chain direta
- Status: confirmada
- Artefatos: fixtures/aws_iam_role_chaining_direct_lab.json
 - Resultado: objective_met true em 4 passos
 - Observacao: o engine executou dois `assume_role` antes do acesso ao objeto.

### Etapa B — Broker decoy com backtracking
- Status: confirmada
- Artefatos: fixtures/aws_iam_role_chaining_backtracking_lab.json
 - Resultado: objective_met true em 6 passos
 - Observacao: o planner abriu o broker decoy, enumerou o dead-end e depois
   pivotou para a chain correta `BrokerRole -> DataAccessRole`.

### Etapa R — AWS real (promocao)
- Status: confirmada
- Artefatos: outputs_real_exp31r_iam_role_chaining_openai/report.md
 - Resultado: objective_met true em 6 passos
 - Observacao: o run real executou `DecoyBrokerRole -> BrokerRole -> DataAccessRole`
   antes do acesso ao objeto sensivel, confirmando role chaining e backtracking
   em AWS.

## Erros, intervencoes e motivos
- Nao houve falha de engine nas etapas A/B.
- Descoberta arquitetural antes da etapa real: o executor AWS usava apenas uma
  credencial assumida "corrente" e nao propagava credenciais por ator em
  `assume_role` encadeado.
  Classificacao: falha de representacao de estado no executor real.
  Intervencao: armazenar credenciais por role e selecionar credenciais com base
  em `action.actor` para `assume_role`, `list` e `access_resource`.
- Intervencao de infraestrutura: adicionar ao Terraform local um lab real
  dedicado com `BrokerRole`, `DataAccessRole` e `DecoyBrokerRole`.

## Descoberta principal
- Classe IAM -> Role chaining confirmada no sintetico.
- O engine trata `assume_role` encadeado como progressao de branch, nao como
  loop redundante.
- A execucao real exigiu uma melhoria geral no executor: credenciais precisam
  ser resolvidas por ator, nao apenas pelo "ultimo assume_role".

## Interpretacao
- A etapa A provou o caso base da classe: chain com dois pivôs antes do
  recurso final.
- A etapa B provou que o backtracking continua funcional quando o dead-end
  ocorre no broker inicial, antes da segunda role.
- A etapa R provou que o mesmo comportamento fecha em AWS real com STS
  encadeado de verdade.

## Implicacoes arquiteturais
- `active_assumed_roles` e `action shaping` continuam adequados para chains com
  multiplos pivôs da mesma superficie STS.
- O executor real agora suporta role chaining de forma geral para qualquer
  superficie posterior que dependa de STS encadeado.
- A classe 4 ganhou um lab real proprio e deixou de depender de inferencia a
  partir do Path 3.

## Ameacas a validade
- O lab real continua controlado, nao multi-account.

## Conclusao
- H1 confirmada. H2 confirmada no sintetico.
- A promocao real foi concluida.
- A classe 4 do portfólio foundation esta fechada para o eixo AWS.
