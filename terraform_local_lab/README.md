# Terraform Local Lab

This folder is intentionally local-only and ignored by git.

It creates the minimum AWS resources for the first, third, and fourth real Rastro paths:
- one sensitive S3 bucket and object
- one decoy S3 bucket and object
- one assumable role named `AuditRole`
- one assumable distractor role named `BucketReaderRole`
- one dead-end role named `A-FinanceAuditRole`
- one successful backtracking role named `Z-DataOpsRole`
- one benign object named `budget-summary.csv` in the sensitive bucket
- one operator policy with the minimum permissions for the initial principal

Basic usage:

```bash
terraform init
cp terraform.tfvars.example terraform.tfvars
terraform plan
terraform apply
```

If you override `bucket_name`, role names, or object keys, you must also update local runtime files to match:
- `terraform_local_lab/rastro_local/aws_real_lab.local.json`
- `terraform_local_lab/rastro_local/aws_role_choice_lab.local.json`
- `terraform_local_lab/rastro_local/aws_backtracking_lab.local.json`
- `terraform_local_lab/rastro_local/objective_aws_backtracking.local.json`
- `terraform_local_lab/rastro_local/scope_aws_backtracking_real.local.json`
- `terraform_local_lab/rastro_local/scope_aws_backtracking_openai.local.json`

The state is local by default.
