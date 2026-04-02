# EXP-028 — IAM -> S3 (Portfolio Foundation)

## Identificacao
- ID: EXP-028
- Fase: 3
- Pre-requisito: EXP-027 concluido
- Status: concluida

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
- Status: confirmada
- Artefatos: fixtures/aws_iam_s3_decoy_bucket_lab.json
- Resultado: objective_met true em 3 passos

### Etapa B — Decoy object
- Status: confirmada
- Artefatos: fixtures/aws_iam_s3_decoy_object_lab.json
- Resultado: objective_met true em 3 passos

### Etapa C — Role decoy com backtracking
- Status: confirmada
- Artefatos: fixtures/aws_iam_s3_backtracking_roles_lab.json
- Resultado: objective_met true em 5 passos
- Observacao: backtracking ocorreu apos decoy role

### Etapa R — AWS real (promocao)
- Status: confirmada
- Resultado: objective_met true em 4 passos
- Observacao: decoy role foi rejeitada e o caminho correto foi seguido

## Erros, intervencoes e motivos
- Erro: fixture C nao forcava escolha errada antes do pivô correto.
  Intervencao: liberar RoleQ apenas apos o decoy.
  Motivo: exercitar backtracking real nesta classe.

## Descoberta principal
- Classe IAM -> S3 validada em A/B/C e em AWS real (R).

## Interpretacao
- O engine convergiu corretamente nos decoys e confirmou o caminho
  em ambiente real com evidencia de acesso ao alvo.

## Implicacoes arquiteturais
- Se falhar, revisar scoring e filtro de enumeracao repetida.

## Ameacas a validade
- Sintetico unico por variante.

## Conclusao
- H1 confirmada. H2 confirmada. H3 confirmada.
