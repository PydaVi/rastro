# EXP-084 - Blind Real Runtime Action Space Pollution

- ID: EXP-084
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-04
- Status: concluida

## Contexto

Depois do `EXP-083`, o gargalo principal do `Blind Real Assessment` deixou de ser
o acoplamento direto a `fixture_path`.

Foi implementado um runtime dinamico derivado de:
- `discovery real`
- `plan.resource_arn`
- `entry_roles`

O objetivo desta etapa foi medir o proximo gargalo real depois de remover esse
acoplamento.

## Hipoteses

- H1: sem `fixture_path`, o assessment discovery-driven passara a executar
  campanhas reais em modo `real`, nao mais em `dry_run`.
- H2: o novo gargalo, se houver, aparecera na qualidade do action space
  discovery-driven e nao mais na dependencia de harness sintetico.
- H3: ambientes reais com discovery de IAM mais ruidoso revelarao poluicao de
  action space e shaping insuficiente.

## Desenho experimental

- Variavel independente:
  - reruns do mesmo `Blind Real Assessment` do `EXP-083`
- Ambiente:
  - mesma conta AWS real autorizada
  - mesmo bundle `aws-foundation`
- Criterio:
  - verificar se:
    - o run deixa de depender de fixture sintetico
    - o scope deixa de carregar recursos sinteticos
    - o planner converge em acao util no action space dinamico real

## Resultado por etapa

### Etapa R2 - runtime fixtureless revelou acoplamento de scope template

Resultado:
- as campanhas passaram a tentar execucao real
- mas falharam em `preflight`

Causa imediata observada:
- `scope.generated.json` ainda herdava:
  - `dry_run = true`
  - `allowed_resources` de templates sinteticos

Isso fez o preflight exigir roles inexistentes no ambiente real.

Intervencao aplicada:
- em modo `blind real`, o scope gerado passou a:
  - forcar `dry_run = false`
  - recomputar `allowed_resources` a partir de:
    - `plan.resource_arn`
    - roles realmente descobertas

### Etapa R3 - runtime real passou, mas o action space continuou poluido

Resultado:
- `campaigns_total = 2`
- `campaigns_passed = 1`
- `campaigns_objective_not_met = 1`
- `campaigns_preflight_failed = 0`

Artefato principal:
- `outputs_blind_real_assessment_foundation_openai/assessment.json`

O que passou:
- `aws-iam-role-chaining`

O que falhou:
- `aws-iam-s3`

Sinal arquitetural novo:
- o run agora acontece em `execution_mode = real`
- mas o planner, no caso `aws-iam-s3`, entrou em ruido de IAM:
  - enumerou roles
  - passou a preferir `assume_role`
  - sobre role descoberta dinamicamente e pouco util
  - em vez de tentar primeiro o `access_resource` exato do objetivo

O detalhe importante e que esse ruido nao veio mais de fixture sintetico.
Veio do proprio ambiente real descoberto.

## Erros, intervencoes e motivos

1. Acoplamento de scope sintetico
- o scope gerado ainda herdava `dry_run=true` e `allowed_resources` sinteticos
- isso foi corrigido no contrato de `run_generated_campaign()`

2. Prefixo sintetico de role no scope
- uma primeira tentativa de liberar `enumerate` adicionou
  `arn:aws:iam::<account>:role/` em `allowed_resources`
- o preflight passou a tratar isso como role obrigatoria inexistente
- a correcao foi remover esse prefixo e deixar `enumerate` sem target

O proximo erro a atacar, ainda sem correcao nesta etapa, ficou claro:
- `action space` discovery-driven real ainda sofre poluicao por roles
  descobertas dinamicamente mas irrelevantes
- o shaping ainda nao prioriza suficientemente `access_resource` exato do
  objetivo frente a ruido novo de IAM

## Descoberta principal

Depois de remover:
- `fixture_path` sintetico
- `scope template` sintetico indevido

o novo gargalo do `Blind Real Assessment` passou a ser outro:
- qualidade do action space discovery-driven em ambiente real ruidoso

Isso e um gargalo melhor do que o anterior:
- agora o produto esta falhando por comportamento ofensivo insuficiente
- nao mais por acoplamento direto a harness sintetico

## Interpretacao

