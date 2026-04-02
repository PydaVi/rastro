# Architecture Note (MVP)

This MVP implements a minimal vertical slice of a controlled pentest agent with strict scope enforcement, deterministic behavior, and auditable execution.

## Core Components
- CLI: `src/app/main.py` orchestrates a bounded run.
- Domain models: `src/core/domain.py` defines objectives, actions, decisions, and observations.
- Planner interface: `src/planner/interface.py` abstracts decision logic.
- Deterministic planner: `src/planner/mock_planner.py` provides a safe, predictable backend.
- Planner metadata: each decision carries backend/model/raw-response metadata for audit and reporting.
- Scope enforcer: `src/execution/scope_enforcer.py` validates every action against allowed actions/resources.
- Executor: `src/execution/executor.py` applies simulated transitions only.
- Fixture: `src/core/fixture.py` provides the synthetic IAM lab and deterministic transitions.
- Attack graph: `src/core/attack_graph.py` keeps an explicit, inspectable graph.
- Audit logger: `src/core/audit.py` writes append-only JSONL events.
- Report generator: `src/reporting/report.py` compiles JSON and Markdown outputs.

## Execution Loop
The CLI runs a bounded loop:
1. Enumerate available actions from the fixture.
2. Planner selects the next action.
3. Scope enforcer validates the action.
4. Executor applies a safe simulated transition.
5. Attack graph is updated.
6. Audit event is logged with planner metadata.

Loop stops on objective completion or max steps.

## Modelo de Execucao e Cobertura (AWS)
Rastro nao executa um teste monolitico sobre toda a conta AWS. A validacao e feita
por campanhas controladas, organizadas por classes de attack path dentro de um
escopo autorizado. Isso garante governanca, rastreabilidade, reprodutibilidade,
clareza de cobertura e seguranca operacional.

### Camadas operacionais
**1. Target** define o ambiente do cliente.
Inclui contas AWS, regioes permitidas, roles de entrada e configuracao base.

Exemplo conceitual:
```yaml
target:
  name: cliente-prod
  platform: aws
  accounts:
    - "111111111111"
    - "222222222222"
  allowed_regions:
    - us-east-1
    - sa-east-1
  entry_roles:
    - arn:aws:iam::111111111111:role/RastroAssessmentRole
```

**2. Authorization** define o que esta explicitamente autorizado.
Campos obrigatorios: `authorized_by`, `authorization_document`, periodo de
validade, perfis permitidos, exclusoes (opcional). Sem authorization valido,
nenhum run e executado.

**3. Profile** define uma familia de attack paths.
Exemplos: `aws-iam-exposure`, `aws-secrets-paths`, `aws-s3-paths`,
`aws-compute-to-identity`, `aws-cross-account`.

Cada profile contem classes de path suportadas, servicos permitidos, limites de
execucao e regras de seguranca.

**4. Campaign** e uma execucao concreta de um profile sobre um target.
Exemplo:
```yaml
campaign:
  target: cliente-prod
  profile: aws-iam-exposure
  mode: controlled
  output: outputs/cliente-prod/iam
```
Cada campanha executa de forma independente, gera evidencia auditavel e produz
artefatos proprios.

**5. Assessment** e um conjunto de campanhas.
Exemplo: `rastro assessment run --target cliente-prod --bundle aws-foundation`.

### Bundles (cobertura)
Bundles sao conjuntos pre-definidos de profiles que definem o nivel de
cobertura oferecido.

`aws-foundation`:
IAM privilege escalation, role chaining, S3 access paths, Secrets Manager
exposure, Parameter Store exposure.

`aws-advanced`:
compute-to-identity pivots, Lambda execution paths, multi-step attack chains,
deeper branch exploration.

`aws-enterprise-full`:
foundation + advanced, multi-account, cross-account trust paths, maior
profundidade de exploracao e campanhas iterativas.

### Fluxo de execucao
Baseline com descoberta inicial do ambiente, identificacao de pivos e
construcao inicial do attack graph. Em seguida, campanhas por profile com
validacao controlada e evidencia. Por fim, consolidacao com agregacao de
attack paths validados, grafo consolidado, relatorio tecnico e executivo e
cobertura alcancada.

### Principios de execucao
Nenhuma execucao fora do escopo autorizado.
Cada campanha e auditavel e isolada.
Evidencia sempre registrada (real ou inferida).
Resultados negativos sao preservados.
Execucao incremental, nao monolitica.

### Evolucao futura
UI para orquestracao de assessments, comparacao entre runs, historico de
exposicao, diffs entre avaliacoes e integracao com CI/CD (Produto 02).

### Regra central
Rastro nao varre a conta inteira. Rastro valida, de forma controlada, as classes
de attack path suportadas atraves de campanhas independentes, com evidencia
auditavel e cobertura explicita.

## Estado operacional atual
O bundle `aws-foundation` agora possui cobertura validada para:
- IAM -> S3
- IAM -> Secrets Manager
- IAM -> SSM Parameter Store
- IAM -> Role chaining

O MVP operacional em implementacao expõe:
- `profile list`
- `target validate`
- `campaign run`
- `assessment run`

Esses comandos reutilizam o runner existente e introduzem a primeira camada
operacional descrita acima: catalogo de profiles, validacao de target,
execucao de campanhas e consolidacao de assessments.
