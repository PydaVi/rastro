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
- harness sintético excessivamente curado
- paths muito roteirizados

e aumenta:
- discovery real
- target selection semântico
- inferência estrutural
- selection por expressividade ofensiva
- competição entre paths concorrentes
- reachability real
- modelagem explícita de credential acquisition
- robustez em mixed environments
- robustez com naming desfavorável ou obfuscado
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

### Critérios de progresso rumo ao attacker-thinker generalista

O roadmap deve produzir sinais observáveis de progresso. Exemplos:

- menos `profile-first`
- menos metadata curada
- mais inferência por `relationships`
- mais mixed benchmarks
- mais competição intra-superfície
- mais competição entre entry surfaces
- mais separação entre `identity reached` e `credentials acquired`
- mais validação real de chains fora de IAM-first puro
- mais promotion-to-real para classes `advanced` e `enterprise`
- mais suporte a aliases e naming desfavorável sem perder estabilidade

Um bloco não conta como progresso forte rumo ao polo generalista se aumentar só:
- número de bundles
- número de profiles
- número de comandos da CLI
- número de relatórios

sem aumentar também inferência, competição, reachability ou robustez estrutural.

### Sinais de drift indesejado

Os seguintes sinais devem ser tratados como alerta explícito:

- bundles crescendo mais rápido que a inferência
- heurísticas lexicais crescendo sem contrapartida estrutural
- novos profiles sem mixed benchmark correspondente
- avanço operacional sem benchmark novo de generalização
- excesso de correções específicas de harness sem ganho arquitetural
- promotion-to-real ausente para classes `advanced`/`enterprise` que já estão
  estáveis sinteticamente
- dependência contínua de metadata curada quando `relationships` já poderiam
  carregar a estrutura relevante

### Regra operacional obrigatória

Ao fechar cada bloco, registrar explicitamente:
- o que aproximou o projeto do polo generalista
- o que permaneceu dependente de campaigns conhecidas
- qual é o próximo experimento com maior leverage para mover a régua

Essa regra é obrigatória mesmo quando o bloco for principalmente operacional.
O objetivo é tornar o drift visível cedo.

### Direção prioritária atual

Os experimentos acumulados até aqui provaram robustez relevante em:
- cenários estruturados
- fixtures e harness sintéticos
- bundles e profiles conhecidos
- campaigns reais controladas e previamente modeladas
- mixed benchmarks com competição crescente

Isso foi necessário e valioso, mas cria um risco explícito de drift:
- continuar melhorando benchmark
- continuar refinando fixture set
- continuar refinando harness
- continuar ampliando profiles conhecidos

sem provar operação `blind real`.

O principal gap atual entre:
- `produto de validação`
e
- `attacker-thinker generalista`

não é mais convergência em cenário estruturado.
É o engine operando em modo realmente adversarial sobre ambiente AWS real pouco
lembrado, parcialmente esquecido e não pré-modelado especificamente para o run.

Regra prioritária deste momento:
- `credential acquisition` e `external entry reachability maturity` continuam importantes
- mas não são, agora, o bloco de maior leverage para medir a régua generalista
- o maior leverage agora é um `blind real assessment`

Próximo experimento de maior leverage:
- assessment real em conta AWS autorizada previamente montada
- sem fixture/profile específico para aquele ambiente
- com discovery real
- target selection real
- e registro explícito de onde o pipeline trava quando a pré-estruturação some

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

Leitura obrigatória deste bloco:
- aproxima o produto do uso operacional real
- continua mais perto de `campaign validator` do que de `generalista ofensivo`
- não deve crescer por muitos blocos consecutivos sem contrapartida em mixed
  benchmark, inferência estrutural ou validação real fora de IAM-first

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
O que aproximou o projeto do polo generalista:
- discovery real como entrada do assessment
- inventário menos dependente de alvo manual
O que permaneceu dependente de campaigns conhecidas:
- heurísticas iniciais ainda fortemente orientadas a foundation
Próximo experimento de maior leverage:
- target selection menos lexical e mais estrutural

Status do bloco 2:
- `target-selection run` implementado
- artefatos `target_candidates.json` e `target_candidates.md` implementados
- validado sobre o discovery real do `aws-foundation`
- resultado observado: 15 candidatos, 5 `high confidence`
- pendente: refinamento de heuristicas e reducao de ruido lexical
Direção do avanço: mais generalização ofensiva
O que aproximou o projeto do polo generalista:
- ranking explícito de candidatos
- primeiros sinais estruturais no selection
O que permaneceu dependente de campaigns conhecidas:
- metadata e naming ainda guiavam fortemente a priorização
Próximo experimento de maior leverage:
- synthesis menos `profile-first`

Status do bloco 3:
- `campaign-synthesis run` implementado
- artefatos `campaign_plan.json` e `campaign_plan.md` implementados
- objetivos e scopes gerados automaticamente por candidato
- validado sobre candidatos reais do `aws-foundation`
- resultado observado: 4 planos gerados, um por profile
- ajuste aplicado: role chaining agora prioriza `DataAccessRole` sobre roles de auditoria
- pendente: integrar `CampaignPlan[]` ao `assessment run`
Direção do avanço: mais operacionalização de campaigns conhecidas
O que aproximou o projeto do polo generalista:
- campanhas passaram a ser sintetizadas, não só escritas manualmente
O que permaneceu dependente de campaigns conhecidas:
- plans ainda saem de profiles conhecidos e famílias fechadas
Próximo experimento de maior leverage:
- assessment discovery-driven com competição entre candidates

Status do bloco 4:
- `assessment run --bundle aws-foundation --discovery-driven` implementado
- pipeline completo validado em AWS real
- artefatos encadeados preservados no assessment
- resultado observado: `assessment_ok=true`, 4/4 campanhas `passed`
- proximo gap real: refinar reachability/pruning e heuristicas de target selection
Direção do avanço: mais operacionalização de campaigns conhecidas
O que aproximou o projeto do polo generalista:
- discovery-driven deixou de exigir objetivo manual
O que permaneceu dependente de campaigns conhecidas:
- bundle foundation ainda domina o contrato do assessment
Próximo experimento de maior leverage:
- ambientes mistos e selection por expressividade ofensiva

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

Atualização adicional:
- mixed resolver menos curado implementado com:
  - `execution_fixture_set` inferido no selection
  - propagacao em `campaign synthesis`
  - resolucao no `get_mixed_synthetic_profile(...)`
