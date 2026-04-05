# EXP-085 - IAM-Heavy Blind Real Subcoverage Diagnosis

- ID: EXP-085
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-04
- Status: concluida

## Contexto

Depois de fechar o primeiro `Blind Real Assessment` funcional no
`aws-foundation`, foi executado um reteste contra um ambiente AWS real
fortemente dominado por IAM privesc.

O ambiente e baseado em um lab publico conhecido por criar dezenas de caminhos
de privilege escalation IAM e grande volume de recursos IAM.

O resultado bruto do Rastro foi fraco para esse tipo de ambiente:
- o assessment discovery-driven encontrou muitos resources IAM
- mas o output final colapsou essencialmente em:
  - `IAM -> S3 exposure` para o bucket de terraform state
  - `IAM role chaining exposure` para roles do lab
- esses findings apareceram repetidos muitas vezes
- a evidencia do finding de `role chaining` ficou fraca e muito mais proxima de
  descoberta/inferencia do que de exploracao provada

## Hipoteses

- H1: a subcobertura nao e explicada por uma falha unica; ela resulta de
  composicao entre:
  - bundle inadequado para o tipo de lab
  - discovery IAM pobre para privilege escalation
  - selection/ranking incapaz de separar exploitability IAM
  - action space real sem acoes de abuse IAM
  - findings/reporting sem deduplicacao nem classificador forte de evidencia
- H2: o `aws-foundation` nao e medida suficiente de qualidade para um ambiente
  IAM-privesc-heavy.
- H3: antes de novo reteste, o proximo bloco de maior leverage nao e rerodar o
  lab; e fechar um bloco de correcao de coverage + evidence hygiene.

## Desenho experimental

- Variavel independente:
  - mesmo `Blind Real Assessment`
  - mesma conta AWS real autorizada
  - entry role de IAM privesc lab
- Ambiente:
  - conta real com dezenas de roles IAM do lab
  - recursos S3 de suporte da conta
- Criterio:
  - observar:
    - quantidade e tipo de resources descobertos
    - quantidade de campaigns/plans gerados
    - quantidade e qualidade dos findings finais
    - se o resultado reflete coverage do tipo de ambiente ou apenas sucesso do
      bundle atual

## Resultados observados

### Resultado do discovery

O discovery real viu o ambiente novo:
- `65` resources
- `46` roles IAM
- varias roles `privesc-*`, `fn*`, `fp*`

Isso elimina a hipotese de que o lab nao foi observado.

### Resultado do selection/synthesis

Mesmo com ampliacao de cobertura:
- `max_candidates_per_profile = 20`
- `max_plans_per_profile = 10`

o assessment ficou concentrado em apenas duas familias do `aws-foundation`:
- `aws-iam-s3`
- `aws-iam-role-chaining`

O `campaign_plan.json` gerou `19` plans:
- `9` de `aws-iam-s3`
- `10` de `aws-iam-role-chaining`

Os candidatos de `aws-iam-role-chaining` apareceram praticamente empatados,
todos com score baixo e pouco discriminativo. Exemplo real observado:
- `18` para:
  - `fn1-privesc3-partial-role`
  - `fn2-exploitableResourceConstraint-role`
  - `fn3-exploitableConditionConstraint-role`
  - `fn4-exploitableNotAction-role`
  - `fp1-allow-and-deny-role`
  - etc.

Isso mostra que o ranking atual nao distingue bem exploitability IAM.

### Resultado do assessment/findings

O `assessment.json` reportou:
- `campaigns_total = 19`
- `campaigns_passed = 19`

Mas o `assessment_findings.json` mostrou essencialmente dois achados repetidos:
- `9` findings de `aws-iam-s3`
- `10` findings de `aws-iam-role-chaining`

O finding de S3 repetiu o mesmo alvo:
- `arn:aws:s3:::pydavi-terraform-state`

O finding de role chaining repetiu varias roles com evidencia fraca:
- `Validated path without exported proof payload.`

### Causas observaveis no codigo

