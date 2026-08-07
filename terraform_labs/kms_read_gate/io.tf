variable "region" {
  type    = string
  default = "us-east-1"
}
variable "prefix" {
  type    = string
  default = "rastro-kms"
}

output "can_read_user_arn" { value = aws_iam_user.can_read.arn }
output "cannot_read_user_arn" { value = aws_iam_user.cannot_read.arn }
output "can_read_access_key_id" { value = aws_iam_access_key.can_read.id }
output "can_read_secret_access_key" {
  value     = aws_iam_access_key.can_read.secret
  sensitive = true
}
output "cannot_read_access_key_id" { value = aws_iam_access_key.cannot_read.id }
output "cannot_read_secret_access_key" {
  value     = aws_iam_access_key.cannot_read.secret
  sensitive = true
}
output "protected_secret_arn" { value = aws_secretsmanager_secret.protected.arn }
output "cmk_arn" { value = aws_kms_key.cmk.arn }

output "ground_truth" {
  value = jsonencode({
    lab = "kms_read_gate"
    true_paths = [
      {
        id          = "read_with_decrypt"
        entry       = aws_iam_user.can_read.arn
        target      = aws_secretsmanager_secret.protected.arn
        class       = "credential_access_direct"
        in_coverage = true
        note        = "GetSecretValue + kms:Decrypt — leitor real"
      }
    ]
    # FP conhecido ENQUANTO o discovery não capturar o kms_key_id por recurso: o
    # cannot-read tem GetSecretValue mas não decifra; sem a captura do KmsKeyId no
    # discovery, o read-gate fica inerte e o engine reporta o caminho = FP. Quando
    # a captura for implementada (contra este secret real), remover daqui.
    false_paths = [
      {
        entry      = aws_iam_user.cannot_read.arn
        target     = aws_secretsmanager_secret.protected.arn
        class      = "credential_access_direct"
        limitation = "discovery ainda não captura kms_key_id por recurso, então o read-gate não dispara em run real e o cannot-read (sem kms:Decrypt) é reportado"
      }
    ]
  })
}