- regressao inicial de `aws-iam-s3` identificada e corrigida
- rerun ponta a ponta confirmado em:
  - `outputs_mixed_generalization_variant_a_assessment/`
  - `outputs_mixed_generalization_variant_b_assessment/`
  - `outputs_mixed_generalization_variant_c_assessment/`
  - `outputs_mixed_generalization_variant_d_assessment/`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-049-mixed-resolver-structural-routing.md`
- leitura do bloco:
  - reduziu curadoria residual do harness sintetico
  - tornou mais explicito o contrato entre selection e execution
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto com chain mais profunda e mais de um alvo forte por entry
  surface implementado em:
  - `fixtures/mixed_generalization_variant_e.discovery.json`
- `mixed_generalization_cross_account` e `mixed_generalization_multi_step`
  expandidos para suportar novos targets e scopes dedicados
- resultado observado:
  - `outputs_mixed_generalization_variant_e_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-050-mixed-generalization-deeper-chain-and-shared-entry.md`
- leitura do bloco:
  - aumentou a competicao entre targets fortes sob a mesma entry surface
  - separou melhor `cross-account` direto de `multi-step` profundo
  - pressionou o benchmark enterprise sem voltar a drift profile-first
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto com estrutura derivada de `relationships` implementado em:
  - `fixtures/mixed_generalization_variant_f.discovery.json`
- `target selection` agora pode derivar:
  - `reachable_roles`
  - `pivot_chain`
  - `chain_depth`
  a partir do inventario relacional, sem depender desses campos no metadata do
  recurso
- resultado observado:
  - `outputs_mixed_generalization_variant_f_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-051-mixed-generalization-relationship-derived-structure.md`
- leitura do bloco:
  - reduziu curadoria estrutural residual no benchmark misto
  - aproximou o selection de inferencia baseada em grafo
  - aumentou a utilidade real do campo `relationships` no discovery snapshot
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto sem `semantic_tags` curado implementado em:
  - `fixtures/mixed_generalization_variant_g.discovery.json`
- resultado observado:
  - `outputs_mixed_generalization_variant_g_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-052-mixed-generalization-without-semantic-tags.md`
- leitura do bloco:
  - removeu mais um atalho semantico do benchmark
  - manteve selecao enterprise estavel com nomes reais + relacoes
  - aumentou confianca de que o scorer estrutural ja sustenta parte do ganho
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto com pivots e entry surfaces obfuscados implementado em:
  - `fixtures/mixed_generalization_variant_h.discovery.json`
- falha inicial isolada como mismatch de harness sintetico:
  - targets diretos de `role-chaining`, `lambda` e `kms` nao podiam ser
    obfuscados sem quebrar fixtures ARN-exatos
- correcao de benchmark aplicada preservando esses targets diretos
- resultado observado apos rerun:
  - `outputs_mixed_generalization_variant_h_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-053-mixed-generalization-obfuscated-target-harness-mismatch.md`
- leitura do bloco:
  - reduziu naming favorecido em pivots e entry surfaces
  - isolou corretamente um limite do harness sintetico, nao do engine
  - manteve o benchmark enterprise estavel apos a correcao
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto com alvos enterprise profundos menos nomeados por negocio
  implementado em:
  - `fixtures/mixed_generalization_variant_i.discovery.json`
- fixtures mistos de `cross-account` e `multi-step` expandidos para aceitar os
  aliases dos novos alvos
- resultado observado:
  - `outputs_mixed_generalization_variant_i_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-054-mixed-generalization-obfuscated-enterprise-targets.md`
- leitura do bloco:
  - reduziu naming de negocio nos alvos enterprise profundos
  - preservou separacao estrutural entre `cross-account` e `multi-step`
  - manteve o benchmark enterprise estavel ponta a ponta
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto com apoio lexical minimo nos alvos enterprise profundos
  implementado em:
  - `fixtures/mixed_generalization_variant_j.discovery.json`
- `api-key` e `master` removidos dos nomes finais desses alvos
- falha inicial isolada como mismatch localizado no harness de `cross-account`
- fixture ampliado para suportar multiplos aliases do mesmo alvo sem quebrar
  variantes anteriores
- resultado observado apos rerun:
  - `outputs_mixed_generalization_variant_j_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-055-mixed-generalization-low-lexical-enterprise-failure.md`
- leitura do bloco:
  - reduziu ainda mais o apoio lexical dos alvos enterprise
  - confirmou que a separacao principal ja vem de estrutura
  - expôs e corrigiu um limite localizado de harness, nao do engine
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto com alvos locais de S3 e SSM menos nomeados implementado em:
  - `fixtures/mixed_generalization_variant_k.discovery.json`
- fixtures sinteticos locais expandidos para suportar os aliases novos
- resultado observado:
  - `outputs_mixed_generalization_variant_k_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-056-mixed-generalization-obfuscated-local-targets.md`
- leitura do bloco:
  - reduziu naming favorecido tambem em alvos locais
  - manteve estabilidade do benchmark sem depender de `api_key` no parametro local
  - deixou o secret local compartilhado com `external-entry` como proximo alvo
    de maior leverage
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto com obfuscacao do secret local compartilhado com
  `external-entry` implementado em:
  - `fixtures/mixed_generalization_variant_l.discovery.json`
- falha inicial isolada como mismatch localizado no fixture set
  `compute-pivot-app` usado pelo roteamento estrutural de `aws-iam-secrets`
- fixture e scope `compute-pivot-app` expandidos para suportar os aliases:
  - `prod/sys/kv_a`
  - `prod/sys/kv_b`
- resultado observado apos rerun:
  - `outputs_mixed_generalization_variant_l_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-057-mixed-generalization-local-secret-obfuscation-failure.md`
- leitura do bloco:
  - reduziu naming favorecido tambem no secret local compartilhado entre
    `aws-iam-secrets` e `aws-external-entry-data`
  - expôs um acoplamento residual do harness ao `execution_fixture_set`
    `compute-pivot-app`
  - removeu esse acoplamento sem mudar o engine ofensivo
- o que aproximou do polo generalista:
  - menor dependencia de naming de negocio em alvo local compartilhado
  - maior robustez do benchmark misto quando o profile pode ser roteado para
    mais de um fixture set
- o que permaneceu dependente de campaigns conhecidas:
  - alias coverage ainda precisa ser mantida nos fixture sets sinteticos
- proximo experimento com maior leverage:
  - reduzir o apoio lexical restante no secret local compartilhado com
    `external-entry`
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto com apoio lexical ainda menor no secret local compartilhado
  implementado em:
  - `fixtures/mixed_generalization_variant_m.discovery.json`
- aliases reduzidos para:
  - `prod/app/s1`
  - `prod/app/s2`
  - `prod/app/s3`
- fixture sets `serverless-business-app` e `compute-pivot-app` expandidos
  preventivamente para suportar os aliases novos
- resultado observado:
  - `outputs_mixed_generalization_variant_m_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-058-mixed-generalization-lower-lexical-local-secret.md`
- leitura do bloco:
  - reduziu mais um apoio lexical residual no alvo local compartilhado entre
    `aws-iam-secrets` e `aws-external-entry-data`
  - preservou a preferencia estrutural de `external-entry` pelo alvo S3 local
  - manteve o benchmark enterprise estavel sem mudanca de engine
- o que aproximou do polo generalista:
  - menor dependencia de naming favorecido em secret local compartilhado
  - maior robustez do mixed benchmark sob aliases menos expressivos
- o que permaneceu dependente de campaigns conhecidas:
  - fixture sets sinteticos ainda precisam de cobertura explicita de aliases
- proximo experimento com maior leverage:
  - reduzir naming favorecido restante em deep targets locais e enterprise sem
    aumentar curadoria manual
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto com deep targets enterprise menos nomeados implementado em:
  - `fixtures/mixed_generalization_variant_n.discovery.json`
- aliases enterprise reduzidos para:
  - `prod/x/t1`
  - `prod/x/t2`
- fixture sets `cross-account` e `multi-step` expandidos para suportar os
  aliases novos
- resultado observado:
  - `outputs_mixed_generalization_variant_n_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-059-mixed-generalization-low-lexical-enterprise-aliases.md`
- leitura do bloco:
  - reduziu apoio lexical residual tambem nos alvos enterprise profundos
  - manteve separacao estrutural entre `cross-account` e `multi-step`
  - confirmou que `score_components.structural` ja domina nos dois casos
- o que aproximou do polo generalista:
  - menor dependencia de naming favorecido em targets enterprise
  - maior evidência de inferencia por profundidade, fronteira de conta e
    reachability estrutural
- o que permaneceu dependente de campaigns conhecidas:
  - fixture sets enterprise ainda exigem cobertura explicita de aliases
- proximo experimento com maior leverage:
  - reduzir curadoria manual remanescente de aliases e metadata nos fixture sets
    mistos, sem perder estabilidade end-to-end
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- suporte generico de aliases implementado em:
  - `src/core/fixture.py`
- nova variante mista aberta com aliases de baixo valor semantico:
  - `fixtures/mixed_generalization_variant_o.discovery.json`
- aliases novos validados sem duplicacao sistematica de actions/transitions:
  - local secret: `prod/r/a1`
  - enterprise: `prod/r/e1`, `prod/r/e2`
- resultado observado:
  - `outputs_mixed_generalization_variant_o_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-060-mixed-generalization-generic-fixture-aliases.md`
- leitura do bloco:
  - reduziu curadoria manual do harness sintetico
  - moveu a logica de alias para uma camada estrutural reutilizavel
  - preservou estabilidade end-to-end com naming ainda menos favorecido
- o que aproximou do polo generalista:
  - menor dependencia de ajustes manuais por alias em fixture sets mistos
  - maior capacidade de continuar pressionando naming desfavoravel sem
    crescimento proporcional do harness
- o que permaneceu dependente de campaigns conhecidas:
  - o benchmark ainda depende de fixture sets sinteticos por familia de path
- proximo experimento com maior leverage:
  - reduzir metadata curada remanescente no benchmark misto, mantendo
    estabilidade end-to-end
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- benchmark misto com metadata curada reduzida implementado em:
  - `fixtures/mixed_generalization_variant_p.discovery.json`
- `network.api_gateway` e `network.load_balancer` passaram a ser tratados como
  publicos por default no selection, salvo `exposure=private`
- metadata nao estrutural reduzida em:
  - roles
  - secrets
  - parameters
  - s3 objects
  - kms keys
  - instances
- resultado observado:
  - `outputs_mixed_generalization_variant_p_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-061-mixed-generalization-reduced-curated-metadata.md`
- leitura do bloco:
  - reduziu metadata curada remanescente sem quebrar o benchmark enterprise
  - aumentou a parcela de inferencia sustentada por relationships e campos
    estruturais minimos
  - manteve separacao correta entre `external-entry`, `cross-account` e
    `multi-step`
- o que aproximou do polo generalista:
  - menor dependencia de metadata nao estrutural
  - maior evidencia de inferencia estrutural reutilizavel
- o que permaneceu dependente de campaigns conhecidas:
  - fixture set routing e objective generation ainda dependem de familias de path
- proximo experimento com maior leverage:
  - reduzir curadoria residual em fixture set routing ou objective generation
    sem perder estabilidade end-to-end
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

### External Entry Reachability Maturity

`external entry` nao deve permanecer descrito apenas como:
- reachability estrutural via metadata
- path semantico plausivel
- pivô credenciado controlado ate o dado

O produto precisa evoluir para distinguir explicitamente, como estados e/ou
criterios separados:

- `network_reachable_from_internet`
- `backend_reachable`
- `credential_acquisition_possible`
- `data_path_exploitable`

Esses estados nao sao equivalentes.

`external entry` so pode ser descrito como `public exploit path proved end-to-end`
quando a cadeia completa estiver provada.

Antes disso, a formulacao correta deve separar:
- `public exposure structurally linked to privileged path`
de
- `public exploit path proved end-to-end`

O roadmap de `external entry` deve incluir prova progressiva de:
- route tables
- security groups
- Internet Gateway
- listener/rules de ALB/NLB
- integracao completa de API Gateway ate backend
- reachability real fim a fim da internet ate o workload

#### Bloco A — Modelagem explícita dos estados de reachability

Objetivo:
- introduzir os estados formais de maturidade de `external entry`
- separar exposicao publica declarada de explorabilidade real

O que o bloco prova:
- o produto consegue representar, relatar e avaliar separadamente:
  - `network_reachable_from_internet`
  - `backend_reachable`
  - `credential_acquisition_possible`
  - `data_path_exploitable`

O que ainda NAO prova:
- reachability de rede AWS real
- reachability fim a fim da internet ate o workload
- exploit path real ate o dado final

Direção do avanço: mais generalização ofensiva

Status atual do Bloco A:
- implementado no reporting com:
  - `external_entry_maturity.applicable`
  - `network_reachable_from_internet`
  - `backend_reachable`
  - `credential_acquisition_possible`
  - `data_path_exploitable`
  - `classification`
- findings de `aws-external-entry-data` agora distinguem:
  - `public exposure structurally linked to privileged path`
  de
  - `public exploit path proved end-to-end`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-062-external-entry-maturity-modeling.md`
