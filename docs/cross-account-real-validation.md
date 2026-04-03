# Cross-Account AWS Real Validation

## Objetivo

Definir o contrato minimo para promover `aws-cross-account-data` para AWS real
sem degradar governanca, auditabilidade ou isolamento operacional.

Hoje a validacao sintetica da classe ja existe. O bloqueio para promocao real
nao e do engine; e do ambiente operacional: falta uma segunda conta AWS
controlada para representar a fronteira real de trust.

## Porque uma conta so nao basta

`cross-account` so e validado de verdade quando existem:

- uma conta origem, com principal inicial e ponto de partida do assessment
- uma conta destino, com role confiavel e recurso sensivel
- uma trust policy explicita entre as duas contas
- evidencia de STS cruzando a fronteira de conta

Simular isso dentro de uma conta so pode validar policy parecida, mas nao prova:

- boundary de conta
- trust inter-account
- isolamento de recursos entre contas
- comportamento real de STS cross-account

Por isso, uma validacao de uma conta so nao deve ser classificada como
`AWS real` para essa classe.

## Contrato operacional minimo

### Conta origem

- principal inicial autorizado para o assessment
- `RastroOperatorRole` ou equivalente
- permissao explicita para `sts:AssumeRole` somente no role destino esperado
- acesso somente aos servicos necessarios para preflight e evidencia

### Conta destino

- recurso sensivel controlado:
  - S3 object, ou
  - Secrets Manager secret, ou
  - SSM parameter
- role de pivô cross-account com trust restrito ao ARN da conta origem
- policy minima para ler apenas o recurso alvo

### Authorization

O authorization do assessment multi-account precisa explicitar:

- contas autorizadas (`source_account`, `destination_account`)
- roles de entrada por conta
- periodo de validade
- documento de autorizacao cobrindo trust inter-account
- perfis permitidos, incluindo `aws-cross-account-data`

## Lab efemero recomendado

Para manter custo e superficie baixos, o lab real deve ser efemero.

### Estrutura minima

#### Conta origem

- `RastroCrossAccountSourceRole`
- policy:
  - `sts:AssumeRole` somente em
    `arn:aws:iam::<destination-account>:role/RastroCrossAccountTargetRole`

#### Conta destino

- `RastroCrossAccountTargetRole`
- trust policy permitindo apenas o role da conta origem
- recurso sensivel unico, preferencialmente:
  - `arn:aws:secretsmanager:<region>:<destination-account>:secret:prod/cross-account/payroll-key-*`

### Fluxo esperado

1. preflight valida identidade e contas autorizadas
2. enumerate na conta origem
3. `sts:AssumeRole` cross-account para a conta destino
4. leitura controlada do recurso sensivel na conta destino
5. report preserva:
   - ARN do role origem
   - ARN do role destino
   - account ids de origem e destino
   - chamada STS cross-account
   - chamada final ao servico de dados
6. `terraform destroy` nas duas contas

## Artefatos que a promocao real precisa provar

Uma promocao real de `aws-cross-account-data` so deve ser marcada como
`concluida` se o report mostrar:

- `objective_met = true`
- `sts:AssumeRole` com `role_arn` da conta destino
- principal efetivo apos STS pertencendo a conta destino
- leitura real de recurso sensivel na conta destino
- cleanup do lab efemero

## Sequencia apos desbloqueio

Quando a segunda conta existir, a ordem correta e:

1. preparar `target` e `authorization` multi-account
2. criar o lab efemero nas duas contas
3. rodar preflight multi-account
4. executar `aws-cross-account-data`
5. destruir o lab
6. atualizar `PLAN.md` e `docs/experiments/EXP-0XX-cross-account-aws-real.md`

## Classificacao do gap atual

- tipo: pre-requisito operacional
- nao e bug do engine
- nao e limitacao do planner
- nao deve ser contornado com pseudo-validacao em uma conta so

## Implicacao arquitetural

Esse bloco e importante porque marca a transicao entre:

- validacao adversarial ainda centrada em uma conta controlada

e

- validacao ofensiva com fronteira real de trust entre contas AWS

Mas a promocao deve acontecer somente quando o ambiente permitir prova real,
nao aproximacao.