1. **Deduplicacao ruim**
- `run_discovery_driven_assessment()` escreve campanhas em:
  - `output_dir / "campaigns" / plan["profile"]`
- portanto, multiplos plans do mesmo profile compartilham o mesmo diretorio e
  o mesmo `report.json`
- `build_assessment_findings()` percorre `result.campaigns` sem dedupe por:
  - `report_json`
  - `target_resource`
  - `finding.id`
- resultado:
  - campaigns diferentes podem gerar o mesmo report final
  - findings repetidos sao emitidos mesmo quando apontam para o mesmo artefato

2. **Evidencia insuficiente / falso positivo conceitual**
- `campaign_synthesis.py` gera objetivos com:
  - `success_criteria = {"mode": "target_observed"}`
- `StateManager.is_objective_met()` aceita sucesso se:
  - `action.target == objective.target`
  - ou o target aparecer observado em qualquer detalhe da observation
- para `aws-iam-role-chaining`, isso permite sucesso por mera observacao do
  target role em enumerate/IAM list, sem exploracao comprovada
- `build_assessment_findings()` nao classifica isso como descoberta parcial;
  gera finding `validated`

3. **Coverage limitada pelo bundle**
- o reteste foi feito com `aws-foundation`
- esse bundle cobre basicamente:
  - `aws-iam-s3`
  - `aws-iam-secrets`
  - `aws-iam-ssm`
  - `aws-iam-role-chaining`
- o ambiente IAM-privesc-heavy pede classes ofensivas diferentes:
  - abuso de policy version
  - attach/detach policy
  - update assume role policy
  - passrole para servicos
  - criacao/atualizacao de recurso intermediario para elevar privilegio
- isso nao esta representado bem no portfolio atual

4. **Limitação de discovery**
- `src/operations/discovery.py` hoje coleta sobretudo:
  - roles IAM
  - S3
  - secrets/ssm
  - compute/network
- mas nao coleta estrutura IAM suficiente para privilege escalation:
  - trust policies
  - inline policies
  - attached managed policies
  - principals que podem assumir cada role
  - groups/users/policy attachments
  - acao-permissao simulada por role
- em lab IAM-heavy, isso e uma perda estrutural de coverage

5. **Limitação de target selection**
- `src/operations/target_selection.py` para `identity.role` ainda usa score
  predominantemente hand-written e lexical
- sinais fortes para `aws-iam-role-chaining` ainda sao coisas como:
  - `broker`
  - `dataaccess`
  - `handler`
  - `runtime`
- isso e desalinhado com roles de um lab IAM-privesc-heavy
- as roles do reteste acabaram quase empatadas e com pouca prioridade ofensiva

6. **Limitação de action space / runtime real**
- `src/core/blind_real_runtime.py` hoje gera acao real basicamente para:
  - `iam_list_roles`
  - `iam_passrole` como `AssumeRole`
  - leitura de S3 / Secrets / SSM
- nao existe action space real para classes IAM-privesc do lab, como:
  - `CreatePolicyVersion`
  - `AttachRolePolicy`
  - `PassRole -> service create/update`
  - `UpdateAssumeRolePolicy`
  - `AddUserToGroup`
  - etc.
- entao mesmo um discovery melhor ainda bateria em coverage de portfolio/runtime

7. **Limitação de reporting/classificacao**
- `build_assessment_findings()` assume que toda campanha `passed` vira finding
  `validated`
- nao existe distincao explicita entre:
  - descoberta
  - reachability inferida
  - exploracao provada
- para IAM-heavy isso gera sobreclaim:
  - o produto diz `validated` para algo que, em varios casos, e apenas
    `target observed`

## Descoberta principal

O reteste IAM-heavy mostrou um gap mais duro e mais honesto:

o primeiro `Blind Real Assessment` funcional do `aws-foundation` nao se
transfere automaticamente para um ambiente focado em privilege escalation IAM.

O problema nao e so `faltar mais profile`.