- o que aproximou do polo generalista:
  - reduziu falso positivo conceitual em `external entry`
  - separou melhor exposicao estrutural, credenciamento e explotabilidade
- o que permaneceu dependente de campaigns conhecidas:
  - os estados ainda sao inferidos por semantica de steps conhecidos
  - ainda nao ha prova de reachability de rede AWS real
- proximo experimento com maior leverage:
  - discovery/relação de rede AWS para compute público

Atualização adicional:
- synthesis com objetivo derivado do candidato final foi endurecida para:
  - nao herdar `success_criteria.flag` do profile base
  - gerar `success_criteria.mode = target_observed`
- a intervencao revelou acoplamento residual entre:
  - objetivo gerado
  - semantica de sucesso
  - harness sintetico com targets canonicos
- correcoes aplicadas:
  - `target_observed` agora aceita prova por:
    - `action.target`
    - identidade/target observado em evidência canonicalizada
  - fixture aliases passaram a cobrir os paths afetados
- revalidacao observada:
  - `outputs_mixed_generalization_variant_p_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-063-target-based-generated-objectives-reveal-synthetic-coupling.md`
- o que aproximou do polo generalista:
  - menor dependencia de objetivos herdados do profile base
  - maior alinhamento entre candidato selecionado e criterio real de sucesso
  - menor acoplamento entre harness sintético e target canônico
- o que permaneceu dependente de campaigns conhecidas:
  - fixture set routing ainda existe por familias de path
  - mixed benchmark ainda depende de resolver sintético
- proximo experimento com maior leverage:
  - reduzir curadoria residual em fixture set routing ou objective generation
    sem reintroduzir acoplamento de target canônico
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- `campaign_synthesis` deixou de depender de `profile.objective_path` para
  gerar objetivos derivados
- o objetivo gerado agora e construído somente com:
  - `description`
  - `target`
  - `success_criteria`
- validacao observada:
  - teste unitario com `objective_path` inexistente passou
  - `outputs_mixed_generalization_variant_p_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-064-profile-independent-objective-generation.md`
- o que aproximou do polo generalista:
  - menor dependencia de objetivos base por familia de path
  - synthesis mais alinhada ao candidato selecionado, nao ao template do profile
- o que permaneceu dependente de campaigns conhecidas:
  - fixture set routing ainda existe por familias de path
  - o resolver sintético misto continua como camada de compatibilidade
- proximo experimento com maior leverage:
  - reduzir curadoria residual em fixture set routing, sem degradar o mixed
    benchmark enterprise
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- `execution_fixture_set` passou a ser inferido mais por estrutura do que por
  lista fixa de profiles
- sinais estruturais agora usados no routing:
  - `resource_type`
  - fronteira de conta
  - `chain_depth`
  - vínculo com compute publico
  - vínculo com runtime serverless
- validacao observada:
  - `outputs_mixed_generalization_variant_p_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-065-structural-fixture-set-routing.md`
- o que aproximou do polo generalista:
  - menor dependencia de roteamento por nome do profile
  - maior coerencia entre structure-aware selection e execution routing
- o que permaneceu dependente de campaigns conhecidas:
  - o resolver sintético misto ainda existe como camada separada
  - fixture sets continuam organizados por familias de path
- proximo experimento com maior leverage:
  - reduzir o papel do resolver sintético misto sem perder estabilidade no
    benchmark enterprise
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- `campaign_plan.json` passou a embutir `fixture_path`
- `run_generated_campaign()` agora executa diretamente a partir do plano quando
  `fixture_path` estiver presente
- o `profile_resolver` ficou como fallback, nao como dependencia obrigatoria
- validacao observada:
  - teste unitario com `profile_resolver` proibido passou
  - `outputs_mixed_generalization_variant_p_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-066-embedded-fixture-paths-reduce-mixed-resolver-dependence.md`
- o que aproximou do polo generalista:
  - plano de campanha mais auto-suficiente
  - menor dependencia de conhecimento externo ao plano na execucao sintética
- o que permaneceu dependente de campaigns conhecidas:
  - resolver sintético ainda existe como fallback
  - fixture sets continuam organizados por familias de path
- proximo experimento com maior leverage:
  - reduzir o papel do resolver sintético para casos realmente excepcionais,
    sem perder estabilidade do benchmark enterprise
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- `target_selection` passou a embutir no candidato:
  - `fixture_path`
  - `scope_template_path`
- `campaign_synthesis` passou a preferir esses caminhos embutidos, usando o
  resolver apenas como fallback
- validacao observada:
  - teste unitario sem `profile_resolver` passou
  - `outputs_mixed_generalization_variant_p_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-067-candidate-embedded-scope-and-fixture-contract.md`
- o que aproximou do polo generalista:
  - candidatos ficaram mais auto-suficientes
  - synthesis passou a depender menos de catalogo externo por familia
- o que permaneceu dependente de campaigns conhecidas:
  - o resolver sintético ainda existe como fallback
  - fixture sets continuam organizados por familias de path
- proximo experimento com maior leverage:
  - reduzir o fallback do resolver para casos realmente excepcionais, sem
    perder estabilidade do benchmark enterprise
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- o benchmark `mixed_generalization_variant_p` passou a executar ponta a ponta
  sem `profile_resolver`
- `run_discovery_driven_assessment()` deixou de depender de resolver default
  quando os artefatos gerados ja carregam:
  - `fixture_path`
  - `scope_template_path`
- validacao observada:
  - teste end-to-end sem resolver passou
  - `outputs_mixed_generalization_variant_p_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-068-mixed-benchmark-without-profile-resolver.md`
- o que aproximou do polo generalista:
  - benchmark enterprise misto deixou de depender de resolver sintético
  - mais do contrato passou a existir nos artefatos do proprio pipeline
- o que permaneceu dependente de campaigns conhecidas:
  - fixture sets sinteticos continuam organizados por familias de path
  - ainda existe fallback de resolver por compatibilidade
- proximo experimento com maior leverage:
  - reduzir dependencia residual de fixture sets por familia sem perder
    estabilidade do benchmark enterprise
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- fixture set unificado criado para `serverless-business-app` em:
  - `fixtures/serverless_business_app_unified_lab.json`
- classes consolidadas nesse fixture:
  - `aws-iam-s3`
  - `aws-iam-secrets`
  - `aws-iam-ssm`
  - `aws-iam-role-chaining`
  - `aws-iam-lambda-data`
  - `aws-iam-kms-data`
- validacao observada:
  - `outputs_serverless_business_app_variant_a_assessment/`
  - `campaigns_total=4`
  - `campaigns_passed=4`
  - `assessment_ok=true`
  - `outputs_mixed_generalization_variant_p_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-069-serverless-unified-fixture-set.md`
