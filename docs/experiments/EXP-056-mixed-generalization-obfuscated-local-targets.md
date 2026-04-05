# EXP-056 — Mixed Generalization Obfuscated Local Targets

## Identificacao

- ID: EXP-056
- Fase: Prioridade 3 / generalizacao ofensiva
- Data: 2026-04-01
- Status: concluida

## Contexto

Depois de `EXP-055`, o benchmark misto enterprise ja tinha reduzido bastante o
apoio lexical nos alvos profundos. O proximo passo natural era começar a fazer
o mesmo nos alvos locais que ainda eram muito evidentes, especialmente:

- S3 local
- SSM local

O secret local compartilhado com `external-entry` foi deixado de fora deste
bloco para nao misturar a reducao de naming com um fixture mais sensivel.

## Hipoteses

H1. O benchmark poderia obfuscar o alvo local de S3 e o alvo local de SSM sem
quebrar o assessment discovery-driven ponta a ponta.

H2. O selection continuaria escolhendo corretamente esses alvos locais mesmo com
menos apoio lexical direto no nome final do recurso.

## Desenho experimental

### Variavel independente

Foi criada:

- `fixtures/mixed_generalization_variant_k.discovery.json`

Mudancas principais:

- S3 local:
  - `payroll/2026-03/payroll.csv` -> `data/2026-03/r1.bin`
- SSM local:
  - `/prod/payroll/api_key` -> `/prod/app/cfg_a`

### Ajuste de harness

Os fixtures sinteticos correspondentes foram expandidos para suportar os novos
aliases:

- `fixtures/mixed_generalization_iam_s3_lab.json`
- `fixtures/serverless_business_app_iam_ssm_lab.json`

## Resultados por etapa

### Etapa 1 — Selection

Confirmada.

Top candidates observados:

- `aws-iam-s3`
  - `arn:aws:s3:::mixed-payroll-data-prod/data/2026-03/r1.bin`
- `aws-iam-ssm`
  - `arn:aws:ssm:us-east-1:123456789012:parameter/prod/app/cfg_a`

Ponto importante:

- `aws-iam-ssm` deixou de depender de `api_key` como keyword hit no alvo final

### Etapa 2 — Assessment discovery-driven ponta a ponta

Confirmada.

Output gerado:

- `outputs_mixed_generalization_variant_k_assessment/`

Resumo observado:

- `campaigns_total = 9`
- `campaigns_passed = 9`
- `assessment_ok = true`

## Erros, intervencoes e motivos

Nao houve falha experimental do engine neste bloco.

O unico trabalho adicional foi ampliar o harness sintetico para aceitar os
novos aliases locais sem quebrar variantes anteriores.

## Descoberta principal

O benchmark misto enterprise continua estavel mesmo com os alvos locais de S3 e
SSM menos evidentes semanticamente.

## Interpretacao

Esse bloco reduz mais um tipo de atalho:

- nomes finais locais muito “explicativos”

O selection ainda preserva os melhores alvos porque:

- a estrutura do inventario continua forte
- a classificacao do recurso continua informativa
- o scorer nao depende mais apenas do nome final do alvo

## Implicacoes arquiteturais

- o benchmark misto agora mede melhor robustez local sob naming desfavoravel
- o caminho para obfuscar tambem o secret local fica mais claro, mas requer
  cuidado extra porque ele e compartilhado com `external-entry`
- o harness sintetico continua precisando aceitar aliases para nao confundir
  ganho de generalizacao com mismatch artificial de fixture

## Ameacas a validade

- o bucket local ainda preserva `mixed-payroll-data-prod`, entao ainda existe
  algum apoio lexical no caminho S3
- o secret local principal ainda continua semanticamente forte

## Conclusao

H1 e H2 confirmadas.

O benchmark misto enterprise permaneceu estavel com alvos locais de S3 e SSM
menos evidentes.

## Proximos passos

1. atacar o secret local compartilhado com `external-entry` sem causar drift de
   harness
2. continuar reduzindo naming favorecido onde o ganho arquitetural for maior do
   que o custo de fixture
3. medir explicitamente quando o componente estrutural sustenta candidatos com
   pouco apoio lexical local
