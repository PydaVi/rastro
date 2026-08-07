variable "region" {
  type    = string
  default = "us-east-1"
}
variable "prefix" {
  type    = string
  default = "rastro-ec2"
}
variable "instance_type" {
  type    = string
  default = "t3.micro"
}

# Credenciais do entry point — o operador configura no ~/.aws pra rodar o engine.
output "entry_user_arn" { value = aws_iam_user.entry.arn }
output "entry_access_key_id" { value = aws_iam_access_key.entry.id }
output "entry_secret_access_key" {
  value     = aws_iam_access_key.entry.secret
  sensitive = true
}
output "target_role_arn" { value = aws_iam_role.target.arn }
output "instance_profile_arn" { value = aws_iam_instance_profile.target.arn }
output "instance_id" { value = aws_instance.target.id }
output "crown_jewel_arn" { value = aws_secretsmanager_secret.crown_jewel.arn }

# GROUND TRUTH — autorado da INTENÇÃO do lab, com os ARNs reais. Nunca da saída
# do engine. Consumido pelo scorer de integridade (scripts/lab_scorer.py).
output "ground_truth" {
  value = jsonencode({
    lab = "ec2_ssm_pivot"
    true_paths = [
      {
        id          = "ec2_compute_pivot"
        entry       = aws_iam_user.entry.arn
        target      = aws_iam_role.target.arn
        class       = "compute_pivot"
        in_coverage = true
        note        = "ssm:SendCommand na instância -> credenciais do role do instance profile via IMDS"
      },
      {
        id          = "ec2_pivot_reaches_crown_jewel"
        entry       = aws_iam_user.entry.arn
        target      = aws_secretsmanager_secret.crown_jewel.arn
        class       = "credential_access_direct"
        in_coverage = true
        note        = "cadeia completa: compute pivot -> a target-role lê a crown jewel. O BFS multi-level do engine atravessa a role de compute_pivot e ACHA isso (validado ao vivo 2026-08-07)"
      }
    ]
    false_paths = []
  })
}