- o que aproximou do polo generalista:
  - menor dependencia de fixture sets por familia dentro do arquétipo serverless
  - maior coerencia entre ambiente sintetico e multiplas classes concorrentes
- o que permaneceu dependente de campaigns conhecidas:
  - `compute-pivot-app` ainda tem fixture sets separados por familia
  - `cross-account` e `multi-step` continuam especializados
- proximo experimento com maior leverage:
  - avaliar unificacao semelhante em `compute-pivot-app` ou decidir se o
    próximo salto é promoção real seletiva
Direção do avanço: mais generalização ofensiva

Atualização adicional:
- fixture set unificado criado para `compute-pivot-app` em:
  - `fixtures/compute_pivot_app_unified_lab.json`
- classes consolidadas nesse fixture:
  - `aws-iam-s3`
  - `aws-iam-secrets`
  - `aws-iam-ssm`
  - `aws-iam-role-chaining`
  - `aws-iam-compute-iam`
  - `aws-external-entry-data`
- validacao observada:
  - `outputs_compute_pivot_app_variant_a_assessment/`
  - `campaigns_total=4`
  - `campaigns_passed=4`
  - `assessment_ok=true`
  - `outputs_mixed_generalization_variant_p_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`
- descoberta arquitetural registrada em:
  - `docs/experiments/EXP-070-compute-unified-fixture-set.md`
- o que aproximou do polo generalista:
  - menor dependencia de fixture sets por familia tambem no arquétipo compute
  - maior proximidade entre arquétipo sintético e ambiente com multiplas classes
    concorrentes
- o que permaneceu dependente de campaigns conhecidas:
  - `cross-account` e `multi-step` continuam especializados
  - ainda existe fallback de resolver por compatibilidade
- proximo experimento com maior leverage:
  - consolidar formalmente o fechamento desta subfase e decidir o proximo salto
    entre generalizacao ofensiva adicional e promoção real seletiva
Direção do avanço: mais generalização ofensiva

### Consolidação da subfase — Generalização ofensiva do segundo nível

Status: concluída

Escopo consolidado nesta subfase:
- menos `profile-first`
- menos dependencia de metadata curada
- menos dependencia de `objective generation` por template de profile
- menos dependencia de `profile_resolver` no benchmark misto
- menos dependencia de fixture sets por familia nos arquétipos:
  - `serverless-business-app`
  - `compute-pivot-app`
- mais inferencia por `relationships`
- mais competicao:
  - intra-superficie
  - entre entry surfaces
  - entre classes concorrentes
- mais separacao entre:
  - `identity reached`
  - `credentials acquired`
- mais robustez com naming desfavoravel e aliases
- mixed benchmark enterprise estabilizado em:
  - `outputs_mixed_generalization_variant_p_assessment/`
  - `campaigns_total=9`
  - `campaigns_passed=9`
  - `assessment_ok=true`

O que aproximou o projeto do polo generalista:
- o pipeline discovery-driven enterprise passou a operar com muito menos
  conhecimento escondido fora dos artefatos gerados
- o benchmark misto deixou de depender de `profile_resolver`
- o contrato candidato -> plano -> execução ficou mais auto-suficiente
- os arquétipos sintéticos principais já suportam múltiplas classes no mesmo
  fixture

O que permaneceu dependente de campaigns conhecidas:
- `cross-account` e `multi-step` ainda usam fixtures especializados
- `cross-account` real continua bloqueado por requisito operacional de segunda
  conta
- `external entry` ainda carece de maturidade de reachability real de rede
  além da exposição estrutural e do pivô credenciado
- ainda existe fallback de resolver por compatibilidade, embora não seja mais
  dependência central do mixed benchmark

Decisão de transição:
- o próximo salto de maior leverage não é mais reduzir harness sintético local
- o próximo salto é aumentar prova real fora de `IAM-first` puro, preservando a
  régua de `external entry`

Próximo bloco escolhido:
- `External Entry Reachability Maturity — Bloco B`
  - discovery/relação de rede AWS para compute público
  - com promoção seletiva posterior para AWS real

Justificativa arquitetural:
- esta subfase já empurrou suficientemente a generalização ofensiva sintética
- o maior risco de drift agora é continuar refinando harness enquanto a prova
  real de `external entry` permanece conceitualmente incompleta
- avançar em reachability real mantém a prioridade AWS / Produto 01 e aumenta
  generalização ofensiva em um eixo que ainda não está epistemicamente fechado
Direção do avanço: mais generalização ofensiva

### Próxima macrofase — Validação real de generalização ofensiva

Status: iniciada

Objetivo macro:
- sair de `generalização sintética convincente`
- para `generalização ofensiva parcialmente provada em AWS real`

Critério macro de saída:
- `external entry` com reachability de rede mais rigorosa que mera exposição
  estrutural
- pelo menos uma validação real forte fora de `IAM-first` puro
- `cross-account real` preparado para execução imediata quando a segunda conta
  estiver disponível

Leitura arquitetural:
- o produto já se afastou de `campaign validator puro`
- mas ainda não pode ser tratado como `generalista ofensivo forte`
- os gaps reais agora estão em:
  - operation `blind real` ainda não provada
  - reachability de rede em `external entry`
  - prova real fora de `IAM-first`
  - `cross-account` real
  - scorer estrutural ainda excessivamente hand-written

#### Bloco prioritário — Blind Real Assessment

Objetivo:
- medir o comportamento do Produto 01 em modo realmente `blind`
- testar discovery real, target selection real e convergência do engine sobre um
  ambiente AWS não modelado especificamente para aquele run

Hipótese central:
- o engine já converge bem quando o path está estruturado em fixtures, profiles
  e benchmarks
- o principal gap atual é provar se ele continua útil quando:
  - a conta é real
  - o ambiente não foi fixture-izado para o run
  - o operador não lembra em detalhe a topologia
  - o target não foi pré-escolhido por profile específico

Desenho experimental:
- usar uma conta AWS real autorizada
- preferencialmente previamente montada e parcialmente esquecida pelo operador
- evitar fixture/profile pré-estruturado específico para aquele ambiente
- rodar o pipeline discovery-driven real
- permitir que discovery e selection escolham os candidatos
- registrar explicitamente, se houver falha, em qual camada o pipeline travou:
  - discovery insuficiente
  - target selection errado
  - inferência estrutural insuficiente
  - dependência residual de metadata curada
  - necessidade de conhecimento pré-modelado
  - falha de executor, policy ou representação de estado

Critérios de sucesso:
- assessment real executado sem fixture específico do ambiente
- ao menos um candidato relevante selecionado por discovery real
- convergência para um path útil, mesmo que o objetivo final não seja atingido
- documentação explícita do ponto de travamento se houver falha
- evidência suficiente para dizer se o principal gargalo atual está em:
  - discovery
  - selection
  - representação
  - executor
  - dependência residual de campanha conhecida

O que o bloco prova:
- se o pipeline discovery-driven sustenta um primeiro modo `blind real`
- se o engine consegue operar sem target previamente modelado para aquele ambiente
- qual é o gargalo arquitetural dominante quando a pré-estruturação desaparece

O que ainda NÃO prova:
- generalização total para qualquer conta AWS
- autonomia ofensiva madura
- cobertura real completa de `cross-account`
- independência completa de profiles conhecidos

Por que este bloco tem mais leverage agora do que benchmark sintético adicional:
- benchmark sintético adicional continua útil para maturação local
- mas já não responde a pergunta mais importante do projeto
- a pergunta mais importante agora é:
  - `o engine continua útil quando o ambiente real deixa de estar estruturado para ele?`
- esse experimento maximiza revelação arquitetural nova, mesmo com maior risco
  de falha

Leitura de prioridade:
- `credential acquisition` e `external entry reachability maturity` continuam na
  trilha de maturidade
- mas o `blind real assessment` é o bloco de maior leverage para a régua
  generalista neste momento

Direção do avanço: mais generalização ofensiva

Status atual:
- primeiro corte executado em AWS real
- documentado em:
  - `docs/experiments/EXP-083-blind-real-assessment-fixture-coupling.md`
  - `docs/experiments/EXP-084-blind-real-runtime-action-space-pollution.md`

Resultado do primeiro corte:
- discovery real funcionou
- target selection real funcionou em primeiro corte
- o principal travamento apareceu na execucao discovery-driven
- os candidatos e planos gerados ainda carregaram:
  - `execution_fixture_set`
  - `fixture_path`
  - `scope_template_path`
- a execucao caiu de volta em harness sintetico por familia de campanha

O que esse corte aproximou do polo generalista:
- provou que o gargalo dominante ja nao esta em preflight nem em discovery real
- isolou o principal bloqueio arquitetural atual:
  - a execucao ainda depende de campanha pre-modelada em fixture sintetico

