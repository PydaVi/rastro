# PLAN.md — Rastro

Rastro é um engine de simulação adversarial autônoma focado em provar
caminhos reais de comprometimento em ambientes cloud.

Não lista vulnerabilidades — raciocina sobre elas, as encadeia,
e valida o caminho completo com evidência auditável.

Este documento define o roadmap vivo do projeto.

---

## Direção estratégica do produto

Rastro é um **engine central de raciocínio sobre attack paths**, sobre o qual
existem dois produtos:

### Produto 01 — Validação de Exposição (prioridade atual)

Execução controlada em ambiente AWS real autorizado.

Entrega:
- attack paths reais, não teóricos
- evidência auditável (ARNs, timestamps, respostas de API)
- grafo de ataque interativo
- mapping MITRE
- remediação por path

### Produto 02 — Attack Path em CI/CD (futuro próximo)

Simulação de attack paths sobre o estado resultante de IaC (Terraform).

Entrega:
- análise no PR antes do deploy
- bloqueio de merge se houver attack path crítico
- evidência contextualizada na mudança que causou o risco

---

## Ordem estratégica do projeto

1. AWS primeiro
2. profundidade antes de expansão
3. Produto 01 antes do Produto 02
4. Kubernetes entra somente após maturidade AWS

---

## Régua permanente de direção do produto

Cada bloco do roadmap deve ser avaliado por duas perguntas:

1. Quanto esse bloco aproxima o Rastro de um `autonomous attacker-thinker` generalista?
2. Quanto esse bloco ainda o mantém como validador adversarial de campaigns AWS pré-estruturadas?

Ao fechar cada bloco, o `PLAN.md` deve registrar explicitamente uma direção predominante:

- `Direção do avanço: mais generalização ofensiva`
- `Direção do avanço: mais operacionalização de campaigns conhecidas`

### Critérios de generalização ofensiva

Um bloco tende a `mais generalização ofensiva` quando reduz dependência de:
- profiles fixos
- heurísticas lexicais simples
- alvos pré-modelados
- paths muito roteirizados

e aumenta:
- discovery real
- target selection semântico
- pivôs via compute
- external entry
- cross-account
- chains multi-step com menor pré-estruturação

### Critérios de operacionalização

Um bloco tende a `mais operacionalização de campaigns conhecidas` quando aumenta:
- runner
- CLI
- preflight
- reporting
- campaign orchestration
- assessment consolidation
- bundles e profiles ainda fortemente baseados em classes conhecidas

Essa régua existe para evitar drift de produto. O objetivo não é abandonar
operacionalização, mas impedir que ela substitua o avanço em generalização ofensiva.

---

## Estado atual

### Fase 0 — completa
Loop central validado com fixture sintético.

### Fase 1 — completa
- OllamaPlanner funcional e validado
- OpenAIPlanner e ClaudePlanner implementados
- Tool Registry YAML com MITRE mapping
- Dry-run completo

### Fase 2 — completa (primeiro corte AWS real)
- Executor AWS real com boto3
- Paths 1 e 2 validados em conta autorizada
- Scope enforcement obrigatório com autorização explícita
- Artefatos sanitizados automáticos

### Fase 3 — em progresso
Multi-branch backtracking validado, path scoring em evolução,
diversificação de attack paths em andamento.

23 experimentos concluídos — ver seção de histórico experimental abaixo.

---

## Histórico experimental — Fase 3

Cada experimento tem documento em `docs/experiments/`.
Resultados negativos têm a mesma obrigatoriedade de documentação
que resultados positivos.

