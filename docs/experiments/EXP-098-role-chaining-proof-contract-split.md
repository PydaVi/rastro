# EXP-098 — Role-Chaining Proof Contract Split

- ID: EXP-098
- Fase: Blind real IAM-heavy
- Data: 2026-04-09
- Status: concluido

## Contexto

Depois do `rerun6`, a classe `aws-iam-role-chaining` ainda misturava duas coisas diferentes:
- oportunidade vista apenas por simulacao
- prova real de assuncao de role

Isso era um erro de contrato. A mesma classe continuava representando niveis epistemicos diferentes.

## Hipoteses

1. `role-chaining` precisa ser separado por modo de prova, mesmo que a campanha de origem continue igual.
2. findings por simulacao devem aparecer como uma familia propria, sem disputar o mesmo significado de um path realmente provado.
3. essa separacao melhora a leitura de coverage sem inflar progresso.

## Desenho experimental

Variavel independente:
- separar o finding final por `proof_mode` em `role-chaining`.

Criterio:
- simulacao deve aparecer como `aws-iam-role-chaining-simulated`
- prova real deve aparecer como `aws-iam-role-assumption-proved`

## Resultados por etapa

### Etapa 1 — Novo contrato de finding

`AssessmentFinding` passou a carregar `proof_mode` explicitamente:
- `simulation`
- `real`
- `structural`

### Etapa 2 — Split semantico de classe

Para `role-chaining`:
- `simulation` -> `aws-iam-role-chaining-simulated`
- `real` -> `aws-iam-role-assumption-proved`

A campanha continua com o profile original.
O split acontece no contrato de findings, onde a leitura de verdade importa.

## Descoberta principal

A separacao correta nao era abrir mais um benchmark.
Era impedir que `role-chaining` continuasse escondendo dois niveis epistemicos atras do mesmo nome.

## Interpretacao

Esse ajuste nao aumenta coverage.
Ele evita inflacao conceitual.

## Implicacoes arquiteturais

1. classes ofensivas podem precisar de subtipos por modo de prova.
2. coverage relevante precisa diferenciar simulacao de impacto real.
3. a fase seguinte deve tratar `aws-iam-role-assumption-proved` como a barra verdadeira da classe.

## Ameacas a validade

- a separacao de finding nao resolve o problema de prova real por si so
- o lab continua subcoberto

## Conclusao

`role-chaining` agora tem um contrato mais honesto: simulacao e prova real deixaram de compartilhar o mesmo nome semantico.

## Proximos experimentos

1. rerodar `aws-iam-role-chaining-only` com o novo split
2. confirmar que os findings aparecem como `aws-iam-role-chaining-simulated`
3. usar `aws-iam-role-assumption-proved` como meta explicita da proxima fase da classe
