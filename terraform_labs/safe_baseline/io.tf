variable "region" {
  type    = string
  default = "us-east-1"
}
variable "prefix" {
  type    = string
  default = "rastro-safe"
}

output "readonly_user_arns" { value = aws_iam_user.readonly[*].arn }
output "readonly_access_key_ids" { value = aws_iam_access_key.readonly[*].id }
output "readonly_secret_access_keys" {
  value     = aws_iam_access_key.readonly[*].secret
  sensitive = true
}

# Controle negativo: NENHUM caminho verdadeiro. Qualquer achado = FP.
output "ground_truth" {
  value = jsonencode({
    lab         = "safe_baseline"
    true_paths  = []
    false_paths = []
  })
}