| ID      | Hipótese central                                  | Resultado         |
|---------|---------------------------------------------------|-------------------|
| EXP-001 | Loop real em AWS preserva controles               | confirmada        |
| EXP-002 | Descoberta dinâmica via s3:ListBucket             | confirmada        |
| EXP-003 | Escolha de pivô entre roles concorrentes          | 5 etapas / parcial|
| EXP-004 | OllamaPlanner após action shaping                 | confirmada        |
| EXP-005 | Backtracking estruturado primeiro corte           | confirmada        |
| EXP-006 | Backtracking com 3 pivôs concorrentes             | confirmada        |
| EXP-007 | Permutação de ordem e rótulos                     | confirmada        |
| EXP-008 | Path scoring — primeiro corte                     | parcial           |
| EXP-009 | Path scoring com evidência observada              | parcial           |
| EXP-010 | Path scoring com lookahead signals                | confirmada        |
| EXP-011 | Branch profundo com lookahead                     | confirmada        |
| EXP-012 | Secrets Manager como superfície nova              | confirmada        |
| EXP-013 | Branch profundo em Secrets Manager                | confirmada        |
| EXP-014 | Backtracking em Secrets Manager (dry-run)         | confirmada        |
| EXP-015 | Backtracking em Secrets Manager (AWS real)        | confirmada        |
| EXP-016 | Backtracking com pivô competitivo adicional       | confirmada        |
| EXP-017 | Backtracking em SSM Parameter Store (AWS real)    | confirmada        |
| EXP-018 | Path scoring com evidencia ruidosa               | confirmada        |
| EXP-019 | Path scoring com evidencia ambigua               | confirmada        |
| EXP-020 | Path scoring com branch profundo e ruido         | confirmada        |
| EXP-021 | Path scoring adversarial sem lookahead forte     | confirmada        |
| EXP-022 | Path scoring com limite de steps apertado        | confirmada        |
| EXP-023 | Path scoring em AWS real (sinal novo)            | confirmada        |
| EXP-024 | Loop trap sintetico para backtracking            | confirmada        |
| EXP-025 | Backtracking com sinais ambiguos e analyze no-op | confirmada        |
| EXP-026 | Backtracking com 3 pivots e branch profundo      | confirmada        |
| EXP-027 | Backtracking em AWS real (validacao)             | confirmada        |

Descobertas arquiteturais principais acumuladas:
- problema raiz de escolha de pivô era representação de estado, não modelo
- prompt-only não basta — policy layer antes do LLM é necessária
- cenário semânticamente fácil mascara ausência de backtracking real
- order sensitivity é propriedade do engine, não do modelo
- lookahead-aware scoring resolve order sensitivity no benchmark atual
- simulador precisa diferenciar transições por parameters para suportar
  branch profundo
- ANALYZE no executor real deve ser no-op para não bloquear branch correto
- ANALYZE precisa contar como progresso do branch para evitar abandono do caminho correto
- backtracking permanece robusto com dois pivôs competitivos antes do caminho correto
- backtracking generaliza para SSM quando o toolchain minimo existe

---

# Eixo 1 — AWS (prioridade máxima)

---

## Curto prazo — AWS

### Objetivo
Fechar maturidade do engine como sistema de validação real.

### Prioridades

**1. Path scoring robusto**
- reduzir order sensitivity residual
- ranking consistente de pivôs
- estabilidade sob permutação
Status: concluído (EXP-018 a EXP-023)
Direção do avanço: mais generalização ofensiva

**2. Backtracking completo**
- branch memory sólida
- recuperação consistente
- evitar loops e revisitas inúteis
Status: concluído (EXP-024 a EXP-027)
Status: em planejamento (próximo bloco)
Direção do avanço: mais generalização ofensiva

**3. Diversificação de attack paths**
- IAM / STS / S3 / Secrets Manager / SSM
- sempre chains completas, nunca features isoladas
- regra: 2-3 experimentos sintéticos → 1 validação real representativa
Status: foundation concluído; advanced/enterprise pendentes
Direção atual do avanço: mista, com predominância de generalização ofensiva

**4. Contrato de integração AWS**
- role assumível com trust policy restrita ao ARN do executor
- preflight obrigatório de validação de permissões
- escopo explícito em scope.yaml com autorização documentada
- cleanup: nenhum recurso criado permanece após o run
- após fechar este item, iniciar implementação das camadas operacionais
  (Target/Authorization/Profile/Campaign/Assessment) conforme
  `docs/architecture.md`.
Status: em progresso
Direção atual do avanço: mais operacionalização de campaigns conhecidas

