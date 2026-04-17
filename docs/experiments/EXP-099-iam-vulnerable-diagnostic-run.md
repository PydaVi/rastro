# EXP-099 — Diagnostic Run: iam-vulnerable (BishopFox)

- ID: EXP-099
- Fase: Diagnostico de generalizacao ofensiva
- Data: 2026-04-16
- Status: concluido

## Contexto

Rodamos o engine contra um ambiente AWS real com o lab `iam-vulnerable` da BishopFox deployado.
O lab contem 31 paths de privilege escalation conhecidos, 42 usuarios vulneraveis, 37 roles,
e um usuario administrador (`brainctl-user` com AdministratorAccess).

Objetivo do experimento: entender por que o engine nao encontra vulnerabilidades em conta real
com decenas de paths conhecidos.

## Hipoteses testadas

1. O engine consegue identificar paths de privesc IAM a partir de discovery real?
2. O LLM configurado (OpenAI) esta sendo usado nas campanhas?
3. O target selection escolhe targets relevantes para o lab?

## Ambiente

- AWS Account: 550192603632
- Entry identity: `arn:aws:iam::550192603632:user/brainctl-user` (AdministratorAccess)
- Roles no lab: 37 (incluindo 31 com nome `privesc-*`)
- Usuarios no lab: 42 (incluindo 31 com nome `privesc-*-user`)
- Bundle usado: `aws-foundation`
- Max steps: 9

## Resultados por etapa

### Etapa 1 — Discovery

Discovery encontrou 105 recursos:
- 46 `identity.role`
- 42 `identity.user`
- 8 `data_store.s3_object` (terraform state files)
- 1 `data_store.s3_bucket`
- 1 `compute.instance_profile`
- Redes/VPC: 7

Todos os 31 roles privesc e 31 usuarios privesc foram encontrados.
**Discovery funcionou corretamente.**

### Etapa 2 — Target Selection

De 105 recursos, selecionou 10 targets:
- `aws-iam-role-chaining`: 5 roles (por score de keyword — `privesc-sageMaker*` e `fn1-*`)
- `aws-iam-s3`: 5 objetos S3 (terraform.tfstate files)

O que NAO foi selecionado:
- 41 roles privesc restantes
- 42 usuarios (que sao os vetores de ataque reais)
- Nenhum raciocinio sobre permissoes dos principals

**Target selection falhou completamente.** Os 5 roles escolhidos foram por coincidencia de
scoring de keyword, nao por relevancia ofensiva. Os 5 targets S3 sao arquivos de estado
Terraform — nao sao targets do iam-vulnerable.

### Etapa 3 — Campaign Synthesis

As campanhas geradas usaram `scope_template_path` de arquivos sinteticos
(`examples/scope_compute_pivot_app_iam_s3.json`) com `planner: {backend: "mock"}`.

O `_infer_execution_fixture_set` retornou `"mixed-generalization"` para os candidatos S3,
e o scope template correspondente nao tem o planner OpenAI configurado.

**Resultado: todas as 84 campanhas rodaram com mock planner, nao com OpenAI.**

### Etapa 4 — Campaigns

84 campanhas executadas (10 targets x ~42 entry identities — todos os usuarios descobertos
foram tratados como potenciais entry identities por `_blind_real_entry_identities`).

Comportamento do mock planner com action_shaping:
- `_prefer_access_on_success` filtrou para apenas `access_resource`
- Mock planner repetiu a mesma acao 7x por campanha
- `brainctl-user` tem AdministratorAccess, entao `iam:SimulatePrincipalPolicy` retorna
  `allowed` para tudo — mas o `objective_met` nunca foi setado

**0 campaigns passadas. 4 findings fracos (todos `observed`).**

## Root causes identificados

### RC-1: Target selection cega a permissoes

O engine mapeia `resource_type` → `profile`. Um `identity.role` vira `aws-iam-role-chaining`.
Nunca pergunta: "o principal de entrada tem permissoes para explorar esse role?"
Nunca pergunta: "quais permissoes o principal tem que habilitam privesc?"

Para o iam-vulnerable, todos os 31 paths comecam de um usuario com uma permissao especifica
(ex: `iam:CreatePolicyVersion`, `iam:AttachRolePolicy`, `iam:PassRole`). O engine nao modela isso.

### RC-2: Synthetic fixture contamination

`_infer_execution_fixture_set` roteia recursos de ambiente real para fixtures sinteticos.
Para `aws-iam-s3`, sempre retorna `"mixed-generalization"`, cujo scope template usa `planner: mock`.

Isso e a contaminacao sintetica que AGENTS.md chama de "suspeita arquitetural seria".
Em ambiente real, o resultado e: LLM nunca e chamado.

### RC-3: LLM entra tarde demais

O LLM so entra na fase de *execucao* — escolhendo entre acoes pre-filtradas.
Nao raciocina sobre o ambiente, nao forma hipoteses, nao prioriza paths.
O espaco de acoes que recebe e determinado por regras estaticas, nao por raciocinio.

### RC-4: Entry identity explosion

`_blind_real_entry_identities` retornou todos os 42 usuarios descobertos como entry identities.
Isso multiplicou o numero de campanhas (10 targets x 42 = 420 possiveis, 84 rodaram).
A maioria delas e sem sentido — `privesc-ssmSendCommand-user` como entry para S3 target.

### RC-5: Mock planner em loop determinístico

Com `_prefer_access_on_success` ativo e access_resource disponivel,
o mock planner repete a mesma acao. Nenhum progresso estrutural.

## Descoberta principal

O engine nao falhou por falta de profiles ou por falta de LLM externo.
Ele falhou porque **o LLM nao entra no momento certo do pipeline**.

O raciocinio sobre "o que e exploravel neste ambiente" precisa acontecer *antes* da selecao
de targets — nao depois. A target selection rule-based e incapaz de responder:

> "O usuario X tem `iam:CreatePolicyVersion`. O que isso habilita neste ambiente especifico?"

Essa pergunta so o LLM consegue responder bem, com o discovery como contexto.

## Implicacoes arquiteturais

1. **StrategicPlanner** e necessario: interface que recebe o discovery snapshot e retorna
   hipoteses de ataque estruturadas. Substitui (ou precede) a target selection rule-based.

2. **Discovery precisa ser enriquecido**: alem de `resource_type`, precisa capturar
   policies attached por principal e permissoes-chave relevantes para privesc.

3. **Synthetic fixture contamination deve ser removida** de runs reais: o `scope.planner`
   configurado pelo usuario deve ser sempre preservado.

4. **Entry identities devem ser o principal ativo**, nao todos os usuarios descobertos.
   Usuarios descobertos sao *targets potenciais de escalada*, nao pontos de entrada.

## Conclusao

Este experimento confirmou o diagnostico do PLAN.md: o engine esta no polo `campaign validator`.

O trabalho necessario esta documentado como Bloco 1 em PLAN.md:
implementar `StrategicPlanner` para que o LLM razocine sobre o discovery
*antes* de gerar campanhas.

## Proximos experimentos

1. EXP-100: Bloco 1 Passo 1 — StrategicPlanner interface + MockStrategicPlanner
2. EXP-101: Bloco 1 Passo 2 — Discovery enriquecido com permissoes por principal
3. EXP-102: Bloco 1 Passo 3 — OpenAICompatibleStrategicPlanner
4. EXP-103: Re-run iam-vulnerable com StrategicPlanner — benchmark real
