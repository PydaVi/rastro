# Codex Labs Generator

Guia para o agente Codex criar novos labs de teste para o Rastro enquanto o desenvolvimento
do núcleo do engine está pausado (Blocos 7–10).

**O que fazer**: criar novos cenários de ataque no lab AWS real, testar com os scripts
existentes e documentar os resultados.

**O que NÃO tocar**: nenhum arquivo em `src/`, `tests/`, `tools/`, `scripts/run_bloco*.py`.
O engine não vai receber mudanças de código agora. Se um cenário falhar porque o engine
não suporta, documente o resultado como `FAIL (engine limitation)` — não tente adaptar o código.

---

## Contexto: o que o engine já sabe fazer

O Rastro hoje prova 9 classes de ataque em AWS real. Cada uma é um "profile":

| Profile | O que prova | Entry identity precisa de |
|---------|-------------|---------------------------|
| `aws-iam-role-chaining` | sts:AssumeRole direto | `sts:AssumeRole` no trust policy da role alvo |
| `aws-iam-attach-role-policy-privesc` | iam:AttachRolePolicy na role alvo | `iam:AttachRolePolicy` em Resource=* ou ARN da role |
| `aws-iam-create-policy-version-privesc` | iam:CreatePolicyVersion em policy da role | `iam:CreatePolicyVersion` na policy que a role usa |
| `aws-iam-pass-role-privesc` | iam:PassRole para serviço | `iam:PassRole` na role alvo |
| `aws-credential-access-secret` | lê secret diretamente e extrai credencial | `secretsmanager:GetSecretValue` no secret |
| `aws-credential-pivot` | lê secret → extrai creds → assume role | `secretsmanager:GetSecretValue` + secret contém AWS creds |
| `aws-credential-pivot-ssm` | lê SSM param → extrai creds → assume role | `ssm:GetParameter` + param contém AWS creds |
| `aws-credential-pivot-s3` | lê S3 object → extrai creds → assume role | `s3:GetObject` + objeto contém AWS creds |
| `aws-iam-create-access-key-pivot` | cria key em user alvo → assume role | `iam:CreateAccessKey` no user alvo |

---

## Conta AWS disponível

- Account ID: `550192603632`
- Region: `us-east-1`
- Terraform state em: `terraform-realistic-iam/terraform.tfstate`
- Credenciais admin: profile `default` em `~/.aws/credentials` (brainctl-user)

**NUNCA use `brainctl-user` como entry identity em campanhas.** Ele é admin de bootstrapping.
Crie novos IAM users para cada lab.

---

## Estrutura de um lab

Cada lab precisa de 5 coisas:

```
terraform-realistic-iam/<lab_name>/
  main.tf                           # recursos AWS a criar
  outputs.tf                        # access keys dos entry users
  rastro_local/
    <lab_name>.local.json           # fixture (snapshot de discovery)
    objective_<lab_name>.local.json # qual role provar acesso
    scope_<lab_name>_openai.local.json  # scope + autorização

scripts/
  run_<lab_name>.py                 # script de integração
```

---

## Como criar um lab: passo a passo

### 1. Terraform: cria os recursos AWS

Siga o padrão dos labs existentes. Veja `terraform-realistic-iam/ssm_parameter_pivot_real/` como referência.

Princípios:
- Nomes de usuários e roles devem ser realistas (não `privesc-X-user`)
  — use nomes de domínio de negócio: `data-pipeline-worker`, `audit-service-role`, `finance-processor-user`
- Cada lab deve ter pelo menos 1 "decoy" — um usuário ou role que parece explorável mas não é
- O trust policy da role alvo deve incluir o user intermediário (nos pivots) ou o entry user (no role chaining)

Exemplo para SSM pivot:
```hcl
resource "aws_iam_user" "entry" {
  name = "finance-ledger-reader"
}

resource "aws_iam_access_key" "entry" {
  user = aws_iam_user.entry.name
}

resource "aws_iam_user_policy" "entry_ssm" {
  user = aws_iam_user.entry.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter"]
      Resource = "arn:aws:ssm:us-east-1:550192603632:parameter/finance/config/service-credentials"
    }]
  })
}

resource "aws_ssm_parameter" "creds" {
  name  = "/finance/config/service-credentials"
  type  = "SecureString"
  value = jsonencode({
    AccessKeyId     = aws_iam_access_key.svc_user.id
    SecretAccessKey = aws_iam_access_key.svc_user.secret
  })
}

# svc_user que aparece no secret e pode assumir a role alvo
resource "aws_iam_user" "svc" {
  name = "finance-processor-svc"
}

resource "aws_iam_access_key" "svc" {
  user = aws_iam_user.svc.name
}

resource "aws_iam_role" "target" {
  name = "finance-admin-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = aws_iam_user.svc.arn }
      Action    = "sts:AssumeRole"
    }]
  })
}
```