O que permaneceu dependente de campaigns conhecidas:
- `run_generated_campaign()` ainda exige `fixture_path`
- `execute_run()` ainda exige `Fixture.load(...)`
- o assessment real continua discovery-driven ate o plano, mas nao ate a
  execucao

Proximo experimento com maior leverage para mover a regua:
- implementar um contrato de execucao discovery-driven real sem `fixture_path`
- rerodar o mesmo `Blind Real Assessment`
- registrar se o novo gargalo passa a ser:
  - action-space real insuficiente
  - target selection errado
  - inferencia estrutural insuficiente
  - executor/policy

Status apos iteracoes:
- o contrato de execucao discovery-driven real sem `fixture_path` foi implementado
- o scope deixou de herdar recursos sinteticos indevidos
- o primeiro `Blind Real Assessment` do `aws-foundation` agora converge em AWS real
  sem fixture especifico do ambiente
- resultado atual:
  - `campaigns_total = 2`
  - `campaigns_passed = 2`
  - `campaigns_preflight_failed = 0`

O que esse fechamento aproximou do polo generalista:
- removeu o principal bloqueio arquitetural entre discovery real e execucao real
- provou um primeiro caso de `blind real` fim a fim fora do quadrante de harness
- mostrou que `policy layer` continua sendo a alavanca correta para filtrar
  ruido real do ambiente

O que permaneceu dependente de campaigns conhecidas:
- o bundle validado foi apenas `aws-foundation`
- o ambiente blind real ainda tinha baixa heterogeneidade de superfícies
- ainda nao houve `blind real` em:
  - `external entry`
  - `compute pivot`
  - `advanced`
  - `enterprise`

Novo proximo experimento com maior leverage para mover a regua:
- executar um `Blind Real Assessment` em conta/autorizacao AWS com maior
  heterogeneidade de recursos e pivots
- preferencialmente contendo:
  - compute publico ou privado com role relevante
  - secrets/ssm reais
  - mais de um alvo plausivel concorrente
- objetivo: medir se a convergencia blind continua quando o ambiente deixa de
  ser quase exclusivamente `foundation`

Reteste IAM-privesc-heavy:
- executado em ambiente real fortemente dominado por IAM privilege escalation
- documentado em:
  - `docs/experiments/EXP-085-iam-heavy-blind-real-subcoverage-diagnosis.md`
  - `docs/experiments/EXP-088-generalization-confidence-correction-after-iam-heavy.md`

Resultado observado:
- o discovery viu o lab novo:
  - `65` resources
  - `46` roles IAM
- o output final, porem, ficou concentrado essencialmente em:
  - `IAM -> S3 exposure`
  - `IAM role chaining exposure`
- findings vieram repetidos muitas vezes
- a evidencia de `role chaining` ficou fraca e mais proxima de descoberta do
  que de exploracao provada

Correcao de leitura obrigatoria:
- a leitura anterior do progresso estava otimista demais
- parte do que foi tratado como `generalizacao ofensiva` era, na pratica:
  - maturidade de harness
  - melhoria de runtime parcial
  - melhoria de honestidade epistemologica
  - melhoria de blind execution parcial
- o reteste IAM-heavy reduziu a confianca na nota implicita de generalizacao do
  produto
- isso nao e regressao de software; e correcao de leitura arquitetural

Julgamento explicito atualizado:
- o nucleo atual ainda esta mais perto de `campaign validator` do que parecia
- discovery e selection reais melhoraram, mas isso nao compensa:
  - contrato de sucesso frouxo
  - findings inflados por multiplicidade de principal
  - runtime IAM-heavy ainda estreito
  - distinctness de path mal modelado
- continuar expandindo bundles, profiles e benchmarks sem refazer esses
  contratos seria erro estrategico

Leitura arquitetural:
- esse reteste revelou subcobertura relevante
- o gap nao e so `faltou mais profile`
- ele combina:
  - bundle inadequado para ambiente IAM-heavy
  - discovery IAM estrutural insuficiente
  - ranking IAM fraco
  - action space real limitado a `AssumeRole` + data access
  - reporting/findings sem higiene de deduplicacao e de classe de evidencia

Antes de novo reteste, precisa fechar:

#### Bloco de correção — IAM-Heavy Blind Real Coverage And Evidence Hygiene

Objetivo:
- corrigir o principal gargalo revelado pelo reteste IAM-privesc-heavy:
  - o engine ja roda em `blind real`, mas ainda cobre mal ambientes dominados
    por privilege escalation IAM e gera findings com evidencia/classificacao
    inadequadas

O que o bloco prova:
- findings deixam de colidir e repetir o mesmo artefato
- descoberta deixa de ser promovida automaticamente a exploracao validada
- o portfolio/runtime passa a cobrir classes IAM-privesc mais alinhadas ao tipo
  de ambiente testado
- ranking/selection passam a diferenciar melhor exploitability IAM

O que ainda NÃO prova:
- cobertura total de labs IAM-privesc conhecidos
- autonomia ofensiva madura em qualquer ambiente IAM-heavy
- `cross-account` real ou `enterprise` completo

Passos:
1. deduplicar campaigns/findings por `plan.id`, `report_json`,
   `target_resource` e fingerprint de evidencia
2. separar estados de evidencia:
   - `discovered`
   - `reachable`
   - `exploited`
   - `validated`
3. definir evidencia minima por classe antes de emitir finding validado
4. ampliar discovery IAM estrutural:
   - trust edges
   - policy attachments
   - sinais de permissao alteradora
5. ampliar portfolio/runtime para IAM privilege escalation real, alem de
   `AssumeRole`
6. ajustar target selection/ranking para ambientes dominados por IAM
7. definir metricas de sucesso do proximo reteste:
   - diversidade de classes
   - findings unicos
   - proporcao de findings realmente provados
   - cobertura acima de `foundation`
8. impedir contaminacao do `Blind Real Assessment` por `fixture_path`
   sintetico quando o ambiente for AWS real e o campaign tiver sido derivado de
   discovery real

Critério de saída:
- findings IAM-heavy sem colisao grosseira
- role chaining nao vira `validated` so por `target_observed`
- campaigns de `blind real` nao recaem em `execution_mode = dry_run` por
  roteamento de fixture sintetico
- ao menos uma nova classe IAM-privesc real aberta alem de `AssumeRole`
- proximo reteste consegue medir:
  - coverage real
  - qualidade de evidencia
  - diversidade de achados

Direção do avanço: mais generalização ofensiva

O que esse bloco aproxima do polo generalista:
- desloca o produto de `foundation exposure validator` para ofensiva IAM mais
  alinhada a ambiente real hostil
- reduz dependencia de campanhas conhecidas e de sucesso por observacao fraca
- melhora a honestidade epistemica do report final

O que permanece dependente de campaigns conhecidas:
- o portfolio IAM-heavy ainda precisa ser aberto
- o runtime real ainda nao cobre varias classes de abuse IAM
- o bundle `aws-foundation` continua insuficiente como medida de qualidade para
  esse tipo de lab

Status atual do bloco:
- concluido parcialmente:
  - higiene de findings inicial
  - classificacao minima de evidencia
  - binding explicito da entry role no report/findings
  - discovery IAM estrutural inicial
  - ranking IAM inicial com sinais de privilege escalation
- novo bloqueio revelado em:
  - `docs/experiments/EXP-086-iam-heavy-blind-real-fixture-routing-contamination.md`

Novo resultado observado no rerun IAM-heavy:
- `campaigns_total = 19`
- `campaigns_passed = 0`
- `campaigns_objective_not_met = 19`
- o assessment gerou planos IAM mais alinhados ao lab, mas parte relevante da
  execucao recaiu em:
  - `fixture_path = fixtures/serverless_business_app_unified_lab.json`
  - `execution_mode = dry_run`

Leitura arquitetural atualizada:
- o bloco de correcao revelou dois subproblemas independentes:
  1. hygiene/evidence/ranking IAM
  2. pureza do modo `blind real`
- antes de abrir novas classes IAM-privesc, precisa fechar o segundo:
  - impedir que campaigns discovery-driven em AWS real voltem a fixture
    sintetico por roteamento de archetype

Novo sub-bloco prioritario dentro desta correcao:
- `Blind Real Execution Purity For IAM-Heavy Assessment`

Objetivo:
- garantir que campaigns geradas por discovery em AWS real usem runtime blind
  real, e nao fixture sintetico herdado de archetype/family

O que esse sub-bloco prova:
- o proximo reteste IAM-heavy passa a medir coverage real do produto, nao
  contaminacao do harness

O que ainda nao prova:
- coverage suficiente de privilege escalation IAM
- sucesso de exploracao alem de `AssumeRole`

