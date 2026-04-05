# EXP-072 — External Entry Reachability Benchmark Objective Coupling

## Identificacao

- ID: EXP-072
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-01
- Status: confirmada

## Contexto

Apos o primeiro corte de discovery de rede no `EXP-071`, o proximo passo do
`Bloco 1 — External Entry Reachability Real` foi criar um benchmark sintético
com quatro estados separados:

- superficie publica sem backend reachavel
- backend reachavel sem cred acquisition
- cred acquisition possivel sem path ao dado
- cadeia completa

O benchmark inicial reutilizou o objetivo existente de `aws-external-entry-data`.

## Hipoteses

H1. O benchmark deveria marcar `objective_met = false` nos tres primeiros
estados, porque ainda nao ha exploração completa ate o dado.

H2. O benchmark deveria marcar `public_exploit_path_proved_end-to-end` apenas
na cadeia completa.

## Desenho experimental

### Variavel independente

- novos fixtures sintéticos de maturidade de `external entry`

### Critério

- `objective_met` e `external_entry_maturity` coerentes com cada estado do
  benchmark

## Resultados por etapa

### Etapa 1 — Run inicial do benchmark

Falhou.

Resultado observado:

- os tres primeiros estados ficaram com `objective_met = true`
- a cadeia completa nao foi classificada como
  `public_exploit_path_proved_end-to-end`

## Erros, intervencoes e motivos

### Causa raiz

O problema nao estava no report builder.

O problema estava no reaproveitamento do objetivo da campanha
`aws-external-entry-data`, que carregava:

- `success_criteria.flag = compute_identity_pivoted`

Isso colapsou o benchmark:

- assim que o pivô de compute acontecia, o run encerrava com `objective_met`
- os estados intermediarios deixavam de ser intermediarios do ponto de vista do
  loop
- a cadeia completa nao chegava ao step de dado final

Classificacao:

- falha de infraestrutura de benchmark
- nao falha do engine central

### Correcao escolhida

Criar um objetivo especifico para o benchmark de reachability:

- sem `flag` de pivô
- com sucesso definido apenas por observacao do alvo final

## Descoberta principal

O benchmark de maturidade de `external entry` nao pode reutilizar um objetivo
de campaign cuja semantica ja assume que:

- pivô de compute
= sucesso suficiente

Isso mascara exatamente a fronteira que o benchmark queria medir:

- `credential path`
vs
- `public exploit path`

## Interpretacao

O experimento revelou acoplamento sintético residual entre:

- benchmark de maturidade
- objetivo operacional de uma campaign conhecida

Essa descoberta reforca a régua do produto:

- benchmarks de generalizacao precisam evitar objetivos que comprimem estados
  intermediarios relevantes

## Implicacoes arquiteturais

- `external entry reachability` precisa de objetivos proprios para benchmark
- reporting pode continuar usando os estados novos
- a prova do bloco fica mais rigorosa quando o objetivo nao herda sucesso por
  flag da classe operacional

## Ameacas a validade

- o benchmark ainda e sintético
- a separacao final de rede real continua dependente dos proximos blocos

## Conclusao

H1 rejeitada no run inicial.

H2 rejeitada no run inicial.

A causa raiz foi isolada:

- objetivo de benchmark acoplado a `success_criteria.flag` da campaign base

Com isso, a correção correta nao é mexer no engine, e sim:

- usar um objetivo de benchmark alinhado ao estado que se quer medir

## Proximos passos

1. rerodar o benchmark com objetivo especifico de reachability
2. validar os quatro estados separadamente
3. atualizar o `PLAN.md` com o passo 3 do bloco marcado como concluido