Após `terraform apply`, pegue as access keys dos outputs.

### 2. Adicione as credenciais ao `~/.aws/credentials`

```ini
[rastro-<lab-name>-entry]
aws_access_key_id = AKIA...
aws_secret_access_key = ...
```

### 3. Crie o fixture `rastro_local/<lab_name>.local.json`

O fixture descreve o que o discovery encontraria neste ambiente.
Campos obrigatórios por tipo de recurso:

**identity.user** (entry user):
```json
{
  "resource_type": "identity.user",
  "identifier": "arn:aws:iam::550192603632:user/finance-ledger-reader",
  "metadata": { "name": "finance-ledger-reader" }
}
```

**identity.user** (target user para CreateAccessKey pivot):
```json
{
  "resource_type": "identity.user",
  "identifier": "arn:aws:iam::550192603632:user/finance-processor-svc",
  "metadata": {
    "name": "finance-processor-svc",
    "createkey_by": ["arn:aws:iam::550192603632:user/finance-ledger-reader"]
  }
}
```

**identity.role** (role alvo):
```json
{
  "resource_type": "identity.role",
  "identifier": "arn:aws:iam::550192603632:role/finance-admin-role",
  "metadata": { "name": "finance-admin-role" }
}
```

**secret.ssm_parameter** (para SSM pivot):
```json
{
  "resource_type": "secret.ssm_parameter",
  "identifier": "arn:aws:ssm:us-east-1:550192603632:parameter/finance/config/service-credentials",
  "metadata": {
    "name": "/finance/config/service-credentials",
    "readable_by": ["arn:aws:iam::550192603632:user/finance-ledger-reader"]
  }
}
```

**secret.secrets_manager** (para Secrets Manager pivot):
```json
{
  "resource_type": "secret.secrets_manager",
  "identifier": "arn:aws:secretsmanager:us-east-1:550192603632:secret/prod/db-credentials",
  "metadata": {
    "name": "prod/db-credentials",
    "readable_by": ["arn:aws:iam::550192603632:user/app-backend-user"]
  }
}
```

**data_store.s3_object** (para S3 pivot):
```json
{
  "resource_type": "data_store.s3_object",
  "identifier": "arn:aws:s3:::my-bucket/config/credentials.json",
  "metadata": {
    "name": "my-bucket/config/credentials.json",
    "readable_by": ["arn:aws:iam::550192603632:user/app-backend-user"]
  }
}
```

**Caller identity** (obrigatório na raiz do fixture):
```json
{
  "caller_identity": {
    "Account": "550192603632",
    "Arn": "arn:aws:iam::550192603632:user/finance-ledger-reader",
    "UserId": "AIDAXXXXXXX"
  }
}
```

### 4. Crie os arquivos objective e scope

**objective**:
```json
{
  "target_resource": "arn:aws:iam::550192603632:role/finance-admin-role",
  "success_mode": "assume_role_proved",
  "description": "Prove que finance-ledger-reader consegue assumir finance-admin-role via SSM pivot"
}
```

`success_mode` válidos:
- `"assume_role_proved"` — para todos os pivots e role chaining
- `"access_proved"` — para `aws-credential-access-secret` (leitura direta)
- `"mutation_executed"` — para IAM privesc (attach, create-policy-version)

**scope** (copie de um existente e ajuste):
```json
{
  "name": "scope-finance-ssm-pivot",
  "aws_account_ids": ["550192603632"],
  "allowed_services": ["iam", "sts", "ssm"],
  "planner": {
    "backend": "openai",
    "model": "gpt-4o"
  }
}
```

`allowed_services` por profile:
- SSM pivot: `["iam", "sts", "ssm"]`
- S3 pivot: `["iam", "sts", "s3"]`
- Secrets pivot: `["iam", "sts", "secretsmanager"]`
- CreateAccessKey: `["iam", "sts"]`
- IAM privesc: `["iam", "sts"]`

