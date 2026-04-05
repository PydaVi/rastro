# EXP-038 — Abertura de External Entry -> IAM -> Data

## Identificação
- ID: EXP-038
- Fase: 3
- Status: confirmada

## Contexto
Depois de abrir `IAM -> Compute -> IAM` no `compute-pivot-app`, o próximo passo era validar uma primeira classe de `external entry` com menos dependência de campaigns IAM-first pré-estruturadas.

O foco desta etapa foi abrir `external entry -> IAM -> data` em um arquétipo com:
- API Gateway pública
- load balancer público
- instância EC2 por trás da superfície pública
- role de aplicação alcançável
- dados finais ligados estruturalmente a essa role

## Hipóteses
- H1: o target selection consegue escolher alvo de `external entry` usando reachability estrutural, não só sinal lexical.
- H2: o pipeline discovery-driven consegue executar a classe `aws-external-entry-data` no `compute-pivot-app`.
- H3: a abertura de `external entry` pode reaproveitar o loop central e o mecanismo de pivot via tool sem refactor novo de domínio.

## Resultados por etapa

### Etapa 1 — Variante B do inventário compute
- snapshot criado em `fixtures/compute_pivot_app_variant_b.discovery.json`
- superfícies públicas adicionadas:
  - `arn:aws:apigateway:us-east-1::/restapis/payroll-webhook-public`
  - `arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/public-webhook-bridge`
- recursos sensíveis receberam `reachable_roles` no metadata

### Etapa 2 — Target selection estrutural
- melhor candidato de `aws-external-entry-data`:
  - `arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/payroll/backend-db-password`
- sinais observados:
  - `external_reachability_signal`
  - `public_path_roles`
- interpretação:
  - o ranking já usa estrutura de reachability, não apenas nome do recurso

### Etapa 3 — Assessment discovery-driven `aws-advanced`
- output gerado em `outputs_compute_pivot_app_advanced_variant_b_assessment/assessment.json`
- resultado:
  - `campaigns_total = 6`
  - `campaigns_passed = 6`
  - `assessment_ok = true`
- interpretação:
  - `aws-external-entry-data` entrou no pipeline discovery-driven
  - compute pivot e external entry coexistem no mesmo arquétipo sem quebrar foundation

## Implementação introduzida
- novo profile `aws-external-entry-data`
- `target selection` expandido para usar:
  - `reachable_roles`
  - `role_to_public_surfaces`
  - surfaces públicas como sinal estrutural de reachability
- novo fixture sintético:
  - `fixtures/compute_pivot_app_external_entry_lab.json`
- reutilização do tool:
  - `ec2_instance_profile_pivot`

## Descoberta principal
O Produto 01 deu o primeiro passo fora do modelo puramente IAM-first: agora já existe uma classe discovery-driven em que a superfície inicial é pública e o alvo final é escolhido com base em relação estrutural entre entry surface, identidade alcançável e dado sensível.

## Conclusão
- H1: confirmada
- H2: confirmada
- H3: confirmada