Novo proximo experimento com maior leverage para mover a regua:
- fechar primeiro a pureza de execucao do `blind real` para campaigns IAM-heavy
- depois rerodar o mesmo ambiente IAM-privesc-heavy com metricas explicitas de:
  - cobertura de classes
  - diversidade de findings
  - evidencia realmente provada

#### Bloco prioritario — Reestruturação do núcleo para blind real IAM-heavy

Objetivo:
- deslocar o produto de validacao de campaigns conhecidas para execucao
  ofensiva mais aberta em ambiente IAM-heavy real

Premissa explicita:
- o problema revelado pelo laboratorio IAM-heavy nao e cosmetico
- nao e apenas `abrir mais profiles`
- o nucleo do produto ainda foi desenhado demais como `campaign validator`
- antes de novo reteste, e necessario fechar um bloco de reestruturacao

O que o laboratorio revelou:
- discovery real ja nao e o gargalo principal
- selection real ja nao e o gargalo principal
- o gargalo migrou para:
  - contrato de execucao
  - action space real
  - portfolio ofensivo IAM
  - classificacao de evidencia
  - pureza do modo blind

Mudancas estruturais obrigatorias:
1. desacoplamento definitivo de `profile -> runtime`
2. modo blind real sem:
   - `fixture_path`
   - `scope_template_path`
   - `execution_fixture_set`
   - resolver sintetico implicito por archetype
3. modelo explicito de estados de prova por finding:
   - `observed`
   - `reachable`
   - `credentialed`
   - `exploited`
   - `validated_impact`
4. definicao de evidencia minima por classe ofensiva
5. portfolio IAM-privesc dedicado, separado do `aws-foundation`
6. ranking IAM por capacidade ofensiva estrutural, nao por naming/heuristica
   lexical como espinha principal
7. expansao do `BlindRealRuntime` para action space intermediario real, nao so
   access ao target final
8. metricas de coverage e deduplicacao proprias para reteste IAM-heavy

O que esse bloco prova:
- que o produto esta ficando epistemicamente mais honesto
- que o modo blind fica realmente blind
- que o proximo reteste vai medir coverage ofensiva real, nao contaminacao do
  harness

O que ele ainda nao prova:
- nao prova ainda generalizacao forte
- nao prova ainda cobertura total de IAM privesc
- nao substitui o reteste
- ele prepara o reteste para medir a coisa certa

Critério de saída:
- campaigns discovery-driven em AWS real nao recaem em fixture routing
  sintetico por familia/archetype
- findings nao colapsam `passed -> validated`
- existe criterio minimo de evidencia por classe IAM aberta
- existe portfolio IAM-privesc inicial separado do `aws-foundation`
- existe action space real intermediario alem de `AssumeRole`
- o proximo reteste IAM-heavy consegue medir:
  - coverage por classe
  - findings unicos
  - prova minima
  - contaminacao de harness

Novo criterio de sucesso de medio prazo:
- o produto precisa conseguir enfrentar o challenge `Wyatt` do CloudFoxable
  como teste cego
- `passar no Wyatt` nao significa reproduzir um write-up conhecido
- significa convergir, com discovery e selection reais, para uma chain hibrida
  app/network/cloud do tipo:
  - foothold interno
  - descoberta lateral relevante
  - pivô via aplicação
  - aquisição de credenciais de workload
  - acesso final ao dado

Regra obrigatoria para esse criterio:
- o futuro teste do `Wyatt` deve ser cego para o engine
- conhecimento humano previo sobre o challenge nao pode ser embutido como:
  - fixture especifico
  - profile especifico
  - target selection ad hoc
  - objetivo customizado para o ambiente
  - scoring moldado para nomes/recursos do challenge

Interpretacao correta:
- `Wyatt` passa a ser criterio de sucesso epistemico, nao benchmark cosmetico
- ele so conta se for resolvido em modo blind, com isolamento do conhecimento
  adquirido por write-up, walkthrough ou memoria do operador

O que esse criterio muda no roadmap:
- work futuro que apenas melhore execution de campaigns conhecidas nao aproxima
  o produto desse marco
- work que aumente:
  - path distinctness
  - blind runtime hibrido
  - app/network/cloud pivot
  - credential acquisition real
  - truthfulness de findings
  passa a ter prioridade maior

Direção do avanço: mais generalização ofensiva

O que esse bloco aproxima do polo generalista:
- reduz o acoplamento central de `campaign validator`
- faz o modo blind medir comportamento ofensivo real, nao sucesso de harness
- desloca a qualidade do produto para coverage, prova e impacto por classe

O que permanece dependente de campaigns conhecidas:
- o portfolio ainda parte de classes ofensivas conhecidas
- o runtime real continua estreito ate abrir novas classes IAM
- o reteste IAM-heavy ainda nao foi refeito sob esse novo contrato

Regra de priorizacao explicita:
- um novo reteste IAM-heavy agora tem MENOS leverage do que fechar este bloco
  estrutural
- rerodar o lab antes dessas correcoes aumentaria ruido, nao conhecimento

Ao fechar este bloco, registrar obrigatoriamente:
- o que aproximou o produto do polo generalista
- o que permaneceu dependente de campaigns conhecidas
- qual e o proximo reteste de maior leverage

Novo proximo experimento com maior leverage para mover a regua:
- fechar primeiro a `Reestruturacao do nucleo para blind real IAM-heavy`
- so depois rerodar o mesmo laboratorio IAM-privesc-heavy
- medindo:
  - coverage ofensiva real
  - evidencia minima por classe
  - unicidade de findings
  - ausencia de contaminacao do harness
- depois disso, preparar o primeiro teste cego orientado ao criterio `Wyatt`,
  sem embutir conhecimento especifico do challenge no runtime, selection ou
  portfolio

#### Bloco prioritario — Reestruturação do núcleo para verdade de path e distinctness

Objetivo:
- refazer os contratos centrais que hoje permitem ao produto parecer mais
  generalista no discurso do que no runtime e no reporting
- tirar do centro do nucleo:
  - `target_observed` como criterio upstream de sucesso
  - findings inflados por multiplicidade de principal
  - agregacao guiada por volume bruto em vez de path distinto

Premissa explicita:
- o problema atual nao e cosmetico
- nao e so `falta de mais portfolio`
- existe divida arquitetural critica no contrato de:
  - objective / success
  - finding / evidence
  - aggregation / distinctness
  - coverage measurement

O que precisa parar imediatamente:
1. parar de tratar `campaigns_passed` como proxy de progresso ofensivo
2. parar de promover findings volumosos como sinal de coverage
3. parar de abrir novos benchmarks sinteticos ou novas families vistosas antes
   de corrigir distinctness e truthfulness do core
4. parar de aceitar `target_observed` como centro do contrato de verdade
5. parar de interpretar multiplicidade de principal contra o mesmo alvo como
   coverage ofensiva

O que precisa ser refeito no nucleo:
1. reescrever o contrato de objective/success para remover o papel central de
   `target_observed`
2. separar explicitamente:
   - sucesso de campanha
   - estado de prova
   - impacto validado
3. redefinir findings para distinguir:
   - `distinct attack path`
   - `same path, multiple principals`
   - `same target, multiple proofs`
4. revisar agregacao/deduplicacao com chave orientada a path distinto e nao a
   volume de campaigns
5. expor `finding_state` por item no output principal, nao so no agregado
6. revisar metricas de coverage para:
   - coverage por classe ofensiva
   - coverage por distinct path
   - multiplicidade de principal separada
7. reavaliar `BlindRealRuntime` e synthesis para que runtime/evidence nao
   herdem semantica frouxa do objective

O que esse bloco prova:
- que o produto ficou epistemicamente mais honesto
- que findings deixam de inflar coverage artificialmente
- que o proximo reteste IAM-heavy medira diversidade estrutural de path, nao
  apenas volume de principals sobre o mesmo recurso

O que ele ainda nao prova:
- nao prova generalizacao forte por si so
- nao prova cobertura IAM-privesc satisfatoria
- nao substitui reteste real
- prepara o proximo reteste para medir a coisa certa

Critérios obrigatorios antes de qualquer novo reteste relevante:
1. `validated` nao pode coexistir com `target_observed` como criterio upstream
   principal
2. cada finding final precisa representar:
   - um path distinto
   - ou uma classe distinta explicitamente justificada
3. `assessment_findings.md` precisa expor `finding_state` por item
4. volume bruto de findings nao conta como progresso
5. reteste IAM-heavy so volta a ter leverage quando:
   - runtime blind real estiver puro
   - aggregation estiver orientada a distinct path
   - coverage estiver medida por classe ofensiva e distinctness

Direção do avanço: mais generalização ofensiva

O que esse bloco aproxima do polo generalista:
- reduz autoengano do produto
- troca volume de campanha por verdade de path
- reorienta o produto para distinctness estrutural e prova minima real

