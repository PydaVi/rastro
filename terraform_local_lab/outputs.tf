output "account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "audit_role_arn" {
  value = aws_iam_role.audit_role.arn
}

output "bucket_name" {
  value = aws_s3_bucket.sensitive_bucket.id
}

output "object_arn" {
  value = "${aws_s3_bucket.sensitive_bucket.arn}/${var.object_key}"
}

output "finance_audit_role_arn" {
  value = aws_iam_role.finance_audit_role.arn
}

output "data_ops_role_arn" {
  value = aws_iam_role.data_ops_role.arn
}

output "dead_end_object_arn" {
  value = "${aws_s3_bucket.sensitive_bucket.arn}/${var.dead_end_object_key}"
}

output "operator_policy_arn" {
  value = aws_iam_policy.rastro_operator_policy.arn
}