### 5. Crie o script de integração

Copie `scripts/run_bloco6d_ssm_pivot.py` como base e ajuste:
- `LAB_DIR`, `FIXTURE_PATH`, `OBJECTIVE_PATH`, `SCOPE_PATH`
- `OUTPUT`, `ACCOUNT`, `REGION`
- `ENTRY_USER_ARN`, `TARGET_ROLE_ARN`
- `profile` no `plan` dict
- `entry_credential_profiles` no `TargetConfig`
- `permitted_profiles` no `AuthorizationConfig`
- A chamada a `_derive_*_hypotheses` correta para o tipo de ataque:
  - SSM/S3/Secrets pivot: `_derive_credential_pivot_hypotheses(discovery_snapshot, [ENTRY_USER_ARN])`
  - CreateAccessKey: `_derive_create_access_key_hypotheses(discovery_snapshot, [ENTRY_USER_ARN])`

O filtro do `attack_class` no script deve bater com o tipo:
- SSM pivot: `h.attack_class == "ssm_pivot"`
- S3 pivot: `h.attack_class == "s3_pivot"`
- Secrets pivot: `h.attack_class == "credential_pivot"`
- CreateAccessKey: `h.attack_class == "iam_create_access_key_pivot"`

### 6. Execute e documente

```bash
OPENAI_API_KEY=sk-... .venv/bin/python scripts/run_<lab_name>.py 2>&1 | tee outputs_<lab_name>/result.txt
```

---

## Cenários sugeridos para criar (prioridade decrescente)

### Grupo A — Variações de pivot (alta prioridade)

Estes cenários já são suportados pelo engine. Criar variações com naming realista
testa que o engine não depende de naming conventions.

**A1 — Pivot duplo SSM** (2 SSM params, só 1 contém creds válidas)
- `analytics-consumer-user` tem acesso a 2 params SSM
- Param `/analytics/config/metrics-endpoint` contém config sem creds
- Param `/analytics/config/service-auth` contém creds reais
- Target: `analytics-platform-role`
- Esperado: engine lê ambos (ou vai direto ao correto) e prova

**A2 — Secrets Manager multi-secret** (2 secrets acessíveis, 1 útil)
- `reporting-agent-user` lê `prod/reporting/db-creds` (contém creds de svc user)
- `reporting-agent-user` também lê `prod/reporting/api-key` (não contém AWS creds)
- Target: `reporting-admin-role`
- Esperado: engine identifica o secret útil e prova

**A3 — S3 pivot com path real** (object key realista)
- Bucket `company-artifacts-550192603632`, object `deploy/configs/service-account.json`
- Entry: `deploy-agent-user` com `s3:GetObject` no bucket
- Target: `deploy-admin-role`
- Esperado: pivot via S3

**A4 — CreateAccessKey com decoy** (user extra que parece explorável)
- `infra-operator-user` tem `iam:CreateAccessKey` em `backup-sync-bot` (que tem acesso a role)
- `infra-operator-user` também tem `iam:ListUsers` (decoy — não leva a lugar)
- Target: `backup-admin-role`
- Esperado: engine usa CreateAccessKey, ignora ListUsers

### Grupo B — Combinações multi-vetor (média prioridade)

Um mesmo entry user tem mais de um path possível. Testa se o engine escolhe um
e completa (não precisa provar os dois).

**B1 — SSM pivot + Role chaining no mesmo entry user**
- `platform-svc-user` tem `ssm:GetParameter` em param com creds
- `platform-svc-user` TAMBÉM pode `sts:AssumeRole` diretamente na role alvo
- Target: `platform-ops-role`
- Esperado: engine prova via qualquer um dos dois paths (provavelmente role chaining por ser mais direto)
- Valor: valida que o engine não fica confuso com múltiplos paths

**B2 — IAM privesc + Credential pivot no mesmo entry user**
- `devops-manager-user` tem `iam:AttachRolePolicy` na role alvo
- `devops-manager-user` TAMBÉM lê um secret com creds de outro user que pode assumir a mesma role
- Target: `devops-admin-role`
- Esperado: engine escolhe attach-role-policy (mais direto) ou credential-pivot
- Valor: valida comportamento em grafos com múltiplos caminhos sobrepostos