O problema e combinatorio:
- o bundle esta desalinhado
- o discovery IAM ainda e pobre para esse tipo de ofensiva
- o ranking de roles nao mede exploitability IAM
- o runtime real nao tem action space de abuse IAM
- o reporting nao separa descoberta de exploracao provada

## Interpretacao

Hoje o Rastro esta forte como:
- validador de exposure foundation
- discovery-driven em cenarios com target/resource relativamente alinhados ao
  portfolio atual

Mas ainda nao esta forte como:
- sistema capaz de enfrentar um ambiente IAM-privesc-heavy estilo
  `iam-vulnerable`

O reteste foi valioso porque deslocou a pergunta certa.

A pergunta nao e mais:
- `o blind real funciona?`

A pergunta agora e:
- `o blind real funciona quando o ambiente e dominado por classes ofensivas que
  o portfolio, o discovery e o runtime ainda nao representam bem?`

## Implicacoes arquiteturais

Antes de novo reteste IAM-heavy, o produto precisa fechar um bloco de correcao
com foco em leverage:

1. **Deduplicacao de findings e coverage**
- dedupe por:
  - `plan.id`
  - `report_json`
  - `target_resource`
  - `evidence fingerprint`
- campaigns nao podem compartilhar o mesmo diretorio por profile

2. **Distincao entre descoberta e exploracao provada**
- findings precisam de estados separados, no minimo:
  - `discovered`
  - `reachable`
  - `exploited`
  - `validated`
- `target_observed` nao deve virar automaticamente `validated`

3. **Evidencia minima por classe**
- cada classe precisa declarar o minimo de prova para virar finding final
- para `role chaining`, por exemplo, observar a role nao basta
- deve existir evidência minima de:
  - `sts:AssumeRole`
  - simulacao de policy relevante
  - ou acesso real ao proximo recurso/pivo

4. **Coverage IAM-privesc**
- o portfolio precisa abrir classes IAM-heavy reais
- o runtime real precisa suportar abuse IAM alem de `AssumeRole`
- o discovery precisa coletar grafo IAM de trust/policies

5. **Selection/ranking em ambiente dominado por IAM**
- o ranking precisa sair de nomes e ir para exploitability estrutural IAM
- ex.:
  - permissoes alteradoras
  - trust edges
  - capacidade de elevar privilegio
  - capacidade de criar novo principal ou novo compute com role

6. **Criterio de sucesso de blind real**
- proximo reteste deve medir duas coisas separadas:
  - `blind real engine quality`
  - `bundle coverage adequacy`
- um ambiente IAM-privesc-heavy nao deve ser usado como veredicto do engine
  foundation sem registrar esse desbalanceamento

## Ameacas a validade

- o reteste ocorreu no `aws-foundation`, nao em um bundle IAM-privesc dedicado
- o ambiente tinha bucket state real que puxou bastante score de S3
- algumas roles do lab podem requerer acoes ainda nao modeladas pelo produto
- portanto, o experimento nao mede `capacidade maxima teorica` do engine; mede
  o encontro entre o engine atual e um ambiente IAM-privesc-heavy

## Conclusao

EXP-085 foi um experimento ruim em cobertura, mas excelente em revelacao.

O que ficou provado:
- o Rastro ja consegue operar em `blind real`
- mas ainda subcobre severamente um ambiente IAM-privesc-heavy
- a principal lacuna atual esta em:
  - coverage ofensiva IAM
  - discovery IAM estrutural
  - action space real de abuse IAM
  - hygiene de findings/evidencia

## Proximos experimentos

- fechar um bloco de correcao antes de novo reteste IAM-heavy, cobrindo:
  - deduplicacao de campaigns/findings
  - distincao entre descoberta e exploracao provada
  - criterio de evidencia minima por classe
  - discovery IAM estrutural
  - target selection IAM-heavy
  - classes reais de privilege escalation IAM
- depois rerodar o mesmo ambiente com metricas explicitas de:
  - cobertura de classes
  - diversidade de findings
  - findings realmente provados
  - reducao de repeticao/colisao de output