O produto deu um passo real rumo ao polo generalista:
- a campanha deixou de ser executada por fixture pre-modelado
- o run real agora bate em ruido de ambiente, que e exatamente a classe de
  problema que importa medir

Mas ainda nao chegou ao nivel desejado:
- a inferencia de `qual acao testar primeiro` em ambiente real continua fraca
  quando discovery dinamico adiciona muitas roles pouco uteis

## Implicacoes arquiteturais

- o proximo ganho de maior leverage nao e mais:
  - remover `fixture_path`
  - remover `scope template`

- o proximo ganho passa a ser:
  - filtrar ruido estrutural obvio do action space real
  - melhorar shaping para preferir `access_resource` exato quando ele ja existe
  - separar melhor:
    - role descoberta
    - role ofensivamente expressiva

## Ameacas a validade

- o bundle foi apenas `aws-foundation`
- o ambiente tinha pouco volume de `secrets` e `ssm`
- o run ainda nao prova convergencia blind geral; ele prova que o bloqueio
  principal migrou para o action space real

## Conclusao

EXP-084 mostrou que o `Blind Real Assessment` entrou em uma fase mais valiosa:
- agora ele falha por ruido e shaping insuficiente no ambiente real
- nao mais por dependencia direta de fixture ou scope sintetico

## Proximos experimentos

- filtrar ruido estrutural obvio no action space real
- priorizar `access_resource` exato do objetivo quando ja estiver disponivel
- rerodar o mesmo blind assessment para medir se o proximo gargalo migra de
  shaping para executor, selection ou policy real

### Etapa R4 - blind real foundation convergiu apos limpeza do action space

Intervencoes aplicadas:
- filtragem de roles de ruido obvio (`aws-service-role/*`) no runtime dinamico
- restauracao explicita de `access_resource` ao objetivo final em execucao real,
  mesmo quando `ToolRegistry` bloquearia a acao por precondicoes herdadas do
  mundo sintetico
- shaping global para preferir `access_resource` exato do objetivo frente a
  ruido residual de `assume_role`

Resultado:
- `campaigns_total = 2`
- `campaigns_passed = 2`
- `campaigns_objective_not_met = 0`
- `campaigns_preflight_failed = 0`

Artefato principal:
- `outputs_blind_real_assessment_foundation_openai/assessment.json`

O que convergiu:
- `aws-iam-s3`
  - acesso real direto ao objeto:
    - `arn:aws:s3:::pydavi-terraform-state/brain-k8s-lab/dev/terraform.tfstate`
  - `proof` exportada com:
    - `bucket`
    - `object_key`
    - `accessed_via`
- `aws-iam-role-chaining`
  - objetivo satisfeito por observacao real da role-alvo no discovery de IAM

## Descoberta principal

Depois de remover:
- acoplamento a fixture
- acoplamento a scope sintetico
- e precondicoes sinteticas bloqueando probes reais diretos

o `Blind Real Assessment` foundation passou a convergir em conta AWS real sem
fixture especifico para aquele ambiente.

## Interpretacao

Esse resultado nao prova autonomia ofensiva madura.

Mas prova algo importante:
- o pipeline agora consegue sair do quadrante de `benchmark/harness`
  tambem na fase de execucao
- o gargalo principal deixou de ser infraestrutura sintetica
- o proximo bloco de maior leverage passa a ser aumentar dificuldade e
  heterogeneidade do `blind real`, nao voltar para fixture tuning

## Implicacoes arquiteturais

- o contrato de execucao discovery-driven real sem `fixture_path` passou no
  primeiro caso real util
- `ToolRegistry` preconditions sinteticas nao podem impedir probes reais
  diretos ao objetivo final em modo blind
- ruido estrutural obvio do inventario real precisa continuar sendo tratado
  como policy layer, nao como problema do LLM

## Conclusao

EXP-084 fechou o primeiro `Blind Real Assessment` funcional do foundation.

O que ficou provado:
- discovery real -> selection real -> synthesis real -> execution real
  convergem sem fixture especifico do ambiente
- o produto ja consegue operar em um primeiro modo `blind real`
  no bundle `aws-foundation`

O que ainda nao ficou provado:
- convergencia blind fora do foundation
- blind real em ambiente com maior heterogeneidade e mais targets concorrentes
- blind real em `external entry`, `compute pivot`, `advanced` ou `enterprise`
