from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class TargetConfig(BaseModel):
    name: str
    platform: Literal["aws"] = "aws"
    accounts: list[str] = Field(default_factory=list)
    allowed_regions: list[str] = Field(default_factory=list)
    entry_roles: list[str] = Field(default_factory=list)
    discovery_ssm_prefixes: list[str] = Field(default_factory=list)
    # Maps identity ARN -> AWS named profile for campaign execution.
    # Discovery always uses the default profile (admin user).
    entry_credential_profiles: dict[str, str] = Field(default_factory=dict)


class AuthorizationConfig(BaseModel):
    authorized_by: str
    authorized_at: str
    authorization_document: str
    permitted_profiles: list[str] = Field(default_factory=list)
    excluded_profiles: list[str] = Field(default_factory=list)
    planner_config: dict | None = None
    # If set, only these entry identity ARNs will be used for campaign generation.
    permitted_entry_identities: list[str] = Field(default_factory=list)
    # Per-profile override: maps profile name -> list of entry identity ARNs.
    # When set for a profile, overrides permitted_entry_identities for that profile.
    profile_entry_identities: dict[str, list[str]] = Field(default_factory=dict)


class ProfileDefinition(BaseModel):
    name: str
    bundle: str
    description: str
    fixture_path: Path
    objective_path: Path
    scope_path: Path
    discovery_ssm_prefixes: list[str] = Field(default_factory=list)


class CampaignResult(BaseModel):
    status: Literal["passed", "objective_not_met", "preflight_failed", "run_failed"]
    campaign_id: str | None = None
    profile: str
    output_dir: Path
    generated_scope: Path
    objective_met: bool
    preflight_ok: bool = True
    preflight_details: dict = Field(default_factory=dict)
    error: str | None = None
    report_json: Path | None = None
    report_md: Path | None = None


class AssessmentFinding(BaseModel):
    id: str
    title: str
    profile: str
    severity: str
    confidence: str
    status: Literal["validated", "observed"] = "validated"
    finding_state: Literal["observed", "reachable", "credentialed", "exploited", "validated_impact"] = "observed"
    target_resource: str
    entry_point: str | None = None
    entry_points: list[str] = Field(default_factory=list)
    principal_multiplicity: int = 1
    distinct_path_key: str = ""
    path_summary: str = ""
    services_involved: list[str] = Field(default_factory=list)
    evidence_summary: str = ""
    evidence_level: Literal["proved", "observed"] = "proved"
    proof_mode: Literal["real", "simulation", "structural"] = "structural"
    mitre_techniques: list[str] = Field(default_factory=list)


class AssessmentResult(BaseModel):
    bundle: str
    target: str
    summary: dict = Field(default_factory=dict)
    artifacts: dict = Field(default_factory=dict)
    findings: list[AssessmentFinding] = Field(default_factory=list)
    campaigns: list[CampaignResult]