**Trilha paralela — MVP operacional do foundation**
- `profile list` para catálogo operacional
- `target validate` para validar configuração do assessment
- `preflight validate` para validar acesso antes do run
- `campaign run` para executar um profile do foundation
- `assessment run` para orquestrar bundle `aws-foundation`
- consolidar outputs por campanha e assessment
- status operacional explícito por campanha
- resumo executivo estável em `assessment.json` e `assessment.md`
Status: em progresso
Direção atual do avanço: mais operacionalização de campaigns conhecidas

Critério de entrada para runner containerizado:
- nao iniciar containerizacao agora
- iniciar somente apos:
  - `internal-data-platform` validado discovery-driven em A/B/C
  - `serverless-business-app` validado ao menos em A/B/C discovery-driven
  - primeiro corte de `compute-pivot-app` validado
  - contrato da CLI operacional estabilizado sem refactor estrutural grande
- objetivo da containerizacao:
  - empacotar runner operacional reprodutivel
  - facilitar execucao controlada do Produto 01
  - nao antecipar empacotamento antes da maturidade da camada discovery-driven

Marco atual:
- catálogo operacional implementado
- target validation implementado
- preflight validation implementado
- campaign run implementado
- assessment run implementado
- consolidação resiliente implementada
- pendente: validação ponta a ponta do bundle `aws-foundation`
Atualização:
- `assessment run --bundle aws-foundation` validado ponta a ponta em AWS real
- artefatos consolidados gerados em `outputs_assessment_aws_foundation_openai/`
- resultado observado: `assessment_ok=true`, 4/4 campanhas `passed`

**Próximo bloco do Produto 01 — Discovery + Target Selection**
- discovery controlado por target/profile
- classificação de recursos descobertos
- ranking auditável de alvos por classe
- síntese automática de campanhas a partir de candidatos
- integração dessa camada ao `assessment run`
Documento de desenho: `docs/product01-discovery-target-selection.md`
Status: planejado
Base de escala sintética: `docs/synthetic-aws-environments.md`

Backlog do bloco:
- Bloco 1: discovery foundation (S3, Secrets, SSM, IAM roles)
- Bloco 2: target selection foundation
- Bloco 3: campaign synthesis foundation
- Bloco 4: assessment discovery-driven
Status do bloco 1:
- `discovery run --bundle aws-foundation` implementado
- artefatos `discovery.json` e `discovery.md` implementados
- validacao ponta a ponta em AWS real concluida
- ajuste estrutural aplicado apos validacao:
  - filtro de service-linked roles
  - correcao de ARN para parametros SSM
- pendente: refinamento de limites/heuristicas
Direção do avanço: mais generalização ofensiva
Status do bloco 2:
- `target-selection run` implementado
- artefatos `target_candidates.json` e `target_candidates.md` implementados
- validado sobre o discovery real do `aws-foundation`
- resultado observado: 15 candidatos, 5 `high confidence`
- pendente: refinamento de heuristicas e reducao de ruido lexical
Direção do avanço: mais generalização ofensiva
Status do bloco 3:
- `campaign-synthesis run` implementado
- artefatos `campaign_plan.json` e `campaign_plan.md` implementados
- objetivos e scopes gerados automaticamente por candidato
- validado sobre candidatos reais do `aws-foundation`
- resultado observado: 4 planos gerados, um por profile
- ajuste aplicado: role chaining agora prioriza `DataAccessRole` sobre roles de auditoria
- pendente: integrar `CampaignPlan[]` ao `assessment run`
Direção do avanço: mais operacionalização de campaigns conhecidas
Status do bloco 4:
- `assessment run --bundle aws-foundation --discovery-driven` implementado
- pipeline completo validado em AWS real
- artefatos encadeados preservados no assessment
- resultado observado: `assessment_ok=true`, 4/4 campanhas `passed`
- proximo gap real: refinar reachability/pruning e heuristicas de target selection
Direção do avanço: mais operacionalização de campaigns conhecidas