**B3 — Chain 2 hops: CreateAccessKey → Role chaining**
- `queue-worker-user` tem `iam:CreateAccessKey` em `pipeline-orchestrator-user`
- `pipeline-orchestrator-user` pode `sts:AssumeRole` em `pipeline-admin-role`
- Entry → CreateAccessKey → nova identidade → AssumeRole → objetivo
- Esperado: `objective_met=True` em 3 steps
- Valor: cadeia de 2 pivots (engine já suporta isso — testar com naming novo)

### Grupo C — Domínios de negócio realistas (baixa prioridade)

Cenários que simulam infraestrutura de empresas reais (fintech, healthtech, SaaS B2B).
Naming completamente desvinculado de qualquer convenção de lab.

**C1 — Fintech: leitura de credencial de gateway de pagamento**
- Usuário: `transaction-processor` (microserviço de processamento)
- Lê `/payments/gateway/service-credentials` (SSM)
- Target: `payments-admin-role`

**C2 — Healthtech: acesso a dados de configuração clínica**
- Usuário: `hl7-integration-service`
- Lê secret `prod/ehr/integration-keys`
- Target: `clinical-data-admin-role`

**C3 — SaaS: deploy pipeline com acesso indevido a prod**
- Usuário: `ci-build-agent`
- Tem `iam:CreateAccessKey` em `prod-deploy-bot`
- Target: `production-infra-role`

---

## Como documentar os resultados

Crie `outputs_<lab_name>/RESULT.md` com:

```markdown
# Resultado: <lab_name>

Data: YYYY-MM-DD
Profile: <profile usado>
Entry: <entry user>
Target: <role alvo>

## Resultado
objective_met: True/False
Steps: N
Error: None / <mensagem>

## Steps
1. [tool] as user → success=True/False
2. ...

## Conclusão
PASS / FAIL (engine limitation) / FAIL (infra issue)

Se FAIL: descreva o que o engine tentou e por que falhou.
Se engine limitation: anote qual código precisaria ser adaptado.
```

---

## Checklist antes de rodar

- [ ] `terraform apply` executado e sem erros
- [ ] Access keys adicionadas em `~/.aws/credentials`
- [ ] `AWS_PROFILE=<entry-profile> aws sts get-caller-identity` retorna o ARN correto
- [ ] Fixture contém o `caller_identity` correto
- [ ] `readable_by` / `createkey_by` no fixture bate com o que o terraform criou
- [ ] O valor do SSM param / conteúdo do S3 object / conteúdo do secret contém
      `{"AccessKeyId": "AKIA...", "SecretAccessKey": "..."}` no formato JSON
- [ ] Trust policy da role alvo inclui o user intermediário (ou o entry user)
- [ ] OPENAI_API_KEY exportada antes de rodar o script

---

## Erros comuns

**"ERRO: nenhuma hipótese gerada"**
→ `readable_by` / `createkey_by` no fixture não bate com o entry user ARN.
Verifique spelling do ARN (case sensitive).

**`credential_extracted: False` no step 1**
→ O valor do SSM param / secret / S3 object não está em JSON com os campos corretos.
O detector procura por `AccessKeyId` + `SecretAccessKey` (case-insensitive). Confirme o conteúdo real:
```bash
aws ssm get-parameter --name "/finance/config/service-credentials" --with-decryption --query Parameter.Value
```

**`objective_met: False`, step de assume_role falhou**
→ Trust policy da role alvo não inclui o user intermediário (ou a identidade extraída).
Verifique se o ARN no trust policy bate com o user que tem as creds armazenadas.

**`NoCredentialError` no executor**
→ O profile no `entry_credential_profiles` não existe em `~/.aws/credentials`.

**Rate limit OpenAI (429)**
→ Aguarde 60s e tente novamente. O engine tem retry automático mas pode esgotar.

---

## O que NÃO criar

- Labs que requerem novos tipos de recursos AWS não listados acima
  (ex: RDS, DynamoDB, Lambda, EC2) — o engine não sabe interagir com eles ainda
- Labs com chains de 3+ pivots distintos — o engine suporta 1 pivot intermediário
- Modificações em `src/`, `tests/`, `tools/aws/`, `scripts/run_bloco*.py`

Se um cenário que você quer testar requer código novo, documente em `RESULT.md` como
`FAIL (engine limitation)` e descreva o que seria necessário. Isso é feedback valioso
para os Blocos 7–10.
