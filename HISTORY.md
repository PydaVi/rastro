# HISTORY.md — Rastro
Historico experimental e arquitetural do projeto. Este documento e referencia; nao e o plano operacional do dia.

## Uso
- `PLAN.md`: direcao atual, proximo bloco, decisoes abertas.
- `REGUA.md`: criterio permanente de generalizacao ofensiva vs operacionalizacao.
- `HISTORY.md`: historico experimental completo e descobertas arquiteturais consolidadas.

## Leitura consolidada
O historico ate aqui prova quatro coisas principais:
- o engine central ficou robusto em backtracking, path scoring e action shaping;
- o Produto 01 deixou de ser apenas fixture/dry-run e ganhou execucao real em AWS;
- o pipeline discovery-driven e o `blind real` inicial existem;
- a leitura de generalizacao estava otimista demais, e os retestes IAM-heavy expuseram dividas estruturais do nucleo.

## Descobertas arquiteturais consolidadas
- o problema raiz inicial de escolha de pivô era representacao de estado, nao apenas planner;
- prompt-only nao basta; policy layer antes do LLM e necessaria;
- order sensitivity e propriedade do engine, nao do modelo;
- lookahead-aware scoring resolveu parte importante da fragilidade de ranking nos benchmarks estruturados;
- o simulador precisou diferenciar transicoes por parameters para suportar branch profundo;
- discovery-driven em AWS real passou a funcionar no `aws-foundation`;
- external entry ganhou prova real de reachability em EC2 publico, ALB, API Gateway e NLB;
- o primeiro `blind real` foundation convergiu, mas isso nao provou generalizacao forte;
- o reteste IAM-heavy mostrou que discovery e selection ja nao sao o gargalo principal; o problema migrou para runtime, evidence e distinctness;
- findings volumosos por principal podem inflar resultado sem aumentar diversidade estrutural de attack paths;
- `target_observed` como centro do contrato de sucesso e divida arquitetural critica;
- parte do progresso recente deve ser reclassificada como melhoria de runtime/harness e honestidade epistemologica, nao como generalizacao forte;