Próxima base de escala para o Produto 01:
- `internal-data-platform` (foundation em escala)
- `serverless-business-app` (advanced serverless)
- `compute-pivot-app` (advanced compute/external entry)

Sequência recomendada:
1. Implementar `internal-data-platform` variantes A/B/C
2. Revalidar pipeline discovery-driven em ambiente sintético maior
3. Só então avançar para `serverless-business-app`
Status atual:
- Variante A implementada em `fixtures/internal_data_platform_variant_a.discovery.json`
- validada no target selection foundation
- Variante B implementada em `fixtures/internal_data_platform_variant_b.discovery.json`
- Variante C implementada em `fixtures/internal_data_platform_variant_c.discovery.json`
- autorun de `target-selection run` executado nas tres variantes
- resultados observados:
  - A: 17 candidatos
  - B: 20 candidatos
  - C: 20 candidatos
- validacao end-to-end discovery-driven concluida nas tres variantes
- resultado observado:
  - A: `campaigns_passed=4/4`
  - B: `campaigns_passed=4/4`
  - C: `campaigns_passed=4/4`
- descoberta arquitetural registrada em `docs/experiments/EXP-032-internal-data-platform-discovery-driven.md`
Direção do avanço: mais generalização ofensiva
- `serverless-business-app` Variante A iniciada
- snapshot inicial criado em `fixtures/serverless_business_app_variant_a.discovery.json`
- documentacao inicial em `docs/environments/serverless-business-app-variant-a.md`
- teste inicial de coerencia do inventario serverless adicionado
- foundation revalidado discovery-driven na Variante A
- resultado observado:
  - `campaigns_passed=4/4`
  - `assessment_ok=true`
- descoberta arquitetural registrada em `docs/experiments/EXP-033-serverless-foundation-generalization.md`
- Variante B implementada em `fixtures/serverless_business_app_variant_b.discovery.json`
- documentacao inicial em `docs/environments/serverless-business-app-variant-b.md`
- KMS introduzido no arquétipo sem quebrar a seleção foundation
- Variante C implementada em `fixtures/serverless_business_app_variant_c.discovery.json`
- documentacao inicial em `docs/environments/serverless-business-app-variant-c.md`
- foundation revalidado discovery-driven nas Variantes B e C
- resultado observado:
  - B: `campaigns_passed=4/4`
  - C: `campaigns_passed=4/4`
- descoberta arquitetural registrada em `docs/experiments/EXP-034-serverless-foundation-hardening.md`
- classes `advanced` abertas no arquétipo:
  - `aws-iam-lambda-data`
  - `aws-iam-kms-data`
- resultados observados em `aws-advanced` discovery-driven:
  - Variante A: `campaigns_passed=5/5`
  - Variante B: `campaigns_passed=6/6`
  - Variante C: `campaigns_passed=6/6`
- descoberta arquitetural registrada em `docs/experiments/EXP-035-serverless-advanced-opening.md`
Direção do avanço: mais generalização ofensiva
- `compute-pivot-app` Variante A iniciada
- snapshot inicial criado em `fixtures/compute_pivot_app_variant_a.discovery.json`
- documentacao inicial em `docs/environments/compute-pivot-app-variant-a.md`
- teste inicial de coerencia do inventario compute adicionado
- foundation target selection validado no arquétipo:
  - S3: `compute-payroll-dumps-prod/payroll/2026-03/payroll.csv`
  - Secrets: `prod/payroll/backend-db-password`
  - SSM: `/prod/payroll/api_key`
- foundation revalidado discovery-driven na Variante A
- resultado observado:
  - `campaigns_passed=4/4`
  - `assessment_ok=true`
- descoberta arquitetural registrada em `docs/experiments/EXP-036-compute-foundation-generalization.md`
- classe `aws-iam-compute-iam` aberta na Variante A
- resultado observado em `aws-advanced` discovery-driven:
  - `campaigns_passed=5/5`
  - `assessment_ok=true`
