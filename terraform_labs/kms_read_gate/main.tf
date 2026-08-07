# Lab KMS read-gate (Camada C, modelo do Bloco 16.3).
#
# Um secret cifrado com CMK customer-managed. Dois users com secretsmanager:
# GetSecretValue no MESMO secret, mas só um tem kms:Decrypt na chave. O engine
# (com o read-gate) deve reportar SÓ o que decifra — ter GetSecretValue não basta.
#
# Testa REDUÇÃO DE FALSO POSITIVO: sem o gate, ambos seriam reportados.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

locals {
  tags = { ManagedBy = "rastro-labs", Lab = "kms_read_gate" }
}

resource "aws_kms_key" "cmk" {
  description             = "rastro lab CMK - read-gate"
  deletion_window_in_days = 7
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowAccountIAM"
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
      Action    = "kms:*"
      Resource  = "*"
    }]
  })
  tags = local.tags
}
resource "aws_kms_alias" "cmk" {
  name          = "alias/${var.prefix}-cmk"
  target_key_id = aws_kms_key.cmk.key_id
}

resource "aws_secretsmanager_secret" "protected" {
  name                    = "${var.prefix}-protected"
  kms_key_id              = aws_kms_key.cmk.arn
  recovery_window_in_days = 0
  tags                    = local.tags
}
resource "aws_secretsmanager_secret_version" "protected" {
  secret_id     = aws_secretsmanager_secret.protected.id
  secret_string = jsonencode({ note = "rastro-lab: only kms:Decrypt holders can really read this" })
}

# user COM decrypt — leitor real
resource "aws_iam_user" "can_read" {
  name          = "${var.prefix}-can-read"
  force_destroy = true
  tags          = local.tags
}
resource "aws_iam_user_policy" "can_read" {
  name = "read-with-decrypt"
  user = aws_iam_user.can_read.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [aws_secretsmanager_secret.protected.arn] },
      { Effect = "Allow", Action = ["kms:Decrypt"], Resource = [aws_kms_key.cmk.arn] },
    ]
  })
}
resource "aws_iam_access_key" "can_read" {
  user = aws_iam_user.can_read.name
}

# user SEM decrypt — tem GetSecretValue mas não decifra → o gate deve suprimir
resource "aws_iam_user" "cannot_read" {
  name          = "${var.prefix}-cannot-read"
  force_destroy = true
  tags          = local.tags
}
resource "aws_iam_user_policy" "cannot_read" {
  name = "read-without-decrypt"
  user = aws_iam_user.cannot_read.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [aws_secretsmanager_secret.protected.arn] },
    ]
  })
}
resource "aws_iam_access_key" "cannot_read" {
  user = aws_iam_user.cannot_read.name
}