O que permanece dependente de campaigns conhecidas:
- o portfolio IAM-privesc ainda sera de classes conhecidas
- o runtime ainda precisara ser ampliado classe por classe
- a generalizacao forte continuara nao provada ate reteste real posterior

Regra de priorizacao explicita:
- esse bloco tem mais leverage do que qualquer novo benchmark vistoso
- esse bloco tem mais leverage do que qualquer novo reteste IAM-heavy agora
- rerodar antes dele aumentaria ruido e inflaria leitura de progresso

Reclassificacao obrigatoria dos avancos recentes:
- melhorias de `blind real` recentes contam como:
  - melhoria parcial de blind execution
  - melhoria de runtime/harness
  - melhoria de honestidade epistemologica
- elas nao contam, por si so, como prova de generalizacao forte

Novo proximo experimento com maior leverage para mover a regua:
- fechar primeiro `Core truthfulness and path distinctness`
- depois rerodar IAM-heavy com:
  - runtime blind real puro
  - distinct path quality
  - coverage por classe ofensiva
  - findings com prova minima e sem inflacao por principal

#### Bloco futuro — Blind Hybrid Challenge Readiness (`Wyatt` gate)

Objetivo:
- preparar o produto para um teste cego de challenge hibrido app/network/cloud
  em AWS real, usando `Wyatt` como gate epistemico de medio prazo

Hipotese central:
- o produto so pode alegar aproximacao real do polo `generalista ofensivo`
  quando conseguir convergir, em modo cego, para uma chain do tipo:
  - foothold inicial
  - descoberta lateral relevante
  - pivô via aplicação
  - aquisição de credenciais de workload
  - acesso final ao dado

Premissa obrigatoria:
- esse gate nao pode ser resolvido com conhecimento incorporado do challenge
- walkthrough, write-up e memoria humana do ambiente nao podem virar:
  - fixture
  - profile
  - objective
  - scope
  - scoring rule
  - selection hack

O que esse bloco prova:
- que o produto saiu do quadrante de `campaign validator` IAM/data-only
  e entrou em um nivel inicial de ofensiva hibrida blind
- que o runtime, selection e reporting conseguem sustentar um challenge mais
  proximo de atacante real do que de campaign conhecida

O que ele ainda nao prova:
- generalizacao ampla para qualquer challenge do CloudFoxable
- cobertura total de appsec/cloud pivot
- autonomia ofensiva madura em qualquer ambiente hostil

Dependencias obrigatorias antes de abrir esse gate:
1. fechar `Reestruturacao do nucleo para verdade de path e distinctness`
2. fechar `Reestruturacao do nucleo para blind real IAM-heavy`
3. runtime blind real com acoes intermediarias hibridas suficientes
4. findings agregados por distinct path, nao por multiplicidade de principal
5. evidencia minima por classe e por estagio de prova

Critério de entrada:
- quando o produto ja nao inflar coverage por:
  - `target_observed`
  - volume bruto de findings
  - multiplicidade de principal
- e quando o runtime blind real puder representar mais do que:
  - `AssumeRole`
  - `SimulatePrincipalPolicy`
  - acesso final a dado

Critério de saída:
- executar `Wyatt` como teste cego
- registrar explicitamente:
  - onde o engine convergiu sem ajuda
  - onde travou
  - se o bloqueio foi de:
    - discovery
    - selection
    - runtime
    - representacao
    - evidence/reporting
- o teste so conta como sucesso se a convergencia vier de comportamento blind
  real e nao de conhecimento previamente embutido

Direção do avanço: mais generalização ofensiva

O que esse bloco aproxima do polo generalista:
- introduz um gate real de challenge hibrido
- desloca o eixo do produto para app/network/cloud pivot
- reduz espaco para autoengano baseado em benchmark estruturado

O que permanece dependente de campaigns conhecidas:
- classes ofensivas ainda podem continuar sendo modeladas
- parte do portfolio ainda sera explicitamente nomeada
- mas o teste final desse gate deve isolar o conhecimento especifico do
  challenge

#### Bloco 1 — External Entry Reachability Real

Objetivo:
- provar `external entry` com semântica de reachability mais rigorosa, sem
  colapsar:
  - exposição estrutural
  - backend reachability
  - credential acquisition
  - data path exploitation

O que o bloco prova:
- o produto consegue modelar e começar a descobrir evidência de rede AWS para
  entry surfaces públicas
- `external entry` deixa de depender apenas de:
  - metadata estrutural
  - path semântico plausível
  - pivô credenciado controlado

O que ainda NÃO prova:
- exploit HTTP arbitrário
- universalidade para qualquer topologia AWS
- `cross-account`

Passos:
1. ampliar discovery AWS para rede relevante de compute público:
   - Internet Gateway
   - route tables
   - subnets
   - security groups
   - ENIs
   - public IPs
2. modelar relações de rede no inventory/relationships
3. criar benchmark sintético de reachability com estados separados:
   - superfície pública sem backend reachável
   - backend reachável sem cred acquisition
   - cred acquisition possível sem path ao dado
   - cadeia completa
4. refletir isso em selection / synthesis / reporting

Status atual:
- `EXP-071` confirmou o primeiro corte do bloco:
  - discovery AWS agora coleta:
    - instance profiles
    - instâncias EC2
    - Internet Gateways
    - route tables
    - subnets
    - security groups
  - o inventory agora registra relações explícitas de rede e vínculo até o
    workload:
    - `deployed_in_subnet`
    - `associated_with_route_table`
    - `routes_to_internet_gateway`
    - `protected_by_security_group`
    - `uses_instance_profile`
- Concluídos no primeiro corte:
  - passo 1
  - passo 2
- `EXP-072` isolou uma falha de benchmark:
  - o objetivo herdado de `aws-external-entry-data` colapsava estados
    intermediarios por `success_criteria.flag`
- `EXP-073` validou o benchmark sintético de maturidade com objetivo proprio:
  - superfície pública sem backend reachável
  - backend reachável sem cred acquisition
  - cred acquisition possível sem path ao dado
  - cadeia completa
- Concluído depois da correção de benchmark:
  - passo 3
- `EXP-074` integrou a nova semântica em:
  - `target selection`
  - `campaign synthesis`
  - reporting intermediario do plano
- Concluído:
  - passo 4
- `EXP-075` refinou o trecho estrutural:
  - `API Gateway / ALB -> backend`
  com sinais separados de:
  - `network_reachable_from_internet`
  - `backend_reachable`
- O bloco agora ja distingue melhor:
  - superficie publica declarada
  - superficie publica com sinais fortes de reachability ate backend
- `EXP-076` levou parte dessa semântica para o discovery AWS:
  - inventory de `network.load_balancer`
  - inventory de `network.api_gateway`
  - metadados minimos de exposição pública
- `EXP-077` adicionou o primeiro grafo estrutural de:
  - `load balancer -> listener -> target group`
  - `api gateway -> integration -> backend`
- `EXP-078` integrou esse grafo ao `target selection` de `aws-external-entry-data`
  para elevar:
  - `network_reachable_from_internet`
  - `backend_reachable`
  a partir de relationships observadas
- `EXP-042` foi rerodado com evidência explícita de rede no pivô real:
  - `ec2:DescribeRouteTables`
  - `ec2:DescribeSubnets`
  - `ec2:DescribeSecurityGroups`
  - `ec2:DescribeInternetGateways`
  - o report real agora exporta `network_path` com:
    - `internet_gateway_ids`
    - `route_table_ids`
    - `route_to_internet_gateway`
    - `security_group_public_ingress`
    - `public_ip`
  - para o lab de EC2 pública direta, isso elevou o caso para:
    - `public_exploit_path_proved_end_to_end`
- `EXP-079` promoveu `external entry` real via ALB:
  - `ALB publico -> listener -> target group -> backend EC2 -> role -> data`
  - a primeira execução revelou um gap de agregação:
    - o produto ainda exigia backend diretamente publico
  - a correção geral moveu a prova para:
    - `load balancer internet-facing`
    - `listener publico`
    - `forwarding`
    - `target health = healthy`
  - o rerun final elevou o caso para:
    - `public_exploit_path_proved_end_to_end`
- `EXP-080` promoveu `external entry` real via API Gateway:
  - `API Gateway publico -> integration -> ALB -> backend EC2 -> role -> data`
  - evidência real agora inclui:
    - `apigateway:GetStages`
    - `apigateway:GetIntegration`
    - mais o trecho `ALB -> target group -> backend healthy`
  - o run final também sustentou:
    - `public_exploit_path_proved_end_to_end`