- descoberta arquitetural registrada em `docs/experiments/EXP-037-compute-pivot-opening.md`
- Variante B implementada em `fixtures/compute_pivot_app_variant_b.discovery.json`
- classe `aws-external-entry-data` aberta na Variante B
- resultado observado em `aws-advanced` discovery-driven:
  - `campaigns_passed=6/6`
  - `assessment_ok=true`
- descoberta arquitetural registrada em `docs/experiments/EXP-038-external-entry-opening.md`
- Variante C implementada em `fixtures/compute_pivot_app_variant_c.discovery.json`
- classes `enterprise` abertas na Variante C:
  - `aws-cross-account-data`
  - `aws-multi-step-data`
- resultado observado em `aws-enterprise` discovery-driven:
  - `campaigns_passed=7/7`
  - `assessment_ok=true`
- descobertas arquiteturais registradas em:
  - `docs/experiments/EXP-039-cross-account-opening.md`
  - `docs/experiments/EXP-040-multi-step-chain-opening.md`
- bloco do "segundo nível" sintético fechado no `compute-pivot-app`:
  - `IAM -> Compute -> IAM`
  - `external entry -> IAM -> data`
  - `cross-account -> data`
  - `multi-step chain`
- outputs end-to-end consolidados com findings:
  - `outputs_compute_pivot_app_variant_a_assessment/`
  - `outputs_compute_pivot_app_advanced_variant_a_assessment/`
  - `outputs_compute_pivot_app_advanced_variant_b_assessment/`
  - `outputs_compute_pivot_app_enterprise_variant_c_assessment/`
- leitura do bloco:
  - o Rastro deixou de estar restrito a campaigns AWS puramente IAM-first
  - ainda falta promoção seletiva para AWS real nas classes de maior valor
Direção atual do avanço: mais generalização ofensiva

Próxima promoção seletiva para AWS real (ordem definida):
1. `aws-iam-compute-iam`
   - concluída em AWS real via `EXP-041`
   - lab efêmero em `terraform_local_lab/compute_pivot_real/`
   - resultado observado:
     - `objective_met=true`
     - `2` steps
     - evidência real:
       - `iam:GetInstanceProfile`
       - `ec2:DescribeIamInstanceProfileAssociations`
   - descoberta arquitetural registrada em `docs/experiments/EXP-041-compute-pivot-aws-real.md`
2. `aws-external-entry-data`
   - concluída em AWS real via `EXP-042`
   - revalidada sob semântica endurecida de credenciais
   - a continuidade da chain usa `assume_role_surrogate` controlado e auditável
   - descoberta arquitetural registrada em:
     - `docs/experiments/EXP-042-external-entry-aws-real.md`
     - `docs/experiments/EXP-043-multi-step-aws-real.md`
3. `aws-cross-account-data`
   - alto valor arquitetural, mas depende de duas contas e trust controlado
   - bloqueado temporariamente por pre-requisito operacional:
     - segunda conta AWS controlada
     - trust policy explicita entre conta origem e conta destino
   - contrato e lab efemero definidos em:
     - `docs/cross-account-real-validation.md`
   - adiado ate existir ambiente multi-account real
   - manter validacao sintetica como referencia ate a promocao real
4. `aws-multi-step-data`
   - concluída em AWS real via `EXP-043`
   - validada com `assume_role_surrogate` controlado no primeiro pivô de compute
   - serve como fechamento real composto do bloco

Critérios de promoção real do segundo nível:
- promover primeiro o que maximiza generalização ofensiva com menor risco operacional
- compute pivot real já está estável
- external entry e multi-step reais agora usam semântica rigorosa de `credential acquisition`
- evitar cross-account real antes de o contrato de autorização multi-account estar explicitado

Próximo passo após o bloqueio de `cross-account`:
- preservar o bloqueio no roadmap
- nao substituir por pseudo-validacao em conta unica
- usar o contrato multi-account como criterio de entrada
- quando a segunda conta existir:
  1. criar target/authorization multi-account
  2. subir lab efemero nas duas contas
  3. executar preflight e run real
  4. destruir os dois lados

