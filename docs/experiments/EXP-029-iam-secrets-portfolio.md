# EXP-029 — IAM -> Secrets Manager (Portfolio Foundation)

## Identificacao
- ID: EXP-029
- Fase: 3
- Pre-requisito: EXP-028 concluido
- Status: concluida

## Contexto
Segunda classe do portfólio foundation. Objetivo: validar IAM -> Secrets Manager
com variacoes de decoy secret e backtracking antes da promocao para AWS real.

## Hipoteses
H1: o engine escolhe o segredo correto quando existe decoy.
H2: o engine ignora segredo decoy no mesmo prefixo.
H3: o engine realiza backtracking quando a role decoy nao leva ao alvo.

## Desenho experimental

### Variavel independente
- tres fixtures sinteticos com decoy secret, decoy prefix e role decoy
- planner OpenAI

### Ambiente
- Secrets Manager com segredo alvo e decoy
- roles com acesso parcial

### Criterio de sucesso
- objective_met true em cada variante
- sem loops de enumerate

## Resultados por etapa

### Etapa A — Decoy secret
- Status: confirmada
- Artefatos: fixtures/aws_iam_secrets_decoy_secret_lab.json
 - Resultado: objective_met true em 3 passos

### Etapa B — Decoy prefix
- Status: confirmada
- Artefatos: fixtures/aws_iam_secrets_decoy_prefix_lab.json
 - Resultado: objective_met true em 3 passos

### Etapa C — Role decoy com backtracking
- Status: confirmada
- Artefatos: fixtures/aws_iam_secrets_backtracking_roles_lab.json
 - Resultado: objective_met true em 5 passos
 - Observacao: backtracking ocorreu apos decoy role

### Etapa R — AWS real (promocao)
- Status: confirmada
- Artefatos: outputs_real_exp29r_iam_secrets_openai/report.md
 - Resultado: objective_met true em 5 passos
 - Observacao: validou a cadeia IAM -> Secrets Manager em AWS real, mas o
   planner escolheu RoleM diretamente; este run nao estressou backtracking real.

## Erros, intervencoes e motivos
- Erro: fixture C nao liberou o pivô correto apos o decoy (RoleQ nunca aparece).
  Classificacao: falha de infraestrutura (fixture).
  Intervencao: adicionar update de identity para liberar RoleQ
  apos o dead-end.

- Erro: assume_role repetido para role falhada nao foi filtrado.
  Classificacao: falha de policy (action shaping insuficiente).
  Intervencao: filtrar assume_role em failed_assume_roles
  em todos os caminhos de action shaping.

## Descoberta principal
- Classe IAM -> Secrets validada em A/B/C e confirmada em AWS real.
- O backtracking foi provado no sintetico C; a promocao real provou acesso
  end-to-end com evidência real, mas nao exigiu recuperacao de dead-end.

## Interpretacao
- O engine convergiu corretamente nos decoys e realizou backtracking
  quando o role decoy foi escolhido primeiro.
- Em AWS real, a classe esta operacionalmente validada para Produto 01:
  enumerate -> assume_role -> list_secrets -> read_secret.

## Implicacoes arquiteturais
- Se falhar, revisar scoring e filtro de enumerate repetida.

## Ameacas a validade
- Sintetico unico por variante.

## Conclusao
- H1 confirmada. H2 confirmada. H3 confirmada.
- A classe 2 do portfólio foundation esta fechada para o eixo AWS.
