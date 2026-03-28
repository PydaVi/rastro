from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ACCOUNT_ID_RE = re.compile(r"\b\d{12}\b")
IAM_USER_ARN_RE = re.compile(r"arn:aws:iam::\d{12}:user/[^\s'\"]+")
IAM_ROLE_ARN_RE = re.compile(r"arn:aws:iam::\d{12}:role/[^\s'\"]+")
STS_ASSUMED_ROLE_ARN_RE = re.compile(r"arn:aws:sts::\d{12}:assumed-role/[^/\s'\"]+/[^\s'\"]+")
S3_ARN_RE = re.compile(r"arn:aws:s3:::[^/\s'\"]+/[^\s'\"]+")
S3_URI_RE = re.compile(r"s3://[^/\s'\"]+/[^\s'\"]+")
ROLE_NAME_RE = re.compile(r"\bAuditRole\b")
USER_NAME_RE = re.compile(r"\bbrainctl-user\b")
SESSION_NAME_RE = re.compile(r"\brastro-audit-session\b")
BUCKET_KEY_LITERAL_RE = re.compile(r"\bsensitive-finance-data/payroll\.csv\b")
BUCKET_LITERAL_RE = re.compile(r"\bsensitive-finance-data\b")
OBJECT_KEY_LITERAL_RE = re.compile(r"\bpayroll\.csv\b")
ROOT_LITERAL_RE = re.compile(r"\broot\b")


def sanitize_value(value: Any, field_name: str | None = None) -> Any:
    if isinstance(value, dict):
        return {k: sanitize_value(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_value(item, field_name) for item in value]
    if isinstance(value, str):
        if field_name == "bucket":
            return "<REDACTED_BUCKET>"
        if field_name == "object_key":
            return "<REDACTED_OBJECT_KEY>"
        if field_name == "preview":
            return "<REDACTED_CONTENT_PREVIEW>"
        if field_name == "authorization_document":
            return value
        value = STS_ASSUMED_ROLE_ARN_RE.sub(
            "arn:aws:sts::<AWS_ACCOUNT_ID>:assumed-role/<REDACTED_ROLE>/<REDACTED_SESSION>",
            value,
        )
        value = IAM_USER_ARN_RE.sub(
            "arn:aws:iam::<AWS_ACCOUNT_ID>:user/<REDACTED_USER>",
            value,
        )
        value = IAM_ROLE_ARN_RE.sub(
            "arn:aws:iam::<AWS_ACCOUNT_ID>:role/<REDACTED_ROLE>",
            value,
        )
        value = S3_ARN_RE.sub(
            "arn:aws:s3:::<REDACTED_BUCKET>/<REDACTED_OBJECT_KEY>",
            value,
        )
        value = S3_URI_RE.sub(
            "s3://<REDACTED_BUCKET>/<REDACTED_OBJECT_KEY>",
            value,
        )
        value = ACCOUNT_ID_RE.sub("<AWS_ACCOUNT_ID>", value)
        value = ROLE_NAME_RE.sub("<REDACTED_ROLE>", value)
        value = USER_NAME_RE.sub("<REDACTED_USER>", value)
        value = SESSION_NAME_RE.sub("<REDACTED_SESSION>", value)
        value = BUCKET_KEY_LITERAL_RE.sub("<REDACTED_BUCKET>/<REDACTED_OBJECT_KEY>", value)
        value = BUCKET_LITERAL_RE.sub("<REDACTED_BUCKET>", value)
        value = OBJECT_KEY_LITERAL_RE.sub("<REDACTED_OBJECT_KEY>", value)
        return value
    return value


def has_real_api_calls(payload: Any) -> bool:
    if isinstance(payload, dict):
        if payload.get("real_api_called") is True:
            return True
        return any(has_real_api_calls(v) for v in payload.values())
    if isinstance(payload, list):
        return any(has_real_api_calls(v) for v in payload)
    return False


def write_sanitized_artifacts(output_dir: Path, report_json: dict, report_markdown: str, audit_path: Path) -> None:
    if not has_real_api_calls(report_json):
        return

    sanitized_json = sanitize_value(report_json)
    sanitized_md = sanitize_value(report_markdown)

    (output_dir / "report.sanitized.json").write_text(json.dumps(sanitized_json, indent=2))
    (output_dir / "report.sanitized.md").write_text(sanitized_md)

    sanitized_lines = []
    for line in audit_path.read_text().splitlines():
        if not line.strip():
            continue
        sanitized_lines.append(json.dumps(sanitize_value(json.loads(line))))
    (output_dir / "audit.sanitized.jsonl").write_text("\n".join(sanitized_lines) + "\n")