Próximo bloco de generalização ofensiva:
- mixed-environment target selection e campaign synthesis
- objetivo:
  - reduzir dependencia de profile-first rigido
  - reduzir peso de heuristica lexical crua
  - escolher o profile mais expressivo para o mesmo alvo quando houver
    competicao entre foundation, advanced e enterprise
- benchmark:
  - `fixtures/mixed_generalization_variant_a.discovery.json`
- resultado inicial:
  - `target selection` agora expõe `score_components.lexical/structural`
  - `campaign synthesis` agora suporta `dedupe_resource_targets=True`
  - `prod/payroll-api-key` e promovido para `aws-external-entry-data`
    quando ha reachability estrutural publica
  - `prod/finance/warehouse-api-key` e promovido para
    `aws-multi-step-data` quando ha chain mais expressiva
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-044-mixed-generalization-selection.md`
Direção do avanço: mais generalização ofensiva

Atualização ponta a ponta:
- mixed environment assessment discovery-driven validado em:
  - `outputs_mixed_generalization_variant_a_assessment/`
- synthesis menos `profile-first` aplicado no assessment com:
  - `dedupe_resource_targets=True`
  - `profile_resolver` sensivel ao contexto do `CampaignPlan`
- resultado observado:
  - `campaigns_total=8`
  - `campaigns_passed=8`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-045-mixed-generalization-end-to-end.md`
- leitura do bloco:
  - reduziu acoplamento entre `profile family` e fixture sintetico fixo
  - aproximou o assessment de uma escolha mais contextual de campanha
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto sem `candidate_profiles` curado implementado em:
  - `fixtures/mixed_generalization_variant_b.discovery.json`
- `target selection` agora infere profiles a partir de:
  - `resource_type`
  - `reachable_roles`
  - `pivot_chain`
  - `role_to_public_surfaces`
  - `role_to_instance_profiles`
  - `chain_depth`
- resultado observado:
  - `outputs_mixed_generalization_variant_b_assessment/`
  - `campaigns_total=8`
  - `campaigns_passed=8`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-046-mixed-generalization-inferred-profiles.md`
- leitura do bloco:
  - reduziu dependencia de `candidate_profiles` manualmente anotado
  - aumentou inferencia estrutural de classe de path
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto com competicao intra-superficie implementado em:
  - `fixtures/mixed_generalization_variant_c.discovery.json`
- competicao adicionada em:
  - secrets locais
  - parameters locais
  - objetos S3
  - secrets cross-account
- correcoes gerais aplicadas:
  - normalizacao lexical para `api-key` vs `api_key`
  - `aws-external-entry-data` deixa de capturar recursos cross-account
- resultado observado:
  - `outputs_mixed_generalization_variant_c_assessment/`
  - `campaigns_total=8`
  - `campaigns_passed=8`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-047-mixed-generalization-same-surface-competition.md`
- leitura do bloco:
  - aumentou a competicao real entre alvos da mesma superficie
  - endureceu a separacao estrutural entre external-entry e cross-account
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto com entry surfaces publicos concorrentes implementado em:
  - `fixtures/mixed_generalization_variant_d.discovery.json`
- `target selection` agora considera:
  - `public_role_quality_signal`
  - `signals.public_role_score`
