variable "region" {
  description = "AWS region for the lab resources."
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "Bucket name used by the first real AWS path. Override if the default is unavailable."
  type        = string
  default     = "sensitive-finance-data"
}

variable "object_key" {
  description = "Object key used by the first real AWS path."
  type        = string
  default     = "payroll.csv"
}

variable "audit_role_name" {
  description = "Role name assumed by Rastro in the first real AWS path."
  type        = string
  default     = "AuditRole"
}

variable "bucket_reader_role_name" {
  description = "Distractor role name used by the third AWS path."
  type        = string
  default     = "BucketReaderRole"
}

variable "finance_audit_role_name" {
  description = "Dead-end role name used by the fourth AWS path."
  type        = string
  default     = "A-FinanceAuditRole"
}

variable "data_ops_role_name" {
  description = "Successful role name used by the fourth AWS path."
  type        = string
  default     = "Z-DataOpsRole"
}

variable "trusted_principal_arn" {
  description = "ARN of the existing IAM principal allowed to assume AuditRole."
  type        = string
}

variable "operator_user_name" {
  description = "Optional IAM user name to receive the operator policy attachment."
  type        = string
  default     = ""
}

variable "operator_role_name" {
  description = "Optional IAM role name to receive the operator policy attachment."
  type        = string
  default     = ""
}

variable "sample_object_content" {
  description = "Content uploaded to the sensitive object."
  type        = string
  default     = "employee_id,name,salary\n1,Alice,100000\n2,Bob,120000\n"
}

variable "decoy_object_key" {
  description = "Object key used in the decoy public bucket."
  type        = string
  default     = "quarterly-summary.csv"
}

variable "decoy_object_content" {
  description = "Content uploaded to the decoy public bucket."
  type        = string
  default     = "quarter,summary\nQ1,stable\nQ2,stable\n"
}

variable "dead_end_object_key" {
  description = "Object key visible in the dead-end branch of the fourth AWS path."
  type        = string
  default     = "budget-summary.csv"
}

variable "dead_end_object_content" {
  description = "Content uploaded to the dead-end object used by the fourth AWS path."
  type        = string
  default     = "department,summary\nfinance,forecast-only\n"
}
