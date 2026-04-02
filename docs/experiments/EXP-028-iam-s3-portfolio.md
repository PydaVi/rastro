# EXP-028 — IAM -> S3 (Portfolio Foundation)

## Identificacao
- ID: EXP-028
- Fase: 3
- Pre-requisito: EXP-027 concluido
- Status: planejada

## Contexto
Primeira classe do portfólio foundation. Objetivo: validar IAM -> S3
com variacoes de decoy e backtracking antes de promocao para AWS real.

## Hipoteses
H1: o engine identifica o bucket correto mesmo com decoy bucket.
H2: o engine ignora objeto decoy no mesmo bucket e acessa o alvo.
H3: o engine realiza backtracking quando a role decoy nao leva ao alvo.

## Desenho experimental

### Variavel independente
- tres fixtures sinteticos com decoy bucket, decoy object e role decoy
- planner OpenAI

### Ambiente
- S3 com bucket alvo e bucket/objeto decoy
- roles com acesso parcial

### Criterio de sucesso
- objective_met true em cada variante
- sem loops de enumerate

## Resultados por etapa

### Etapa A — Decoy bucket
- Status: pendente
- Artefatos: fixtures/aws_iam_s3_decoy_bucket_lab.json

### Etapa B — Decoy object
- Status: pendente
- Artefatos: fixtures/aws_iam_s3_decoy_object_lab.json

### Etapa C — Role decoy com backtracking
- Status: pendente
- Artefatos: fixtures/aws_iam_s3_backtracking_roles_lab.json

### Etapa R — AWS real (promocao)
- Status: pendente
- Critério: A/B/C confirmadas

## Erros, intervencoes e motivos
- Nenhum ate o momento.

## Descoberta principal
- Pendente.

## Interpretacao
- Pendente.

## Implicacoes arquiteturais
- Se falhar, revisar scoring e filtro de enumeracao repetida.

## Ameacas a validade
- Sintetico unico por variante.

## Conclusao
- Pendente.
