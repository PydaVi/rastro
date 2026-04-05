# EXP-083 - Blind Real Assessment Fixture Coupling

- ID: EXP-083
- Fase: Validacao real de generalizacao ofensiva
- Data: 2026-04-04
- Status: parcial

## Contexto

Depois de fechar:
- robustez forte em benchmarks estruturados
- discovery-driven em bundles conhecidos
- `external entry` real com evidencia de rede

o principal gap do produto passou a ser outro:
- o engine operar em modo realmente `blind` sobre uma conta AWS real nao
  preparada especificamente para aquele run

Esse experimento foi o primeiro corte dessa pergunta.

## Hipoteses

- H1: o pipeline discovery-driven real consegue inventariar uma conta AWS pouco
  lembrada sem fixture especifico para o ambiente.
- H2: o target selection real consegue escolher candidatos relevantes a partir
  desse discovery.
- H3: o principal gargalo atual, se houver falha, aparecera depois de
  discovery/selection, na fronteira entre plano gerado e execucao.

## Desenho experimental

- Variavel independente:
  - conta AWS real autorizada em `examples/target_aws_blind_real.json`
  - autorizacao em `examples/authorization_aws_blind_real.json`
- Ambiente:
  - conta real previamente montada
  - topologia nao fixture-izada especificamente para o run
  - operador sem memoria detalhada do ambiente
- Criterio:
  - rodar `assessment run --bundle aws-foundation --discovery-driven`
  - registrar:
    - discovery real observado
    - candidatos escolhidos
    - planos gerados
    - ponto exato de travamento se o path nao convergir

## Resultado por etapa

### Etapa R1 - blind real assessment foundation

Comando:

```bash
RASTRO_ENABLE_AWS_REAL=1 OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python -m app.main assessment run \
  --bundle aws-foundation \
  --target examples/target_aws_blind_real.json \
  --authorization examples/authorization_aws_blind_real.json \
  --out outputs_blind_real_assessment_foundation_openai \
  --max-steps 9 \
  --discovery-driven
```

Resultado:
- `campaigns_total = 2`
- `campaigns_passed = 0`
- `campaigns_objective_not_met = 2`
- `assessment_ok = true`

Artefatos:
- `outputs_blind_real_assessment_foundation_openai/assessment.json`
- `outputs_blind_real_assessment_foundation_openai/assessment.md`
- `outputs_blind_real_assessment_foundation_openai/discovery/discovery.json`
- `outputs_blind_real_assessment_foundation_openai/target-selection/target_candidates.json`
- `outputs_blind_real_assessment_foundation_openai/campaign-synthesis/campaign_plan.json`

O discovery real funcionou:
- `33` resources
- `11` relationships
- tipos observados:
  - `identity.role`
  - `data_store.s3_bucket`
  - `data_store.s3_object`
  - `compute.ec2_instance`
  - `compute.instance_profile`
  - `network.internet_gateway`
  - `network.load_balancer`
  - `network.lb_listener`
  - `network.route_table`
  - `network.security_group`
  - `network.subnet`
  - `network.target_group`

Resumo de inventory:
- Roles: `4`
- Buckets: `1`
- Objects: `8`
- Secrets: `0`
- Parameters: `0`
- Instance profiles: `1`
- Instances: `5`
- Load balancers: `1`

O target selection tambem funcionou em primeiro corte:
- os principais candidatos vieram do bucket real
  `arn:aws:s3:::pydavi-terraform-state/.../terraform.tfstate`
- um candidato de `aws-iam-role-chaining` tambem foi selecionado a partir de
  role real descoberta

O travamento apareceu na execucao:
- os candidatos e planos gerados continuaram carregando:
  - `execution_fixture_set`
  - `fixture_path`
  - `scope_template_path`
- exemplos observados:
  - `fixtures/mixed_generalization_iam_s3_lab.json`
  - `fixtures/compute_pivot_app_unified_lab.json`

Na pratica, o `blind real assessment` caiu de volta em campanhas guiadas por
fixture sintetico mesmo depois de discovery e selection reais.

## Erros, intervencoes e motivos

Nao houve falha de infraestrutura AWS:
- preflight passou
- discovery rodou
- selection rodou
- synthesis rodou

Tambem nao houve falha primaria de acesso ao executor real.

A falha principal foi arquitetural:
- `run_generated_campaign()` ainda depende de `fixture_path`
- `execute_run()` ainda exige `Fixture.load(fixture_path)`
- portanto, a fase de execucao continua acoplada a campanhas
  previamente modeladas em harness sintetico

Esse acoplamento transforma o `blind real assessment` em:
- discovery real
- selection real
- mas execucao ainda dependente de fixtures sinteticos por familia

## Descoberta principal

O primeiro `blind real assessment` respondeu a pergunta certa:
- o gargalo dominante atual nao esta em discovery
- nao esta em preflight
- nao esta em acesso AWS real

O gargalo esta no contrato de execucao do assessment discovery-driven:
- o pipeline ainda precisa degradar para fixture set sintetico para executar
  campanhas

## Interpretacao

Isso reposiciona o gap principal do produto.

O problema nao e mais:
- conseguir selecionar alvos em ambiente desconhecido

O problema agora e:
- executar campanhas discovery-driven reais sem depender de uma maquina de
  estados sintetica pre-modelada para aquele ambiente

Em outras palavras:
- o produto ja se comporta como `blind real` ate o fim de selection
- mas ainda nao ate o fim da execucao

## Implicacoes arquiteturais

- `Blind Real Assessment` nao pode ser considerado concluido
- o proximo bloco de maior leverage deixa de ser benchmark adicional
- o novo gargalo central passa a ser:
  - desacoplar a execucao discovery-driven de `fixture_path`
  - construir um contrato de execucao real orientado a action space real,
    nao a transicoes sinteticas pre-modeladas

## Ameacas a validade

- o teste usou apenas `aws-foundation`
- a conta observada tinha baixo volume de secrets/parameters
- o run nao prova ainda se um action-space real sem fixture convergira bem;
  ele prova apenas que o acoplamento atual impede medir isso

## Conclusao

EXP-083 foi negativo no resultado final, mas positivo arquiteturalmente.

O que ficou provado:
- discovery real de conta pouco lembrada funciona
- target selection real funciona em primeiro corte
- o principal gargalo atual do Produto 01 rumo ao polo generalista e o
  acoplamento entre campaign execution e fixture sintetico

## Proximos experimentos

- definir e implementar um contrato de execucao discovery-driven real sem
  `fixture_path`
- rerodar o `Blind Real Assessment` no mesmo ambiente para medir o novo gargalo
- so depois retomar benchmark sintetico adicional se ele responder a uma
  pergunta arquitetural nova
