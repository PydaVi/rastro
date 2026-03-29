from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ACCOUNT_ID_RE = re.compile(r"\b\d{12}\b")
IAM_USER_ARN_RE = re.compile(r"arn:aws:iam::\d{12}:user/[^\s'\"]+")
IAM_ROLE_ARN_RE = re.compile(r"arn:aws:iam::\d{12}:role/[^\s'\"]+")
STS_ASSUMED_ROLE_ARN_RE = re.compile(r"arn:aws:sts::\d{12}:assumed-role/([^/\s'\"]+)/([^\s'\"]+)")
S3_ARN_RE = re.compile(r"arn:aws:s3:::[^/\s'\"]+/[^\s'\"]+")
S3_URI_RE = re.compile(r"s3://[^/\s'\"]+/[^\s'\"]+")
IAM_USER_PATH_RE = re.compile(r":user/([^\s'\"]+)")
IAM_ROLE_PATH_RE = re.compile(r":role/([^\s'\"]+)")
STS_ROLE_PATH_RE = re.compile(r":assumed-role/([^/\s'\"]+)/([^\s'\"]+)")
S3_PATH_RE = re.compile(r"arn:aws:s3:::([^/\s'\"]+)/([^\s'\"]+)")
S3_URI_PATH_RE = re.compile(r"s3://([^/\s'\"]+)/([^\s'\"]+)")
ROOT_LITERAL_RE = re.compile(r"\broot\b")


class SanitizerContext:
    def __init__(self) -> None:
        self.role_map: dict[str, str] = {}
        self.user_map: dict[str, str] = {}
        self.session_map: dict[str, str] = {}
        self.bucket_map: dict[str, str] = {}
        self.object_key_map: dict[str, str] = {}

    def role_alias(self, value: str) -> str:
        return self._alias(self.role_map, value, "<REDACTED_ROLE>")

    def user_alias(self, value: str) -> str:
        return self._alias(self.user_map, value, "<REDACTED_USER>")

    def session_alias(self, value: str) -> str:
        return self._alias(self.session_map, value, "<REDACTED_SESSION>")

    def bucket_alias(self, value: str) -> str:
        return self._alias(self.bucket_map, value, "<REDACTED_BUCKET>")

    def object_key_alias(self, value: str) -> str:
        return self._alias(self.object_key_map, value, "<REDACTED_OBJECT_KEY>")

    @staticmethod
    def _alias(mapping: dict[str, str], value: str, prefix: str) -> str:
        if value not in mapping:
            suffix = "" if not mapping else f"_{len(mapping) + 1}"
            mapping[value] = f"{prefix}{suffix}"
        return mapping[value]


def sanitize_value(
    value: Any,
    field_name: str | None = None,
    context: SanitizerContext | None = None,
) -> Any:
    context = context or SanitizerContext()

    if isinstance(value, dict):
        return {k: sanitize_value(v, k, context) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_value(item, field_name, context) for item in value]
    if isinstance(value, str):
        if field_name == "bucket":
            return context.bucket_alias(value)
        if field_name == "object_key":
            return context.object_key_alias(value)
        if field_name == "preview":
            return "<REDACTED_CONTENT_PREVIEW>"
        if field_name == "authorization_document":
            return value
        return _sanitize_string(value, context)
    return value


def _sanitize_string(value: str, context: SanitizerContext) -> str:
    def replace_sts(match: re.Match[str]) -> str:
        role_name = match.group(1)
        session_name = match.group(2)
        return (
            "arn:aws:sts::<AWS_ACCOUNT_ID>:assumed-role/"
            f"{context.role_alias(role_name)}/{context.session_alias(session_name)}"
        )

    def replace_user_arn(match: re.Match[str]) -> str:
        name_match = IAM_USER_PATH_RE.search(match.group(0))
        user_name = name_match.group(1) if name_match else "user"
        return f"arn:aws:iam::<AWS_ACCOUNT_ID>:user/{context.user_alias(user_name)}"

    def replace_role_arn(match: re.Match[str]) -> str:
        name_match = IAM_ROLE_PATH_RE.search(match.group(0))
        role_name = name_match.group(1) if name_match else "role"
        return f"arn:aws:iam::<AWS_ACCOUNT_ID>:role/{context.role_alias(role_name)}"

    def replace_s3_arn(match: re.Match[str]) -> str:
        bucket_name, object_key = S3_PATH_RE.match(match.group(0)).groups()
        return (
            f"arn:aws:s3:::{context.bucket_alias(bucket_name)}/"
            f"{context.object_key_alias(object_key)}"
        )

    def replace_s3_uri(match: re.Match[str]) -> str:
        bucket_name, object_key = S3_URI_PATH_RE.match(match.group(0)).groups()
        return f"s3://{context.bucket_alias(bucket_name)}/{context.object_key_alias(object_key)}"

    value = STS_ASSUMED_ROLE_ARN_RE.sub(replace_sts, value)
    value = IAM_USER_ARN_RE.sub(replace_user_arn, value)
    value = IAM_ROLE_ARN_RE.sub(replace_role_arn, value)
    value = S3_ARN_RE.sub(replace_s3_arn, value)
    value = S3_URI_RE.sub(replace_s3_uri, value)
    value = ACCOUNT_ID_RE.sub("<AWS_ACCOUNT_ID>", value)

    for original, alias in sorted(context.role_map.items(), key=lambda item: len(item[0]), reverse=True):
        value = re.sub(rf"\b{re.escape(original)}\b", alias, value)
    for original, alias in sorted(context.user_map.items(), key=lambda item: len(item[0]), reverse=True):
        value = re.sub(rf"\b{re.escape(original)}\b", alias, value)
    for original, alias in sorted(context.session_map.items(), key=lambda item: len(item[0]), reverse=True):
        value = re.sub(rf"\b{re.escape(original)}\b", alias, value)
    for original, alias in sorted(context.bucket_map.items(), key=lambda item: len(item[0]), reverse=True):
        value = re.sub(rf"\b{re.escape(original)}\b", alias, value)
    for original, alias in sorted(context.object_key_map.items(), key=lambda item: len(item[0]), reverse=True):
        value = re.sub(rf"\b{re.escape(original)}\b", alias, value)

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

    context = SanitizerContext()
    sanitized_json = sanitize_value(report_json, context=context)
    sanitized_md = sanitize_value(report_markdown, context=context)

    (output_dir / "report.sanitized.json").write_text(json.dumps(sanitized_json, indent=2))
    (output_dir / "report.sanitized.md").write_text(sanitized_md)

    sanitized_lines = []
    for line in audit_path.read_text().splitlines():
        if not line.strip():
            continue
        sanitized_lines.append(json.dumps(sanitize_value(json.loads(line), context=context)))
    (output_dir / "audit.sanitized.jsonl").write_text("\n".join(sanitized_lines) + "\n")
