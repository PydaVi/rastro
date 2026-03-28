# MVP Report

Objective: Demonstrate synthetic IAM privilege escalation path to sensitive bucket.

## Starting Conditions
```
{'flags': [], 'identities': {'analyst': {'available_actions': [{'action_type': 'enumerate', 'target': 'account', 'parameters': {'note': 'list_roles'}, 'technique': {'mitre_id': 'T1087.004', 'mitre_name': 'Account Discovery: Cloud Account', 'tactic': 'discovery', 'platform': 'AWS'}, 'tool': 'iam_list_roles'}, {'action_type': 'assume_role', 'target': 'AuditRole', 'parameters': {'note': 'attempt_role_assumption'}, 'technique': {'mitre_id': 'T1548', 'mitre_name': 'Abuse Elevation Control Mechanism', 'tactic': 'privilege-escalation', 'platform': 'AWS IAM'}, 'tool': 'iam_passrole'}]}}}
```

## Steps Taken
Total steps: 3

## Step-by-Step
```
1. ActionType.ENUMERATE analyst -> account (tool=iam_list_roles) | success=True | reason=Selected highest-priority action enumerate.
2. ActionType.ASSUME_ROLE analyst -> AuditRole (tool=iam_passrole) | success=True | reason=Selected highest-priority action assume_role.
3. ActionType.ACCESS_RESOURCE AuditRole -> sensitive_bucket (tool=s3_read_sensitive) | success=True | reason=Selected highest-priority action access_resource.
```

## Allowed Actions
```
[{'action_type': <ActionType.ENUMERATE: 'enumerate'>, 'actor': 'analyst', 'target': 'account', 'parameters': {'note': 'list_roles'}, 'technique': {'mitre_id': 'T1087.004', 'mitre_name': 'Account Discovery: Cloud Account', 'tactic': 'discovery', 'platform': 'AWS'}, 'tool': 'iam_list_roles'}, {'action_type': <ActionType.ASSUME_ROLE: 'assume_role'>, 'actor': 'analyst', 'target': 'AuditRole', 'parameters': {'note': 'attempt_role_assumption'}, 'technique': {'mitre_id': 'T1548', 'mitre_name': 'Abuse Elevation Control Mechanism', 'tactic': 'privilege-escalation', 'platform': 'AWS IAM'}, 'tool': 'iam_passrole'}, {'action_type': <ActionType.ACCESS_RESOURCE: 'access_resource'>, 'actor': 'AuditRole', 'target': 'sensitive_bucket', 'parameters': {'note': 'read_sensitive'}, 'technique': {'mitre_id': 'T1530', 'mitre_name': 'Data from Cloud Storage', 'tactic': 'collection', 'platform': 'S3'}, 'tool': 's3_read_sensitive'}]
```

## Blocked Actions
```
[]
```

## Observations
```
[{'success': True, 'details': {'details': 'Roles enumerated.'}}, {'success': True, 'details': {'granted_role': 'AuditRole', 'details': 'AssumeRole succeeded.'}}, {'success': True, 'details': {'details': 'Sensitive bucket accessed.'}}]
```

## Graph Summary
- Nodes: 5
- Edges: 4

## MITRE ATT&CK Mapping
```
[{'mitre_id': 'T1087.004', 'mitre_name': 'Account Discovery: Cloud Account', 'tactic': 'discovery', 'platform': 'AWS'}, {'mitre_id': 'T1548', 'mitre_name': 'Abuse Elevation Control Mechanism', 'tactic': 'privilege-escalation', 'platform': 'AWS IAM'}, {'mitre_id': 'T1530', 'mitre_name': 'Data from Cloud Storage', 'tactic': 'collection', 'platform': 'S3'}]
```

## Tool Chain
```
['iam_list_roles', 'iam_passrole', 's3_read_sensitive']
```

## Attack Graph (Mermaid)
```mermaid
graph TD
  identity_analyst["identity:analyst"]
  resource_account["resource:account"]
  resource_AuditRole["resource:AuditRole"]
  identity_AuditRole["identity:AuditRole"]
  resource_sensitive_bucket["resource:sensitive_bucket"]
  identity_analyst -->|"enumerate"| resource_account
  linkStyle 0 stroke:#1b7f3b,stroke-width:2px;
  identity_analyst -->|"assume_role"| resource_AuditRole
  linkStyle 1 stroke:#1b7f3b,stroke-width:2px;
  identity_analyst -->|"assume_role"| identity_AuditRole
  linkStyle 2 stroke:#1b7f3b,stroke-width:2px;
  identity_AuditRole -->|"access_resource"| resource_sensitive_bucket
  linkStyle 3 stroke:#1b7f3b,stroke-width:2px;
```

## Outcome
Objective met: True
