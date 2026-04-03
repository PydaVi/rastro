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

O MVP operacional atual expõe:
- `profile list`
- `target validate`
- `preflight validate`
- `discovery run`
- `campaign run`
- `assessment run`

Esses comandos reutilizam o runner existente e introduzem a primeira camada
operacional descrita acima: catalogo de profiles, validacao de target,
execucao de campanhas e consolidacao de assessments.

Validacao operacional atual:
- `assessment run --bundle aws-foundation` validado ponta a ponta em AWS real
- artefatos gerados por campanha e por assessment
- resultado atual observado: 4/4 campanhas `passed`, `assessment_ok: true`

## Contrato operacional atual do aws-foundation

O `aws-foundation` ja funciona como primeiro bundle operacional do Produto 01.
O contrato atual e:

**1. Catalogo**
- profiles versionados no catalogo interno
- bundle `aws-foundation` composto por 4 campanhas:
  - `aws-iam-s3`
  - `aws-iam-secrets`
  - `aws-iam-ssm`
  - `aws-iam-role-chaining`

**2. Target**
- arquivo JSON com:
  - `name`
  - `platform`
  - `accounts`
  - `allowed_regions`
  - `entry_roles`

**3. Authorization**
- arquivo JSON com:
  - `authorized_by`
  - `authorized_at`
  - `authorization_document`
  - `permitted_profiles`
  - `excluded_profiles`

**4. Preflight**
- validacao explicita antes do run
- checa identidade AWS corrente
- checa conta permitida
- checa existencia dos roles declarados no scope
- falha de preflight aborta a campanha e e preservada como status operacional

**5. Campaign**
- gera scope derivado do target + authorization + profile
- executa um unico profile
- produz:
  - `report.json`
  - `report.md`
  - `attack_graph.html`
  - `audit.jsonl`
  - `scope` gerado da campanha
- status operacional:
  - `passed`
  - `objective_not_met`
  - `preflight_failed`
  - `run_failed`

**6. Assessment**
- executa todas as campanhas do bundle
- nao aborta no primeiro erro
- preserva falhas e continua a consolidacao
- produz:
  - `assessment.json`
  - `assessment.md`
- resumo estavel:
  - `campaigns_total`
  - `campaigns_passed`
  - `campaigns_objective_not_met`
  - `campaigns_preflight_failed`
  - `campaigns_run_failed`
  - `assessment_ok`

## Comandos atuais do MVP

```bash
python -m app.main profile list
python -m app.main target validate --target examples/target_aws_foundation.local.json
python -m app.main preflight validate --scope examples/scope_aws_dry_run.json
python -m app.main campaign run \
  --profile aws-iam-s3 \
  --target examples/target_aws_foundation.local.json \
  --authorization examples/authorization_aws_foundation.local.json \
  --out outputs/campaign
python -m app.main assessment run \
  --bundle aws-foundation \
  --target examples/target_aws_foundation.local.json \
  --authorization examples/authorization_aws_foundation.local.json \
  --out outputs/assessment
```

## Limites atuais

- ainda nao existe engine de descoberta/ranking de alvos para contas reais
- o catalogo de profiles ainda e interno ao codigo
- o bundle `aws-foundation` e o unico bundle operacional pronto
- advanced e enterprise ainda dependem de expansao do portfolio
- `aws-cross-account-data` em AWS real continua dependente de um contrato
  multi-account explicito e de uma segunda conta controlada

## Contrato para cross-account real

`aws-cross-account-data` nao deve ser promovido para AWS real com pseudo-lab de
uma conta so. A validacao real exige:

- conta origem
- conta destino
- trust policy explicita entre contas
- evidencia real de `sts:AssumeRole` cruzando o boundary de conta
- leitura do recurso alvo na conta destino

Documento de desenho:
- `docs/cross-account-real-validation.md`

## Proximo bloco do Produto 01

O proximo bloco arquitetural do Produto 01 e a camada de:
- `Discovery`
- `Target Selection`
- `Campaign Synthesis`

Documento de desenho:
- `docs/product01-discovery-target-selection.md`
- `docs/synthetic-aws-environments.md`

