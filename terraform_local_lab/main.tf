data "aws_caller_identity" "current" {}

locals {
  decoy_bucket_name = "public-reports-${data.aws_caller_identity.current.account_id}"
}

data "aws_iam_policy_document" "audit_role_trust" {
  statement {
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [var.trusted_principal_arn]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "audit_role" {
  name               = var.audit_role_name
  assume_role_policy = data.aws_iam_policy_document.audit_role_trust.json

  tags = {
    ManagedBy = "terraform_local_lab"
    Purpose   = "rastro-first-real-path"
  }
}

resource "aws_iam_role" "bucket_reader_role" {
  name               = var.bucket_reader_role_name
  assume_role_policy = data.aws_iam_policy_document.audit_role_trust.json

  tags = {
    ManagedBy = "terraform_local_lab"
    Purpose   = "rastro-third-path-decoy"
  }
}

resource "aws_iam_role" "finance_audit_role" {
  name               = var.finance_audit_role_name
  assume_role_policy = data.aws_iam_policy_document.audit_role_trust.json

  tags = {
    ManagedBy = "terraform_local_lab"
    Purpose   = "rastro-fourth-path-dead-end"
  }
}

resource "aws_iam_role" "data_ops_role" {
  name               = var.data_ops_role_name
  assume_role_policy = data.aws_iam_policy_document.audit_role_trust.json

  tags = {
    ManagedBy = "terraform_local_lab"
    Purpose   = "rastro-fourth-path-success"
  }
}

resource "aws_iam_role_policy" "audit_role_s3" {
  name = "rastro-audit-role-s3"
  role = aws_iam_role.audit_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.sensitive_bucket.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = [
          "${aws_s3_bucket.sensitive_bucket.arn}/${var.object_key}"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "bucket_reader_role_s3" {
  name = "rastro-bucket-reader-role-s3"
  role = aws_iam_role.bucket_reader_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.decoy_bucket.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "finance_audit_role_s3" {
  name = "rastro-finance-audit-role-s3"
  role = aws_iam_role.finance_audit_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.sensitive_bucket.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "data_ops_role_s3" {
  name = "rastro-data-ops-role-s3"
  role = aws_iam_role.data_ops_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.sensitive_bucket.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = [
          "${aws_s3_bucket.sensitive_bucket.arn}/${var.object_key}"
        ]
      }
    ]
  })
}

resource "aws_s3_bucket" "sensitive_bucket" {
  bucket = var.bucket_name

  tags = {
    ManagedBy = "terraform_local_lab"
    Purpose   = "rastro-first-real-path"
  }
}

resource "aws_s3_bucket" "decoy_bucket" {
  bucket = local.decoy_bucket_name

  tags = {
    ManagedBy = "terraform_local_lab"
    Purpose   = "rastro-third-path-decoy"
  }
}

resource "aws_s3_object" "payroll_csv" {
  bucket       = aws_s3_bucket.sensitive_bucket.id
  key          = var.object_key
  content      = var.sample_object_content
  content_type = "text/csv"
  etag         = md5(var.sample_object_content)
}

resource "aws_s3_object" "decoy_csv" {
  bucket       = aws_s3_bucket.decoy_bucket.id
  key          = var.decoy_object_key
  content      = var.decoy_object_content
  content_type = "text/csv"
  etag         = md5(var.decoy_object_content)
}

resource "aws_s3_object" "dead_end_csv" {
  bucket       = aws_s3_bucket.sensitive_bucket.id
  key          = var.dead_end_object_key
  content      = var.dead_end_object_content
  content_type = "text/csv"
  etag         = md5(var.dead_end_object_content)
}

resource "aws_iam_policy" "rastro_operator_policy" {
  name        = "RastroOperatorPolicy"
  description = "Minimum permissions for the first real Rastro AWS path."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sts:GetCallerIdentity"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:ListRoles"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:SimulatePrincipalPolicy"
        ]
        Resource = [
          aws_iam_role.audit_role.arn,
          aws_iam_role.bucket_reader_role.arn,
          aws_iam_role.finance_audit_role.arn,
          aws_iam_role.data_ops_role.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sts:AssumeRole"
        ]
        Resource = [
          aws_iam_role.audit_role.arn,
          aws_iam_role.bucket_reader_role.arn,
          aws_iam_role.finance_audit_role.arn,
          aws_iam_role.data_ops_role.arn
        ]
      }
    ]
  })

  tags = {
    ManagedBy = "terraform_local_lab"
    Purpose   = "rastro-first-real-path"
  }
}

resource "aws_iam_user_policy_attachment" "operator_user_attachment" {
  count = var.operator_user_name != "" ? 1 : 0

  user       = var.operator_user_name
  policy_arn = aws_iam_policy.rastro_operator_policy.arn
}

resource "aws_iam_role_policy_attachment" "operator_role_attachment" {
  count = var.operator_role_name != "" ? 1 : 0

  role       = var.operator_role_name
  policy_arn = aws_iam_policy.rastro_operator_policy.arn
}
