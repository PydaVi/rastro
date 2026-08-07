variable "region" {
  type    = string
  default = "us-east-1"
}
variable "prefix" {
  type    = string
  default = "rastro-lambda"
}

output "entry_user_arn" { value = aws_iam_user.entry.arn }
output "entry_access_key_id" { value = aws_iam_access_key.entry.id }
output "entry_secret_access_key" {
  value     = aws_iam_access_key.entry.secret
  sensitive = true
}
output "target_role_arn" { value = aws_iam_role.target.arn }
output "function_arn" { value = aws_lambda_function.target.arn }
output "embedded_user_arn" { value = aws_iam_user.embedded.arn }

output "ground_truth" {
  value = jsonencode({
    lab = "lambda_env_pivot"
    true_paths = [
      {
        id          = "lambda_env_pivot"
        entry       = aws_iam_user.entry.arn
        target      = aws_iam_role.target.arn
        class       = "lambda_pivot"
        in_coverage = true
        note        = "lê a env da função -> extrai as creds do embedded-user -> assume a target-role"
      }
    ]
    false_paths = []
  })
}
