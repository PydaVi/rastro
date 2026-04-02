# EXP-030 — IAM -> SSM Parameter Store (Portfolio Foundation)

## Identificacao
- ID: EXP-030
- Fase: 3
- Pre-requisito: EXP-029 concluido
- Status: concluida

## Contexto
Terceira classe do portfólio foundation. Objetivo: validar IAM -> SSM Parameter
Store com selecao correta de parametro e backtracking antes da promocao para AWS real.

## Hipoteses
H1: o engine escolhe o parametro correto quando existe um decoy no mesmo path.
H2: o engine realiza backtracking quando a role inicial nao leva ao parametro alvo.

## Desenho experimental

### Variavel independente
- dois fixtures sinteticos: decoy parameter e role decoy com backtracking
- planner OpenAI

### Ambiente
- SSM Parameter Store com parametro alvo e parametro decoy
- roles com acesso parcial por path

### Criterio de sucesso
- objective_met true em cada variante
- sem loops de enumerate ou assume_role repetido

## Resultados por etapa

### Etapa A — Decoy parameter
- Status: confirmada
- Artefatos: fixtures/aws_iam_ssm_decoy_parameter_lab.json
 - Resultado: objective_met true em 4 passos
 - Observacao: o engine ignorou o parametro decoy no mesmo path.

### Etapa B — Role decoy com backtracking
- Status: confirmada
- Artefatos: fixtures/aws_iam_ssm_backtracking_roles_lab.json
 - Resultado: objective_met true em 7 passos
 - Observacao: backtracking ocorreu apos enumerate do parametro decoy em RoleA.

### Etapa R — AWS real (promocao)
- Status: confirmada
- Artefatos: outputs_real_exp30r_iam_ssm_openai/report.md
 - Resultado: objective_met true em 5 passos
 - Observacao: validou a cadeia IAM -> SSM Parameter Store em AWS real, com
   enumeracao e leitura real do parametro alvo; o planner escolheu RoleM
   diretamente, sem stress de backtracking no run real.

## Erros, intervencoes e motivos
- Nao houve falha de engine nas etapas A/B/R.
- Intervencao operacional: os runs sinteticos precisaram ser rerodados com
  rede liberada no ambiente do agente para acessar a API OpenAI.

## Descoberta principal
- Classe IAM -> SSM confirmada no portfolio foundation.
- O engine distingue parametro alvo de parametro decoy no mesmo path e realiza
  backtracking quando a role inicial revela apenas sinal enganoso.

## Interpretacao
- O comportamento observado em EXP-017 foi reproduzido agora no formato de
  classe de portfólio: uma variante focada em selecao de alvo e outra focada
  em recuperacao de pivô errado.
- A promocao real provou a cadeia end-to-end do Produto 01 para SSM.

## Implicacoes arquiteturais
- A combinacao `enumerate -> analyze -> access_resource` continua geral para
  superfícies de segredo configuracional.
- O portfólio foundation agora cobre tres classes com evidência real: S3,
  Secrets Manager e SSM Parameter Store.

## Ameacas a validade
- O run real nao exigiu backtracking; ele confirmou a cadeia real, nao a
  recuperacao de dead-end em ambiente AWS.

## Conclusao
- H1 confirmada. H2 confirmada.
- A classe 3 do portfólio foundation esta fechada para o eixo AWS.