- `EXP-081` promoveu `external entry` real via NLB:
  - `NLB publico -> listener TCP -> target group -> backend EC2 privado -> role -> data`
  - evidência real agora inclui:
    - `elasticloadbalancing:DescribeLoadBalancers`
    - `elasticloadbalancing:DescribeListeners`
    - `elasticloadbalancing:DescribeTargetGroups`
    - `elasticloadbalancing:DescribeTargetHealth`
  - o run final também sustentou:
    - `public_exploit_path_proved_end_to_end`
- `EXP-082` aprofundou `external entry` real via ALB com roteamento rico:
  - `ALB publico -> listener rule -> multiplos target groups -> backend correto -> role -> data`
  - evidência real agora inclui:
    - `elasticloadbalancing:DescribeRules`
    - `matched_listener_rule_arns`
    - `matched_listener_rule_priorities`
    - `matched_target_groups`
    - `multiple_target_groups_observed`
  - o run final também sustentou:
    - `public_exploit_path_proved_end_to_end`
- Pendentes:
  - observação real mais rica de host-based routing / regras concorrentes
  - API Gateway com integracoes e roteamento mais ricos

Critério de saída:
- discovery e reporting distinguem explicitamente:
  - `network_reachable_from_internet`
  - `backend_reachable`
  - `credential_acquisition_possible`
  - `data_path_exploitable`
- benchmark sintético novo validado
- pelo menos um lab real exporta evidência de rede suficiente para sustentar
  `public_exploit_path_proved_end_to_end` sem overclaim
- pelo menos duas famílias reais de `external entry` sustentam essa prova:
  - EC2 pública direta
  - ALB público com backend privado
- cobertura real adicional:
  - API Gateway publico com integration ate backend
  - NLB publico com backend privado
  - ALB publico com listener rules e multiplos target groups
Direção do avanço: mais generalização ofensiva

Leitura de leverage atual:
- este bloco continua importante para maturidade de `external entry`
- mas, neste momento, nao e o bloco de maior leverage para medir o polo
  generalista
- o maior leverage agora e o `Blind Real Assessment`, porque ele mede o
  comportamento do engine quando a pre-estruturacao do ambiente cai

#### Bloco 2 — Credential Acquisition Real Em Compute/External

Objetivo:
- endurecer a separação entre:
  - `identity reached`
  - `credentials acquired`

O que o bloco prova:
- o engine e o executor real não tratam pivô alcançado como credencial
  automaticamente adquirida
- reporting evita falso positivo operacional nessa fronteira

O que ainda NÃO prova:
- internet-to-backend fim a fim
- `cross-account`

Passos:
1. revisar estado e reporting de credenciais adquiridas
2. adicionar benchmarks focados em:
   - compute pivot com identidade alcançada mas sem cred acquisition
   - external entry com reachability parcial
3. validar executor real e findings

Critério de saída:
- nenhuma chain é marcada como explorável só por `reached_role`
- cred acquisition passa a ser prova explícita no produto
Direção do avanço: mais generalização ofensiva

#### Bloco 3 — External Entry Real End-to-End

Objetivo:
- obter a primeira validação real forte fora de `IAM-first` puro

O que o bloco prova:
- caminho real de:
  - entry surface pública
  - backend reachability
  - credential acquisition
  - acesso ao dado

O que ainda NÃO prova:
- generalização para todas as classes de `external entry`
- `cross-account`

Passos:
1. desenhar lab efêmero real mínimo e barato
2. subir ambiente
3. rodar assessment/campaign discovery-driven
4. coletar evidência de rede, pivô, credencial e dado
5. destruir ambiente

Critério de saída:
- classificar corretamente:
  - `public exposure structurally linked to privileged path`
  ou
  - `public exploit path proved end-to-end`
- com evidência real de rede e não só de pivô
Direção do avanço: mais generalização ofensiva

#### Bloco 4 — Cross-Account Real Readiness

Objetivo:
- preparar `cross-account` real sem improviso nem pseudo-validação

O que o bloco prova:
- contrato operacional multi-account completo
- readiness técnica e documental para promoção real

O que ainda NÃO prova:
- chain real cruzando duas contas

Passos:
1. consolidar contrato multi-account:
   - target
   - authorization
   - trust
   - evidência esperada
2. preparar lab efêmero de duas contas
3. preparar checklist operacional

Critério de saída:
- bloco pronto para execução imediata quando a segunda conta existir
Direção do avanço: mais generalização ofensiva

#### Bloco 5 — Cross-Account Real

Dependência:
- segunda conta controlada

Objetivo:
- obter a primeira validação real de `cross-account`

O que o bloco prova:
- trust real entre contas
- `sts:AssumeRole` cruzando boundary
- acesso ao dado na conta destino

O que ainda NÃO prova:
- cobertura total de enterprise

Passos:
1. subir lab efêmero de duas contas
2. rodar assessment/campaign controlada
3. coletar evidência real
4. destruir ambiente

Critério de saída:
- primeira validação real de `cross-account`
Direção do avanço: mais generalização ofensiva

#### Bloco 6 — Menos Scorer Curado

Objetivo:
- reduzir a dependência restante de scorer estrutural excessivamente
  hand-written

O que o bloco prova:
- maior parcela do ranking sustentada por:
  - relationships
  - reachability observada
  - profundidade e qualidade estrutural da chain

O que ainda NÃO prova:
- autonomia total do scorer

Passos:
1. separar explicitamente:
   - fato estrutural
   - heurística manual
2. tornar `score_components` mais auditável
3. criar benchmark adversarial contra scorer curado

Critério de saída:
- menos peso em regra manual textual
- mais peso em estrutura observada
Direção do avanço: mais generalização ofensiva

### Decisão futura de organização documental

Para evitar que o `PLAN.md` continue crescendo até perder função operacional,
fica registrada a seguinte divisão futura:

- `PLAN.md`
  - direção atual
  - próximo bloco
  - decisões abertas
  - documento curto e ativo
- `HISTORY.md`
  - histórico experimental completo
  - tabela consolidada
  - descobertas arquiteturais
- `REGUA.md`
  - critério permanente de generalização ofensiva vs operacionalização

Critério para executar essa divisão:
- quando o `PLAN.md` começar a dificultar leitura operacional do próximo bloco
- sem apagar histórico
- preservando rastreabilidade experimental

Decisão de início:
- o próximo bloco prioritário de maior leverage passa a ser:
  - `Blind Real Assessment`
- `External Entry Reachability Real` permanece como trilha de maturidade
- motivo:
  - mede o principal gap epistemológico atual:
    - operação blind real em conta AWS pouco lembrada e não pré-modelada
  - evita drift para benchmarkismo e melhoria infinita de harness
  - mantém AWS primeiro e Produto 01 primeiro
Direção do avanço: mais generalização ofensiva

#### Bloco B — Discovery/relação de rede AWS para compute público

Objetivo:
- ampliar o discovery para capturar estrutura de rede relevante de compute
  publico

O que o bloco prova:
- descoberta e relacao explicita de:
  - Internet Gateway
  - subnets
  - route tables
  - security groups
  - public IP / ENI / instance profile

O que ainda NAO prova:
- listener/rule efetivo ate backend
- integracao completa de API Gateway ate workload
- exploracao fim a fim a partir da internet

Direção do avanço: mais generalização ofensiva

#### Bloco C — ALB/NLB/API Gateway to backend reachability

Objetivo:
- modelar e provar a cadeia de reachability entre entry surface e backend

O que o bloco prova:
- listener/rules de ALB/NLB
- target groups e backend registrado
- integracao de API Gateway ate Lambda / backend compute
- separacao entre:
  - superficie publica declarada
  - backend realmente alcançavel

O que ainda NAO prova:
- aquisicao de credenciais
- exploracao completa ate o dado final
- validacao real de rede em AWS

Direção do avanço: mais generalização ofensiva

#### Bloco D — Promoção seletiva para AWS real com evidência de rede

Objetivo:
- promover `external entry` para AWS real com evidência de rede, nao apenas de
  path credenciado controlado

O que o bloco prova:
- evidência real de reachability da internet ate o workload
- distinção auditavel entre:
  - reachability de rede
  - aquisicao de credenciais
  - explotabilidade do path ate o dado

O que ainda NAO prova:
- generalizacao total para todas as classes de `external entry`
- exploit HTTP arbitrario ou vulnerabilidades de app

Direção do avanço: mais generalização ofensiva

#### Bloco E — Integração dessa semântica ao selection / synthesis / reporting

Objetivo:
- integrar maturidade de `external entry` ao pipeline discovery-driven

O que o bloco prova:
- `target selection` passa a considerar maturidade de reachability
- `campaign synthesis` deixa explicito em qual nivel o path se encontra
- reporting evita falso positivo conceitual em `external entry`

O que ainda NAO prova:
- prova automatica universal de internet-to-backend para qualquer ambiente AWS
- cobertura total de `external entry` multi-servico

Direção do avanço: mais generalização ofensiva

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
