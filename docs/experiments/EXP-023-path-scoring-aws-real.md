# EXP-023 — Path Scoring em AWS Real (Sinal Novo)

## Identificacao
- ID: EXP-023
- Fase: 3
- Pre-requisito: EXP-022 concluido
- Status: concluida

## Contexto
EXP-021/022 fecharam o path scoring em dry_run sob lookahead ambiguo e
limite apertado de passos. EXP-023 valida em AWS real que o engine
mantem a escolha correta de pivô quando existe bucket decoy em conta
real, sem regressao de scoring/shaping.

## Hipoteses
H1: o planner converge para o role correto e acessa o objeto sensivel
    em AWS real dentro de max_steps=6.

H2: a presenca de bucket decoy em conta real nao desvia o caminho.

## Desenho experimental

### Variavel independente
- execucao real em AWS (RASTRO_ENABLE_AWS_REAL=1)
- planner OpenAI

### Ambiente
- conta: 550192603632
- bucket alvo: sensitive-finance-data
- bucket decoy: public-reports-550192603632
- roles: AuditRole (caminho correto), BucketReaderRole (decoy)

### Artefatos
- `terraform_local_lab/rastro_local/aws_role_choice_lab.local.json`
- `terraform_local_lab/rastro_local/objective_aws_role_choice.local.json`
- `terraform_local_lab/rastro_local/scope_aws_role_choice_openai_real.local.json`

### Criterio de sucesso
- objective_met true
- acesso confirmado ao `arn:aws:s3:::sensitive-finance-data/payroll.csv`

## Resultados por etapa

### Etapa 1 — Execucao AWS real com OpenAIPlanner
- Status: confirmada
- Resultado: objective_met true em 4 passos
- Passos: enumerate roles -> assume role correto -> list bucket -> get object sensivel
- Observacao: bucket decoy nao foi escolhido como pivô

## Erros, intervencoes e motivos
- Nenhum.

## Descoberta principal
- Path scoring + action shaping mantem a escolha correta de pivô em AWS real
  mesmo com bucket decoy acessivel.

## Interpretacao
- O scoring se manteve consistente fora do simulador e nao houve regressao
  de ordem ou desviacao para o caminho decoy.

## Implicacoes arquiteturais
- Se falhar, revisar integracao real do scoring com decoys reais.

## Ameacas a validade
- Apenas um ambiente real.
- Dois pivots apenas.

## Conclusao
- H1 confirmada. H2 confirmada.
