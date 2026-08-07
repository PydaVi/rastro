# Lab EC2 — compute pivot via ssm:SendCommand (Camada C, modelo do Bloco 16.3).
#
# Caminho de ataque REAL provisionado (a intenção, base do ground_truth):
#   entry-user (ssm:SendCommand na instância) → rouba as credenciais do role do
#   instance profile via IMDS → o role alcança a "crown jewel" (um secret).
# O engine deve gerar a hipótese compute_pivot: entry-user → target-role.
#
# Reachability de rede NÃO é o vetor aqui (isso é external_entry, superfície
# separada) — o vetor é a permissão IAM ssm:SendCommand, IAM-grounded.

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
data "aws_vpc" "default" { default = true }
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}
data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

locals {
  tags = { ManagedBy = "rastro-labs", Lab = "ec2_ssm_pivot" }
}

# --- crown jewel: o que o role da instância alcança (prova de valor) ---
resource "aws_secretsmanager_secret" "crown_jewel" {
  name                    = "${var.prefix}-crown-jewel"
  recovery_window_in_days = 0
  tags                    = local.tags
}
resource "aws_secretsmanager_secret_version" "crown_jewel" {
  secret_id     = aws_secretsmanager_secret.crown_jewel.id
  secret_string = jsonencode({ note = "rastro-lab: crown jewel reachable via instance role" })
}

# --- role da instância (o alvo do pivot) ---
data "aws_iam_policy_document" "ec2_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "target" {
  name               = "${var.prefix}-target-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
  tags               = local.tags
}
# SSM core: o agente registra a instância (necessário pro SendCommand ao vivo)
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.target.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
# a role alcança a crown jewel (torna o pivot uma escalação concreta)
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
resource "aws_iam_instance_profile" "target" {
  name = "${var.prefix}-target-profile"
  role = aws_iam_role.target.name
  tags = local.tags
}

# --- a instância ---
resource "aws_security_group" "lab" {
  name        = "${var.prefix}-sg"
  description = "rastro ec2 pivot lab — egress only (SSM)"
  vpc_id      = data.aws_vpc.default.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}
resource "aws_instance" "target" {
  ami                         = data.aws_ssm_parameter.al2023_ami.value
  instance_type               = var.instance_type
  subnet_id                   = tolist(data.aws_subnets.default.ids)[0]
  vpc_security_group_ids      = [aws_security_group.lab.id]
  iam_instance_profile        = aws_iam_instance_profile.target.name
  associate_public_ip_address = true # conectividade SSM sobre internet
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "optional"
  }
  tags = merge(local.tags, { Name = "${var.prefix}-target" })
}

# --- entry point: user com ssm:SendCommand na instância + o que o executor chama ---
resource "aws_iam_user" "entry" {
  name          = "${var.prefix}-entry-user"
  force_destroy = true
  tags          = local.tags
}
resource "aws_iam_user_policy" "entry" {
  name = "compute-pivot-entry"
  user = aws_iam_user.entry.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:SendCommand", "ssm:GetCommandInvocation", "ssm:StartSession"]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "iam:GetInstanceProfile",
          "ec2:DescribeInstances",
          "ec2:DescribeIamInstanceProfileAssociations",
        ]
        Resource = ["*"]
      },
    ]
  })
}
resource "aws_iam_access_key" "entry" {
  user = aws_iam_user.entry.name
}
