# EXP-087 - IAM-Heavy Blind Real Reestruturação do Núcleo

- **ID**: EXP-087
- **Fase**: Validacao real de generalizacao ofensiva
- **Data**: 2026-04-04
- **Status**: planejamento

## Objetivo

Transformar `Blind Real Assessment` em um fluxo puramente adversarial:
- discovery real e selection real já convergem
- agora o foco e o core execution runtime, o portfolio IAM privesc e a evidencia
  mínima por classe
- meta imediata: reconstruir o contrato do bloco para medir coverage real
  antes de qualquer novo reteste IAM-heavy

## Premissas do plano

- discovery e target selection já entregam inventario real
- o pipeline ainda propaga `fixture_path`/`scope_template_path`/`execution_fixture_set`
  para campaigns IAM-heavy
- o runtime real continua limitado a `iam_list_roles`, `iam_passrole` e
  `access_resource`
- findings ainda carecem de estados de evidencia claros e deduplcam

## Passos da reestruturação (em ordem de prioridade)

1. **Bloco “Runtime Cleanroom”**
   - impedir que `run_generated_campaign()` use `fixture_path` quando:
     - discovery_snapshot veio de AWS real
     - plan foi derivado de discovery (não legacy bundle)
   - obrigar `BlindRealRuntime` a ser o único executor no modo `real` para
     estas plans, e falhar caso runtime não tenha cobertura mínima
   - atualizar testes para cumprir o contrato

2. **Bloco “Evidence States”**
   - estender `AssessmentFinding` (models/reporting) com estados:
     `observed`, `reachable`, `credentialed`, `exploited`, `validated_impact`
   - definir heurísticas mínimas por classe (ex.,
     `aws-iam-role-chaining`: assume_role com `granted_role` + `target_accessed`)
   - ajustar `build_assessment_findings()` para mapear estados e dedupe
   - exposição no `assessment_findings.md/json` e `report.md`

3. **Bloco “IAM Portfolio Core”**
   - adicionar toolchain/policies para abuse IAM (CreatePolicyVersion,
     AttachRolePolicy, ElevateAssumeRolePolicy, PassRole -> service create)
   - ampliar `BlindRealRuntime.enumerate_actions` / `_assume_role_actions` para
     incluir essas ações condicionadas a `policy_escalation_signals`
   - assegurar que o runtime pode criar as credenciais intermediárias necessárias

4. **Bloco “Ranking offensive structure”**
   - tornar `target_selection` dependente de `policy_escalation_signals`,
     `trust_edges`, `can_assume` em vez de keywords `handler`/`broker`
   - garantir que scores reflitam exploitability (policy actions, pass role, admin)

5. **Bloco “Measurement e testes manuais”**
   - definir métricas: coverage por classe, findings únicos/duplicados, prova média
   - gerar checklist de reteste manual para `iam-vulnerable` (execution_mode,
     runtime_fixture, findings states)
   - documentar em `docs/experiments/EXP-087` e `PLAN.md`

## Critérios de sucesso (antes de novo reteste)

- campaigns IAM-heavy discovery-driven em AWS real rodando com runtime blind real
- `fixtures` sintéticos não aparecem em `execution_mode=real` runs
- `assessment_findings` indica estados de prova progressivos
- portfolio IAM-privesc separado do `aws-foundation`
- `BlindRealRuntime` expõe ações intermediárias relevantes
- métricas de coverage/dedup estão registradas para acompanhamento manual

## Próximos passos operacionais

1. Implementar o bloqueio de `fixture_path` no executor real e validar com
   `tests/test_mvp.py::test_run_generated_campaign_builds_blind_real_runtime_without_fixture_path`.
2. Implementar a enumeração de ações IAM abusivas no runtime e escrever testes
   dedicados (mock IAM-heavy snapshot).
3. Expandir `build_assessment_findings()` com estados/evidência e garantir que
   `assessment_findings.md` documenta o novo status.
4. Atualizar `PLAN.md` ao concluir cada bloco (direção: mais generalização ofensiva).
5. Executar reteste IAM-heavy manual com checklist (coverage, duplicates, harness contamination).

## Verificação manual sugerida

- Antes de rodar `assessment run`, confirme:
  - o plan gerado não carrega `fixture_path`
  - `BlindRealRuntime` foi construído e loga `runtime_fixture`
  - `authorization` contém `permitted_profiles` para os novos IAM classes
- Durante o reteste:
  - registre `execution_mode` das campaigns (deve ser `real`)
  - verifique que as steps contêm as novas ações IAM intermediárias
  - checar `assessment_findings` para estados e dedupe
- Após o reteste:
  - comparar findings únicos e coverage por classe
  - confirmar que `report.json`/`assessment_findings.json` mostram `credentialed`/`exploited`

Essa documentação dá uma base viável para você seguir os testes manuais nos próximos dias.