- resultado observado:
  - `outputs_mixed_generalization_variant_d_assessment/`
  - `campaigns_total=8`
  - `campaigns_passed=8`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-048-mixed-generalization-competing-entry-surfaces.md`
- leitura do bloco:
  - aumentou competicao entre caminhos de entrada, nao so entre alvos finais
  - aproximou o selection de uma nocao melhor de qualidade de pivô
Direção do avanço: mais generalização ofensiva

**5. Qualidade do Produto 01**
- relatório técnico e executivo
- remediação por path
- evidência clara e auditável
- artefatos sanitizados prontos para compartilhamento

### Próxima sequência de experimentos (prioridade 3 — Portfólio MITRE Cloud/AWS)

Objetivo: expandir o portfólio de attack paths com base em MITRE
ATT&CK (Cloud/AWS), priorizando cadeias vendáveis com evidência real.

#### Etapa A — Mapa de portfólio (baseline)
- definir classes de path por tática/serviço (MITRE Cloud/AWS)
- agrupar em bundles: foundation / advanced / enterprise
- definir critérios de promoção para AWS real (2-3 sintéticos + 1 real)

#### Etapa B — Execução por classe
- para cada classe: 2-3 fixtures sintéticos com variações de pivô/decoy
- 1 validação AWS real representativa por classe crítica

#### Etapa C — Consolidação
- matriz de cobertura (classe → experimentos → real validation)
- evidência e limites conhecidos

Regra: estender a etapa apenas se houver falha que isole causa específica
ou regressão do engine.

### Mapa de portfólio — Classes base (MITRE Cloud/AWS)

**Foundation (vendável mínimo)**
1. IAM → S3 (bucket/object)
   - T1087.004, T1548, T1619, T1530
2. IAM → Secrets Manager (secret access)
   - T1548, T1552.005
3. IAM → SSM Parameter Store (parameter access)
   - T1548, T1552.004
4. IAM → Role chaining (STS assume role → resource)
   - T1548, T1078

**Advanced (expansão controlada)**
5. IAM → Compute → IAM (passrole/instance profile → new identity)
   - T1078, T1098, T1525
6. IAM → Lambda (invoke/update) → S3/Secrets
   - T1648, T1552.005
7. IAM → KMS (decrypt) → S3/Secrets
   - T1552.001
8. External entry → IAM → data access (IMDS/APIGW/S3 triggers)
   - T1078, T1525, T1552

**Enterprise (cobertura ampla)**
9. Cross-account trust → pivô → data access
   - T1484, T1078
10. Multi-step chain (3+ pivôs, mixed services)
   - combinação de técnicas acima

### External Entry — Subclasses (Advanced/Enterprise)
1. IMDSv1/IMDSv2 downgrade → instance profile → IAM → S3/Secrets
2. API Gateway/Lambda public invoke → IAM role → data access
3. S3 public write → Lambda trigger → IAM role → data access
4. STS assume role via external ID leakage

### Bundles operacionais (Produto 01)

- **aws-foundation**: classes 1–4
- **aws-advanced**: classes 1–8
- **aws-enterprise-full**: classes 1–10

### Matriz de cobertura — Prioridade 3 (planejada)

Formato: Classe → Sintéticos (2-3) → Validação AWS real (1)

| Classe | Sintéticos | AWS real | Observações |
|-------|-----------|---------|-------------|
| 1. IAM → S3 | EXP-028A/B/C | EXP-028R | decoys de bucket/objeto (confirmado) |
| 2. IAM → Secrets Manager | EXP-029A/B/C | EXP-029R | segredo decoy vs alvo (confirmado) |
| 3. IAM → SSM Parameter Store | EXP-030A/B | EXP-030R | parameter decoy vs alvo (confirmado) |
| 4. IAM → Role chaining | EXP-031A/B | EXP-031R | 2 pivôs antes do alvo (confirmado) |
| 5. IAM → Compute → IAM | EXP-032A/B | EXP-032R | instance profile → role |
| 6. IAM → Lambda → data | EXP-033A/B | EXP-033R | invoke/update → acesso |
| 7. IAM → KMS → data | EXP-034A/B | EXP-034R | decrypt → S3/Secrets |
| 8. External entry → IAM → data | EXP-035A/B/C | EXP-035R | IMDS/APIGW/S3 trigger |
| 9. Cross-account trust | EXP-036A/B | EXP-036R | trust mal configurado |
| 10. Multi-step chain (3+ pivôs) | EXP-037A/B | EXP-037R | cadeia mista |

Regra: cada classe só promove para AWS real após 2-3 sintéticos estáveis.

### Blocos de experimentos — Prioridade 3

**Bloco Foundation (classes 1–4)**
- EXP-028A/B/C: IAM → S3 (variações de decoy)
- EXP-028R: AWS real (IAM → S3)
- EXP-029A/B/C: IAM → Secrets (decoy/target)
- EXP-029R: AWS real (IAM → Secrets)
- EXP-030A/B: IAM → SSM (decoy/target)
- EXP-030R: AWS real (IAM → SSM)
- EXP-031A/B: Role chaining (2 pivôs)
- EXP-031R: AWS real (role chaining)
Status: concluído

**Bloco Advanced (classes 5–8)**
- EXP-032A/B: IAM → Compute → IAM
- EXP-032R: AWS real (compute → role)
- EXP-033A/B: IAM → Lambda → data
- EXP-033R: AWS real (Lambda path)
- EXP-034A/B: IAM → KMS → data
- EXP-034R: AWS real (KMS path)
- EXP-035A/B/C: External entry (IMDS/APIGW/S3 trigger)
- EXP-035R: AWS real (1 cenário representativo)

**Bloco Enterprise (classes 9–10)**
- EXP-036A/B: Cross-account trust
- EXP-036R: AWS real (cross-account)
- EXP-037A/B: Multi-step chain (3+ pivôs)
- EXP-037R: AWS real (cadeia mista)

---

## Médio prazo — AWS

### Objetivo
Transformar o engine em produto utilizável — Produto 01 operacional.

### Prioridades

**1. Padronização operacional**
- onboarding de conta AWS via role cross-account
- execução via credenciais temporárias
- processo repetível e documentado

**2. Runner oficial**
- containerizado
- self-hosted
- independente do ambiente do operador

**3. Ampliação de superfícies (com disciplina)**
- Lambda
- EC2
- SSM
- Parameter Store
- KMS (quando relevante)

**4. Lab AWS oficial**
- bootstrap via IaC
- cenários versionados e reproduzíveis
- regressão de comportamento entre versões

**5. Início controlado do Produto 02**
- parser de `terraform show -json`
- projeção de estado AWS a partir do plan
- sem deploy real

---

## Longo prazo — AWS

### Objetivo
Fechar a tese do Rastro em AWS antes de expandir para novos vetores.

### Prioridades

**1. Maturidade de produto**
- histórico de runs comparável
- diff de exposição entre execuções
- dashboard para cliente

**2. Maturidade de engine**
- escolha estratégica entre paths concorrentes
- priorização por impacto real

**3. Persistência de grafo**
- Neo4j ou equivalente
- dataset anonimizado para pesquisa

**4. Consolidação dos dois produtos**
- Produto 01 operacional com clientes reais
- Produto 02 funcional em CI/CD

---

# Eixo 2 — Kubernetes (próximo vetor)

Kubernetes entra somente após maturidade AWS comprovada.

---

## Curto prazo — Kubernetes (apenas modelagem, sem implementação)

### Objetivo
Definir o modelo antes de qualquer implementação.

### Prioridades
- taxonomia de attack paths Kubernetes
- domain model conceitual
- Tool Registry conceitual
- desenho de laboratório (brain-chaos)

---

## Médio prazo — Kubernetes

### Objetivo
Primeiros paths reais em ambiente controlado.

### Prioridades
- RBAC abuse
- service account pivot
- secrets discovery
- privileged pod escape
- lateral movement AWS → cluster

---

## Longo prazo — Kubernetes

### Objetivo
Segundo vetor completo do Rastro.

### Prioridades
- integração AWS ↔ Kubernetes em attack paths híbridos
- reutilização completa do engine central
- Tool Registry Kubernetes completo

---

# Princípios fundamentais

**Nenhum vendor obrigatório.**
Ollama é padrão. Backends são plugáveis. APIs externas são opção.

**Autorização explícita obrigatória.**
Sem authorized_by e authorization_document, o run não inicia.

**Engine é independente do LLM.**
Planner sugere. Engine decide, valida, executa, observa.

**Cada fase é publicável.**
Resultados geram material técnico. Projeto cresce em visibilidade
junto com a base de código.

**Testes sem dependências externas.**
pytest roda offline. AWS e LLM testados com mocks.

**Não expandir escopo antes de fechar fase.**
Cada fase entregue completa antes da próxima começar.

---

# Regra central

Rastro não cresce adicionando integrações.

Rastro cresce provando attack paths completos,
com raciocínio, execução controlada e evidência auditável.
