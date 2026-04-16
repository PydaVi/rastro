# EXP-091 — Distinct path coverage metrics first pass

- ID: EXP-091
- Fase: Reestruturacao do nucleo para verdade de path e distinctness
- Data: 2026-04-04
- Status: concluido

## Contexto

Depois do primeiro corte de `truthfulness`, o produto ainda nao media coverage da
forma correta.

Mesmo com findings agregados por `distinct_path_key`, o output principal ainda nao
expunha com clareza a diferenca entre:
- volume bruto vindo de campaigns
- quantidade de paths distintos
- multiplicidade de principal sobre o mesmo path

Sem isso, um novo reteste IAM-heavy ainda correria risco de inflar a leitura de
coverage por puro volume.

## Hipoteses

1. O `assessment_findings` precisa carregar metricas explicitas de distinctness.
2. O resumo principal precisa mostrar separadamente:
   - total de findings fonte por campaign
   - total de paths distintos
   - multiplicidade total de principals
   - principals adicionais acima do numero de paths
3. Essas metricas sao um pre-requisito para reler o reteste IAM-heavy sem
   autoengano.

## Desenho experimental

Variavel independente:
- adicao de metricas de distinct path e multiplicidade no summary de
  `assessment_findings`

Ambiente:
- suite offline focada em agregacao de findings

Criterio:
- dois campaigns com o mesmo path e principals diferentes devem produzir:
  - `source_campaign_findings_total = 2`
  - `distinct_paths_total = 1`
  - `principal_multiplicity_total = 2`
  - `additional_principal_observations = 1`

## Resultados por etapa

1. `assessment_findings.json`
- passou a registrar:
  - `source_campaign_findings_total`
  - `distinct_paths_total`
  - `principal_multiplicity_total`
  - `additional_principal_observations`
  - `paths_with_multiple_principals`
  - `principal_multiplicity_by_profile`

2. `assessment_findings.md`
- passou a expor essas metricas no topo do documento
- isso torna visivel quando o volume bruto excede a diversidade estrutural real

3. Validacao offline
- campaigns identicos com principals diferentes colapsaram corretamente em um
  finding unico com multiplicidade `2`
- o markdown passou a evidenciar a diferenca entre `source campaigns` e
  `distinct paths`

## Erros, intervencoes e motivos

Nenhuma intervencao estrutural adicional foi necessaria alem da extensao do
summary e dos testes.

## Descoberta principal

Distinctness so com deduplicacao por fingerprint ainda nao basta.

O produto tambem precisa mostrar, no output principal, o quanto do volume bruto
vem de repeticao por principal. Sem isso, o operador continua suscetivel a ler
84 findings como 84 paths.

## Interpretacao

Este experimento continua no eixo de honestidade epistemologica.
Nao aumenta coverage ofensiva.
Aumenta a capacidade de medir corretamente a falta dela.

## Implicacoes arquiteturais

- todo reteste IAM-heavy deve ser lido primeiro por `distinct_paths_total` e nao
  por `findings_total` bruto vindo de campaigns
- multiplicidade de principal deve continuar como dimensao separada da verdade de
  path
- o proximo passo ainda nao e rerun; e ampliar runtime/portfolio IAM-heavy sob
  esse contrato de leitura mais honesto

## Ameacas a validade

- `distinct_path_key` continua sendo aproximacao estrutural e nao semantica
  ofensiva completa
- a metrica ainda nao distingue, sozinha, paths semanticamente diferentes com a
  mesma sequencia superficial de steps

## Conclusao

O produto agora mede melhor o que foi provado por path distinto e o que e apenas
repeticao por principal.

Isso nao melhora a capacidade ofensiva do Rastro, mas melhora a capacidade de
nao mentir sobre ela.

## Proximos experimentos

1. ampliar distinctness para uma semantica mais ofensiva do path
2. abrir runtime/portfolio IAM-heavy sob esse contrato
3. so depois rerodar o ambiente IAM-heavy simples
