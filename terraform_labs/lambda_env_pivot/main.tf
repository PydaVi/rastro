# Lab Lambda env-var pivot (Camada C, modelo do Bloco 16.3).
#
# Caminho REAL: entry-user (lambda:GetFunctionConfiguration) lê a config da função
# → as env vars contêm as credenciais de um "embedded-user" → o engine extrai as
# creds (identidade extraída) → assume a target-role (que confia no embedded-user).
#
# NB: os nomes das env vars NÃO podem ter prefixo AWS_ (reservado pelo Lambda).
# Usamos access_key_id/secret_access_key — que o detector do engine reconhece no
# JSON da env.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.0" }
  }
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

locals {
  tags = { ManagedBy = "rastro-labs", Lab = "lambda_env_pivot" }
}

# --- crown jewel que a target-role alcança ---
resource "aws_secretsmanager_secret" "crown_jewel" {
  name                    = "${var.prefix}-crown-jewel"
  recovery_window_in_days = 0
  tags                    = local.tags
}
resource "aws_secretsmanager_secret_version" "crown_jewel" {
  secret_id     = aws_secretsmanager_secret.crown_jewel.id
  secret_string = jsonencode({ note = "rastro-lab: reachable via the role the embedded creds can assume" })
}

# --- embedded-user: suas credenciais ficam nas env vars da função ---
resource "aws_iam_user" "embedded" {
  name          = "${var.prefix}-embedded-user"
  force_destroy = true
  tags          = local.tags
}
resource "aws_iam_access_key" "embedded" {
  user = aws_iam_user.embedded.name
}

# --- target-role: confia no embedded-user e alcança a crown jewel ---
data "aws_iam_policy_document" "target_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [aws_iam_user.embedded.arn]
    }
  }
}
resource "aws_iam_role" "target" {
  name               = "${var.prefix}-target-role"
  assume_role_policy = data.aws_iam_policy_document.target_trust.json
  tags               = local.tags
}
resource "aws_iam_role_policy" "target_reads_jewel" {
  name = "read-crown-jewel"
  role = aws_iam_role.target.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.crown_jewel.arn]
    }]
  })
}
# permitir que o embedded-user assuma a target-role (permission policy do lado dele)
resource "aws_iam_user_policy" "embedded_assume" {
  name = "assume-target"
  user = aws_iam_user.embedded.name
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["sts:AssumeRole"], Resource = [aws_iam_role.target.arn] }]
  })
}

# --- a função Lambda (execution role mínima; nunca é invocada, só lida) ---
data "aws_iam_policy_document" "lambda_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "lambda_exec" {
  name               = "${var.prefix}-exec-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
  tags               = local.tags
}
data "archive_file" "handler" {
  type        = "zip"
  output_path = "${path.module}/handler.zip"
  source {
    content  = "def handler(event, context):\n    return {}\n"
    filename = "handler.py"
  }
}
resource "aws_lambda_function" "target" {
  function_name    = "${var.prefix}-worker"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.handler.output_path
  source_code_hash = data.archive_file.handler.output_base64sha256
  environment {
    variables = {
      # credenciais embutidas (a vulnerabilidade). Nomes sem prefixo AWS_.
      access_key_id     = aws_iam_access_key.embedded.id
      secret_access_key = aws_iam_access_key.embedded.secret
      app_stage         = "prod"
    }
  }
  tags = local.tags
}

# --- entry point: user que lê a config da função ---
resource "aws_iam_user" "entry" {
  name          = "${var.prefix}-entry-user"
  force_destroy = true
  tags          = local.tags
}
resource "aws_iam_user_policy" "entry" {
  name = "lambda-read-entry"
  user = aws_iam_user.entry.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:GetFunctionConfiguration", "lambda:GetFunction"]
      Resource = [aws_lambda_function.target.arn]
    }]
  })
}
resource "aws_iam_access_key" "entry" {
  user = aws_iam_user.entry.name
}
