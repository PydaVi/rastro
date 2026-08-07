# Lab baseline seguro (Camada B — controle negativo).
#
# Recursos existem, mas NENHUM caminho de ataque: users só têm permissões inócuas
# (List/Describe/GetCallerIdentity), roles não confiam nesses users e não têm
# permissão perigosa. A resposta certa do engine é ZERO achado. Qualquer hipótese
# gerada aqui é FALSO POSITIVO medido — sem negativos não dá pra saber se o engine
# acha ataque ou só acha coisa.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.region
}

locals {
  tags = { ManagedBy = "rastro-labs", Lab = "safe_baseline" }
}

resource "aws_iam_user" "readonly" {
  count         = 3
  name          = "${var.prefix}-readonly-${count.index}"
  force_destroy = true
  tags          = local.tags
}
resource "aws_iam_user_policy" "readonly" {
  count = 3
  name  = "harmless-readonly"
  user  = aws_iam_user.readonly[count.index].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:ListBucket", "ec2:DescribeInstances", "sts:GetCallerIdentity", "cloudwatch:GetMetricData"]
      Resource = ["*"]
    }]
  })
}
resource "aws_iam_access_key" "readonly" {
  count = 3
  user  = aws_iam_user.readonly[count.index].name
}

# roles que NÃO confiam nos users acima (trust só um serviço AWS) e sem privesc
data "aws_iam_policy_document" "svc_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "svc" {
  count              = 2
  name               = "${var.prefix}-svc-role-${count.index}"
  assume_role_policy = data.aws_iam_policy_document.svc_trust.json
  tags               = local.tags
}