Essa camada fecha a principal lacuna atual do MVP:
- hoje o sistema executa campanhas conhecidas
- o proximo passo e descobrir recursos reais, selecionar alvos e sintetizar
  campanhas automaticamente dentro do escopo autorizado

Base de escala recomendada:
- `internal-data-platform`
- `serverless-business-app`
- `compute-pivot-app`

Esses arquétipos sinteticos ampliam o realismo dos testes sem cair em
aleatoriedade opaca.

Status do primeiro corte:
- `discovery run --bundle aws-foundation` implementado
- artefatos iniciais:
  - `discovery.json`
  - `discovery.md`
- cobertura inicial de discovery:
  - IAM roles
  - S3 buckets e amostra de objetos
  - Secrets Manager
  - SSM Parameter Store por prefixes controlados
- validado em AWS real no bundle `aws-foundation`
- ajuste aplicado apos validacao real:
  - filtrar service-linked roles do inventario inicial
  - corrigir ARN de parametros SSM no artefato

## Status do segundo corte: Target Selection foundation

`target-selection run` agora transforma o inventario do `aws-foundation` em
`TargetCandidate[]` auditaveis.

Artefatos atuais:
- `target_candidates.json`
- `target_candidates.md`

Contrato atual do candidato:
- `id`
- `resource_arn`
- `resource_type`
- `profile_family`
- `score`
- `confidence`
- `selection_reason`
- `signals`
- `supporting_evidence`

Heuristicas atuais do primeiro corte:
- palavras-chave sensiveis no nome/ARN
- diferenciacao por superficie (`s3_object`, `secret`, `parameter`, `role`)
- sinais especificos de role chaining (`BrokerRole`, `DataAccessRole`)

Validacao atual:
- executado sobre `outputs_discovery_aws_foundation_openai/discovery.json`
- 15 candidatos gerados
- 5 candidatos `high confidence`

Limites atuais do segundo corte:
- ranking ainda e heuristico e lexical
- ainda nao existe correlacao por policy/trust graph
- candidatos ainda nao viram campanhas automaticamente

## Status do terceiro corte: Campaign Synthesis foundation

`campaign-synthesis run` agora transforma `TargetCandidate[]` em `CampaignPlan[]`
para o `aws-foundation`.

Artefatos atuais:
- `campaign_plan.json`
- `campaign_plan.md`
- `generated/<profile>/<candidate>/objective.generated.json`
- `generated/<profile>/<candidate>/scope.generated.json`

Contrato atual do plano:
- `id`
- `profile`
- `target_candidate_id`
- `resource_arn`
- `priority`
- `planned_services`
- `generated_objective`
- `generated_scope`
- `confidence`
- `score`

Validacao atual:
- executado sobre os candidatos reais do `aws-foundation`
- 4 planos gerados, um por profile
- heuristica de role chaining ajustada para priorizar `DataAccessRole`
  sobre roles de auditoria

Limites atuais do terceiro corte:
- o plano ainda nao executa automaticamente no `assessment run`
- scopes gerados ainda partem de templates de profile
- ainda nao existe pruning por reachability real

## Status do quarto corte: Assessment discovery-driven

`assessment run --bundle aws-foundation --discovery-driven` agora executa o
pipeline completo:

1. discovery
2. target selection
3. campaign synthesis
4. campaign execution
5. assessment consolidation

Artefatos encadeados no assessment:
- `discovery/discovery.json`
- `target-selection/target_candidates.json`
- `campaign-synthesis/campaign_plan.json`
- `campaigns/<profile>/report.json`
- `assessment.json`
- `assessment.md`

Validacao atual:
- executado ponta a ponta em AWS real
- resultado observado: `assessment_ok: true`
- 4/4 campanhas `passed`
- campaigns geradas automaticamente a partir do inventario e dos candidatos

Limites atuais do quarto corte:
- o pipeline ainda usa heuristicas simples de selecao
- ainda nao existe pruning por reachability real no campaign synthesis
- advanced e enterprise ainda nao foram conectados ao fluxo discovery-driven
