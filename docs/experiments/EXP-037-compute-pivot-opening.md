# EXP-037 — Abertura de IAM -> Compute -> IAM

## Identificação
- ID: EXP-037
- Fase: 3
- Status: confirmada

## Contexto
Depois de validar o `foundation` no arquétipo `compute-pivot-app`, o próximo passo era abrir a classe `IAM -> Compute -> IAM` para reduzir dependência de campaigns IAM-first e empurrar o Produto 01 na direção de maior generalização ofensiva.

## Hipóteses
- H1: o pipeline discovery-driven consegue abrir a classe `aws-iam-compute-iam` no `compute-pivot-app`.
- H2: o engine reconhece sucesso quando um pivot via compute ativa um postcondition de tool e materializa uma nova identidade.
- H3: a política de target selection continua priorizando o alvo foundation mais valioso no inventário compute.

## Resultados por etapa

### Etapa 1 — Seleção inicial
- o novo profile `aws-iam-compute-iam` foi sintetizado
- o candidato principal foi `arn:aws:iam::123456789012:role/PayrollAppInstanceRole`
- interpretação:
  - a seleção estrutural de role ligada a instance profile funcionou

### Etapa 2 — Falha inicial do assessment discovery-driven `aws-advanced`
- resultado observado:
  - `campaigns_total = 5`
  - `campaigns_passed = 4`
  - `aws-iam-compute-iam = objective_not_met`
- comportamento:
  - o run executou `ec2_instance_profile_pivot` com sucesso
  - a evidência mostrou `reached_role = arn:aws:iam::123456789012:role/PayrollAppInstanceRole`
  - mesmo assim, o objetivo não foi marcado como atingido

### Etapa 3 — Ranking foundation no inventário compute
- o `aws-iam-s3` priorizou o bucket `arn:aws:s3:::compute-payroll-dumps-prod`
  em vez do objeto `.../payroll.csv`
- interpretação:
  - a política de scoring ainda está insuficiente para privilegiar o alvo
    object-level mais útil em inventários compute

## Causa raiz isolada

### Falha de representação de estado
- `StateManager.is_objective_met()` consultava `fixture.has_flag(required_flag)`
- isso ignora flags derivadas de postconditions de tools executadas com sucesso
- consequência:
  - o pivot compute gerava evidência e nova identidade, mas o objetivo baseado em
    flag nunca era considerado atendido

### Falha de policy
- o scoring de `aws-iam-s3` ainda não privilegia suficientemente objetos sobre buckets
  quando ambos compartilham sinais fortes

## Correções aplicadas
- `StateManager.is_objective_met()` passou a avaliar `required_flag` contra as flags ativas derivadas do estado, não contra o fixture estático
- o scoring de `aws-iam-s3` passou a:
  - favorecer mais targets object-level
  - penalizar buckets que já possuem objetos mais específicos no inventário
- o `target selection` ganhou sinais estruturais para `aws-iam-compute-iam`:
  - role ligada a instance profile
  - role ligada a instância EC2
  - reachability via superfície pública

## Revalidação

### Etapa 4 — Assessment discovery-driven `aws-advanced` após correções
- output gerado em `outputs_compute_pivot_app_advanced_variant_a_assessment/assessment.json`
- resultado:
  - `campaigns_total = 5`
  - `campaigns_passed = 5`
  - `assessment_ok = true`
- interpretação:
  - a classe `aws-iam-compute-iam` foi aberta com sucesso
  - o objetivo baseado em postcondition do tool passou a ser reconhecido corretamente
  - o ranking foundation no inventário compute voltou a privilegiar o alvo object-level

## Descoberta principal
O gap principal não estava no fixture nem no profile novo. Estava em uma limitação estrutural do engine: objetivos baseados em flags derivadas de tools não estavam sendo avaliados contra o estado ativo do run. Isso é um problema geral, não específico de compute pivot. A revalidação também mostrou que o target selection precisa combinar sinais lexicais com estrutura de reachability para não degradar em ambientes compute-heavy.

## Conclusão
- H1: confirmada
- H2: confirmada
- H3: confirmada