## Tabela experimental completa
| ID | Titulo | Status | Documento |
|---|---|---|---|
| EXP | 003-path3-role-choice | hipótese principal refutada nas etapas 2–4 / confirmada na etapa 5 | `docs/experiments/EXP-003-path3-role-choice.md` |
| EXP | 005-backtracking-first-cut | primeiro corte implementado; validado offline, em Path 4 dry-run com OpenAIPlanner, e em Path 4 AWS real como convergência end-to-end | `docs/experiments/EXP-005-backtracking-first-cut.md` |
| EXP | 006-multi-branch-backtracking | hipotese principal confirmada apos endurecimento iterativo do Path 5 | `docs/experiments/EXP-006-multi-branch-backtracking.md` |
| EXP | 007-order-and-label-permutation | hipotese de convergencia confirmada com orcamento suficiente; fragilidade de order sensitivity confirmada | `docs/experiments/EXP-007-order-and-label-permutation.md` |
| EXP | 008-path-scoring-order-invariance | primeiro corte implementado; melhora parcial confirmada | `docs/experiments/EXP-008-path-scoring-order-invariance.md` |
| EXP | 009-evidence-aware-path-scoring | melhora parcial confirmada; gargalo restante isolado | `docs/experiments/EXP-009-evidence-aware-path-scoring.md` |
| EXP | 010-lookahead-path-scoring | hipotese principal confirmada | `docs/experiments/EXP-010-lookahead-path-scoring.md` |
| EXP | 011-deeper-branch-lookahead | confirmado apos correcao do simulador | `docs/experiments/EXP-011-deeper-branch-lookahead.md` |
| EXP | 012-secrets-manager-branching | confirmado em `dry_run` e em AWS real | `docs/experiments/EXP-012-secrets-manager-branching.md` |
| EXP | 013-secrets-manager-deeper-branching | confirmado em `dry_run` | `docs/experiments/EXP-013-secrets-manager-deeper-branching.md` |
| EXP | 014-secrets-manager-backtracking | hipótese principal confirmada | `docs/experiments/EXP-014-secrets-manager-backtracking.md` |
| EXP | 015-secrets-manager-backtracking-real | hipótese principal confirmada após correção do executor real | `docs/experiments/EXP-015-secrets-manager-backtracking-real.md` |
| EXP | 016-secrets-manager-competitive-backtracking | hipótese principal confirmada | `docs/experiments/EXP-016-secrets-manager-competitive-backtracking.md` |
| EXP | 017-ssm-backtracking-competitive | hipótese principal confirmada | `docs/experiments/EXP-017-ssm-backtracking-competitive.md` |
| EXP | 018-path-scoring-noisy-permutations | em andamento | `docs/experiments/EXP-018-path-scoring-noisy-permutations.md` |
| EXP | 019-path-scoring-ambiguous-decoys | em andamento | `docs/experiments/EXP-019-path-scoring-ambiguous-decoys.md` |
| EXP | 020-path-scoring-deep-noisy | concluido | `docs/experiments/EXP-020-path-scoring-deep-noisy.md` |
| EXP | 021-path-scoring-weak-lookahead | concluida | `docs/experiments/EXP-021-path-scoring-weak-lookahead.md` |
| EXP | 022-path-scoring-tight-steps | concluida | `docs/experiments/EXP-022-path-scoring-tight-steps.md` |
| EXP | 023-path-scoring-aws-real | concluida | `docs/experiments/EXP-023-path-scoring-aws-real.md` |
| EXP | 024-backtracking-loop-trap | concluida | `docs/experiments/EXP-024-backtracking-loop-trap.md` |
| EXP | 025-backtracking-ambiguous-analyze | concluida | `docs/experiments/EXP-025-backtracking-ambiguous-analyze.md` |
| EXP | 026-backtracking-three-pivots-deep | concluida | `docs/experiments/EXP-026-backtracking-three-pivots-deep.md` |
| EXP | 027-backtracking-aws-real | concluida | `docs/experiments/EXP-027-backtracking-aws-real.md` |
| EXP | 028-iam-s3-portfolio | concluida | `docs/experiments/EXP-028-iam-s3-portfolio.md` |
| EXP | 029-iam-secrets-portfolio | concluida | `docs/experiments/EXP-029-iam-secrets-portfolio.md` |
| EXP | 030-iam-ssm-portfolio | concluida | `docs/experiments/EXP-030-iam-ssm-portfolio.md` |
| EXP | 031-iam-role-chaining-portfolio | concluida | `docs/experiments/EXP-031-iam-role-chaining-portfolio.md` |
| EXP | 032-internal-data-platform-discovery-driven | confirmada | `docs/experiments/EXP-032-internal-data-platform-discovery-driven.md` |
| EXP | 033-serverless-foundation-generalization | confirmada | `docs/experiments/EXP-033-serverless-foundation-generalization.md` |
| EXP | 034-serverless-foundation-hardening | confirmada | `docs/experiments/EXP-034-serverless-foundation-hardening.md` |
| EXP | 035-serverless-advanced-opening | confirmada | `docs/experiments/EXP-035-serverless-advanced-opening.md` |
| EXP | 036-compute-foundation-generalization | confirmada | `docs/experiments/EXP-036-compute-foundation-generalization.md` |
| EXP | 037-compute-pivot-opening | confirmada | `docs/experiments/EXP-037-compute-pivot-opening.md` |
| EXP | 038-external-entry-opening | confirmada | `docs/experiments/EXP-038-external-entry-opening.md` |
| EXP | 039-cross-account-opening | confirmada | `docs/experiments/EXP-039-cross-account-opening.md` |
| EXP | 040-multi-step-chain-opening | confirmada | `docs/experiments/EXP-040-multi-step-chain-opening.md` |
| EXP | 041-compute-pivot-aws-real | concluida | `docs/experiments/EXP-041-compute-pivot-aws-real.md` |
| EXP | 042-external-entry-aws-real | concluida | `docs/experiments/EXP-042-external-entry-aws-real.md` |
| EXP | 043-multi-step-aws-real | concluida | `docs/experiments/EXP-043-multi-step-aws-real.md` |
| EXP | 044-mixed-generalization-selection | concluida | `docs/experiments/EXP-044-mixed-generalization-selection.md` |
| EXP | 045-mixed-generalization-end-to-end | concluida | `docs/experiments/EXP-045-mixed-generalization-end-to-end.md` |
| EXP | 046-mixed-generalization-inferred-profiles | concluida | `docs/experiments/EXP-046-mixed-generalization-inferred-profiles.md` |
| EXP | 047-mixed-generalization-same-surface-competition | concluida | `docs/experiments/EXP-047-mixed-generalization-same-surface-competition.md` |
| EXP | 048-mixed-generalization-competing-entry-surfaces | concluida | `docs/experiments/EXP-048-mixed-generalization-competing-entry-surfaces.md` |
| EXP | 049-mixed-resolver-structural-routing | concluida | `docs/experiments/EXP-049-mixed-resolver-structural-routing.md` |
| EXP | 050-mixed-generalization-deeper-chain-and-shared-entry | concluida | `docs/experiments/EXP-050-mixed-generalization-deeper-chain-and-shared-entry.md` |
| EXP | 051-mixed-generalization-relationship-derived-structure | concluida | `docs/experiments/EXP-051-mixed-generalization-relationship-derived-structure.md` |
| EXP | 052-mixed-generalization-without-semantic-tags | concluida | `docs/experiments/EXP-052-mixed-generalization-without-semantic-tags.md` |
| EXP | 053-mixed-generalization-obfuscated-target-harness-mismatch | concluida | `docs/experiments/EXP-053-mixed-generalization-obfuscated-target-harness-mismatch.md` |
| EXP | 054-mixed-generalization-obfuscated-enterprise-targets | concluida | `docs/experiments/EXP-054-mixed-generalization-obfuscated-enterprise-targets.md` |
| EXP | 055-mixed-generalization-low-lexical-enterprise-failure | concluida | `docs/experiments/EXP-055-mixed-generalization-low-lexical-enterprise-failure.md` |
| EXP | 056-mixed-generalization-obfuscated-local-targets | concluida | `docs/experiments/EXP-056-mixed-generalization-obfuscated-local-targets.md` |
| EXP | 057-mixed-generalization-local-secret-obfuscation-failure | confirmada | `docs/experiments/EXP-057-mixed-generalization-local-secret-obfuscation-failure.md` |
| EXP | 058-mixed-generalization-lower-lexical-local-secret | confirmada | `docs/experiments/EXP-058-mixed-generalization-lower-lexical-local-secret.md` |
| EXP | 059-mixed-generalization-low-lexical-enterprise-aliases | confirmada | `docs/experiments/EXP-059-mixed-generalization-low-lexical-enterprise-aliases.md` |
| EXP | 060-mixed-generalization-generic-fixture-aliases | confirmada | `docs/experiments/EXP-060-mixed-generalization-generic-fixture-aliases.md` |
| EXP | 061-mixed-generalization-reduced-curated-metadata | confirmada | `docs/experiments/EXP-061-mixed-generalization-reduced-curated-metadata.md` |
| EXP | 062-external-entry-maturity-modeling | confirmada | `docs/experiments/EXP-062-external-entry-maturity-modeling.md` |
| EXP | 063-target-based-generated-objectives-reveal-synthetic-coupling | confirmada | `docs/experiments/EXP-063-target-based-generated-objectives-reveal-synthetic-coupling.md` |
| EXP | 064-profile-independent-objective-generation | confirmada | `docs/experiments/EXP-064-profile-independent-objective-generation.md` |
| EXP | 065-structural-fixture-set-routing | confirmada | `docs/experiments/EXP-065-structural-fixture-set-routing.md` |
| EXP | 066-embedded-fixture-paths-reduce-mixed-resolver-dependence | confirmada | `docs/experiments/EXP-066-embedded-fixture-paths-reduce-mixed-resolver-dependence.md` |
| EXP | 067-candidate-embedded-scope-and-fixture-contract | confirmada | `docs/experiments/EXP-067-candidate-embedded-scope-and-fixture-contract.md` |
| EXP | 068-mixed-benchmark-without-profile-resolver | confirmada | `docs/experiments/EXP-068-mixed-benchmark-without-profile-resolver.md` |
| EXP | 069-serverless-unified-fixture-set | confirmada | `docs/experiments/EXP-069-serverless-unified-fixture-set.md` |
| EXP | 070-compute-unified-fixture-set | confirmada | `docs/experiments/EXP-070-compute-unified-fixture-set.md` |
| EXP | 071-external-entry-network-discovery-foundation | confirmada | `docs/experiments/EXP-071-external-entry-network-discovery-foundation.md` |
| EXP | 072-external-entry-reachability-benchmark-objective-coupling | confirmada | `docs/experiments/EXP-072-external-entry-reachability-benchmark-objective-coupling.md` |
| EXP | 073-external-entry-reachability-benchmark-states | confirmada | `docs/experiments/EXP-073-external-entry-reachability-benchmark-states.md` |
| EXP | 074-external-entry-reachability-selection-synthesis | confirmada | `docs/experiments/EXP-074-external-entry-reachability-selection-synthesis.md` |
| EXP | 075-external-entry-surface-to-backend-structural-signals | confirmada | `docs/experiments/EXP-075-external-entry-surface-to-backend-structural-signals.md` |
| EXP | 076-external-entry-discovery-public-surface-inventory | confirmada | `docs/experiments/EXP-076-external-entry-discovery-public-surface-inventory.md` |
| EXP | 077-external-entry-discovery-surface-backend-relationships | confirmada | `docs/experiments/EXP-077-external-entry-discovery-surface-backend-relationships.md` |
| EXP | 078-external-entry-selection-from-discovered-network-graph | confirmada | `docs/experiments/EXP-078-external-entry-selection-from-discovered-network-graph.md` |
| EXP | 079-external-entry-alb-aws-real | concluida | `docs/experiments/EXP-079-external-entry-alb-aws-real.md` |
| EXP | 080-external-entry-apigateway-aws-real | concluida | `docs/experiments/EXP-080-external-entry-apigateway-aws-real.md` |
| EXP | 081-external-entry-nlb-aws-real | concluida | `docs/experiments/EXP-081-external-entry-nlb-aws-real.md` |
| EXP | 082-external-entry-alb-listener-rules-aws-real | concluida | `docs/experiments/EXP-082-external-entry-alb-listener-rules-aws-real.md` |
| EXP | 083-blind-real-assessment-fixture-coupling | parcial | `docs/experiments/EXP-083-blind-real-assessment-fixture-coupling.md` |
| EXP | 084-blind-real-runtime-action-space-pollution | concluida | `docs/experiments/EXP-084-blind-real-runtime-action-space-pollution.md` |
| EXP | 085-iam-heavy-blind-real-subcoverage-diagnosis | concluida | `docs/experiments/EXP-085-iam-heavy-blind-real-subcoverage-diagnosis.md` |
| EXP | 086-iam-heavy-blind-real-fixture-routing-contamination | concluida | `docs/experiments/EXP-086-iam-heavy-blind-real-fixture-routing-contamination.md` |
| EXP | 087-iam-heavy-blind-real-restructure-plan | - | `docs/experiments/EXP-087-iam-heavy-blind-real-restructure-plan.md` |
| EXP | 088-generalization-confidence-correction-after-iam-heavy | concluida | `docs/experiments/EXP-088-generalization-confidence-correction-after-iam-heavy.md` |
