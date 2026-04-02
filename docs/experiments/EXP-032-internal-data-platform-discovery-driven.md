# EXP-032 — Internal Data Platform Discovery-Driven Validation

## Identificação
- ID: EXP-032
- Fase: 3
- Status: confirmada

## Contexto
Depois de validar o `aws-foundation` em ambientes pequenos e em AWS real, o próximo risco arquitetural era o pipeline discovery-driven depender demais de labs mínimos. O objetivo deste experimento foi provar que discovery, target selection, campaign synthesis e execução continuam coerentes em um ambiente sintético maior, com naming corporativo plausível e ruído semântico.

## Hipóteses
- H1: o pipeline discovery-driven consegue gerar campanhas executáveis para o arquétipo `internal-data-platform`.
- H2: as três variantes A/B/C mantêm o bundle `aws-foundation` operacional ponta a ponta.
- H3: falhas reveladas por variantes maiores devem apontar para gaps gerais do engine operacional, não para remendos específicos do ambiente.

## Desenho experimental

### Variável independente
- três snapshots de discovery do arquétipo `internal-data-platform`
  - Variante A: ruído baixo
  - Variante B: ruído médio
  - Variante C: ruído alto

### Ambiente
- superfícies: IAM, S3, Secrets Manager, SSM
- bundle validado: `aws-foundation`
- execução: `assessment run` discovery-driven sobre profiles sintéticos do arquétipo

### Critério de sucesso
- `campaigns_total = 4`
- `campaigns_passed = 4`
- zero `preflight_failed`
- zero `run_failed`

## Resultados por etapa

### Etapa 1 — Primeira execução end-to-end
- Resultado: falhou parcialmente
- Sintoma: todas as 4 campanhas ficaram em `objective_not_met`
- O que foi revelado:
  - o scope gerado estava herdando apenas `target.accounts`, o que descartava accounts implícitas no próprio campaign sintético
  - `ToolRegistry` dependia de flags explícitas no fixture, e os novos labs não propagavam pós-condições automaticamente
  - objetivos gerados continuavam dependentes do `flag` base, mesmo quando o campaign já havia alcançado o `objective.target`

### Etapa 2 — Correções gerais
- Resultado: correções aplicadas ao engine operacional
- Correções:
  - `campaign_synthesis` agora mescla `aws_account_ids` e `allowed_regions` com o que está implícito nos próprios recursos do campaign
  - `StateManager.snapshot()` agora deriva flags ativas a partir das `postconditions` das tools executadas com sucesso
  - `StateManager.is_objective_met()` agora reconhece objetivo atingido quando uma ação bem-sucedida alcança exatamente `objective.target`

### Etapa 3 — Reexecução das variantes A/B/C
- Variante A: `campaigns_passed = 4/4`
- Variante B: `campaigns_passed = 4/4`
- Variante C: `campaigns_passed = 4/4`

## Erros, intervenções e motivos

### Erro 1 — Scope gerado com account errada para campaign sintético
- Sintoma: após a enumeração inicial, todas as ações seguintes eram removidas
- Causa raiz: `campaign_synthesis` ancorava `aws_account_ids` exclusivamente no `TargetConfig`
- Intervenção: mesclar accounts e regions extraídos dos `allowed_resources` e do `resource_arn` do candidato
- Motivo: o scope gerado precisa refletir o campaign derivado, não só o ambiente operacional externo

### Erro 2 — Pós-condições de tool não apareciam no snapshot
- Sintoma: `iam_passrole` ficava bloqueado após `iam_list_roles`
- Causa raiz: o engine dependia de `add_flags` explícito no fixture para representar pós-condições já conhecidas do Tool Registry
- Intervenção: derivar flags ativas a partir das `postconditions` das tools bem-sucedidas
- Motivo: isso reduz acoplamento do engine à implementação manual de flags em cada fixture

### Erro 3 — Objetivo gerado dependia do flag base em vez do alvo alcançado
- Sintoma: o campaign lia o recurso correto, mas `objective_met` seguia `False`
- Causa raiz: `is_objective_met()` só aceitava `success_criteria.flag`
- Intervenção: aceitar também “ação bem-sucedida cujo `target` é igual a `objective.target`”
- Motivo: campanhas geradas dinamicamente precisam reconhecer sucesso pelo alvo atingido, não só por sinalização manual do fixture

## Descoberta principal
O primeiro gap real do pipeline discovery-driven em ambientes maiores não estava no planner, mas no contrato entre campaign synthesis, Tool Registry e critério de sucesso. O engine precisava reconhecer contexto derivado do campaign e sucesso por alvo alcançado, não só por flags estáticas.

## Interpretação
- O pipeline discovery-driven já era funcional no `aws-foundation` real, mas ainda carregava pressupostos de labs pequenos.
- Ambientes sintéticos maiores revelaram três dependências rígidas:
  - account derivada apenas do target
  - pós-condições dependentes do fixture
  - sucesso dependente de flag estática
- As três correções são gerais e fortalecem o Produto 01 como sistema operacional, não só este arquétipo.

## Implicações arquiteturais
- campaign synthesis precisa ser orientado pelo campaign derivado, não só pelo target
- Tool Registry deve poder enriquecer o estado do engine sem exigir mutação manual do fixture
- objetivos gerados dinamicamente precisam suportar semântica “target reached”

## Ameaças à validade
- o arquétipo ainda cobre apenas `foundation`
- a variante `internal-data-platform` continua IAM-first, sem compute ou external entry
- role chaining continua modelado com objetivo de pivô, não ainda com objetivo final de dado no campaign gerado

## Conclusão
- H1: confirmada
- H2: confirmada
- H3: confirmada

O pipeline discovery-driven do Produto 01 agora foi validado ponta a ponta em três ambientes sintéticos maiores, com correções estruturais no engine operacional.

## Próximos passos
- revalidar o mesmo pipeline em `serverless-business-app`
- endurecer a semântica de `aws-iam-role-chaining` para gerar objetivo final de dado, não só pivô
