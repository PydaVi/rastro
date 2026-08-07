# terraform_labs — labs de AWS real para a fase de validação

Labs em Terraform que provisionam ambientes reais pra validar o engine contra
AWS de verdade, seguindo os critérios de integridade de `docs/lab-integrity.md`:
cada lab **autora seu próprio ground_truth** (os caminhos de ataque reais,
derivados da INTENÇÃO do lab, nunca da saída do engine) como output do terraform,
com os ARNs reais. Inclui controle negativo (Camada B) e um plant de FP conhecido.

## Os labs

| lab | camada | o que valida |
|---|---|---|
| `ec2_ssm_pivot` | C | compute pivot via `ssm:SendCommand` → role do instance profile |
| `lambda_env_pivot` | C | credencial embutida na env da Lambda → assume role |
| `kms_read_gate` | C | secret cifrado com CMK: só quem tem `kms:Decrypt` deve ser reportado (reduz FP) |
| `safe_baseline` | B | **controle negativo** — resposta certa é zero achado (mede FP real) |

> **Independência (anti-viés):** estes labs são Camada C (eu os escrevi). A Camada A
> — labs externos tipo CloudGoat, que ninguém aqui escreveu — é o anti-viés mais
> forte e entra separado (clonar + aplicar), não neste diretório.

## Pré-requisitos

- Credenciais AWS suas configuradas (você é dono da conta) com permissão de
  **leitura ampla** pra o discovery enumerar (ex.: `ReadOnlyAccess`/`SecurityAudit`)
  e permissão pra criar os recursos do lab (o `apply`).
- `terraform` ≥ 1.6, `python` com o venv do projeto.
- **Custo:** os labs criam 1 instância `t3.micro` (só o EC2), users, roles, 1 CMK,
  1 Lambda, secrets. Baratos e efêmeros — **destrua depois**.

## Caminho do apply (você roda; eu não aplico)

Pra cada lab:

```bash
cd terraform_labs/<lab>            # ex.: ec2_ssm_pivot
terraform init
terraform apply                    # revise o plano e aprove
```

Depois de aplicado, rode o teste de cobertura (discovery real + scorer de
integridade, usando SUAS credenciais ambientes):

```bash
cd /home/pydavi/rastro
RASTRO_ENABLE_AWS_REAL=1 .venv/bin/python terraform_labs/test_lab.py <lab>
# ex.: ... test_lab.py ec2_ssm_pivot
#      ... test_lab.py kms_read_gate --bundle aws-advanced
```

O script lê o `ground_truth` do output do terraform, roda o discovery de verdade,
e pontua se o engine **enxergou** os caminhos reais (recall), sem inventar
nenhum (falso positivo). Saída honesta: miss inesperado = bug; FP esperado =
limite conhecido declarado; ✓ = íntegro.

Quando terminar:

```bash
cd terraform_labs/<lab>
terraform destroy
```

## O que este teste mede (e o que ainda não)

- **Mede agora:** cobertura de hipótese — o engine gera a hipótese do caminho
  real? É o piso: um caminho que o engine nem enxerga nunca vai provar nada.
- **Ainda não:** prova de execução (a campanha executa a mutação real + rollback).
  Precisa das credenciais de entrada (os `entry_access_key` que cada lab emite) e
  da métrica de prova no scorer — próximo passo da fase.

## Notas por lab

- **kms_read_gate** declara um **FP esperado** no ground_truth: enquanto o
  discovery não capturar o `kms_key_id` por recurso, o read-gate fica inerte em
  run real e o `cannot-read` (sem `kms:Decrypt`) é reportado. O teste vai mostrar
  esse FP como esperado — quando a captura for implementada contra este secret
  real, o gate dispara e o FP some.
- **ec2_ssm_pivot** provisiona a instância com `AmazonSSMManagedInstanceCore` +
  IP público pra o agente SSM registrar (necessário só pra a PROVA de execução;
  a cobertura de hipótese já funciona sem isso).
