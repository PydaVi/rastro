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


class AuthorizationConfig(BaseModel):
    authorized_by: str
    authorized_at: str
    authorization_document: str
    permitted_profiles: list[str] = Field(default_factory=list)
    excluded_profiles: list[str] = Field(default_factory=list)


class ProfileDefinition(BaseModel):
    name: str
    bundle: str
    description: str
    fixture_path: Path
    objective_path: Path
    scope_path: Path


class CampaignResult(BaseModel):
    profile: str
    output_dir: Path
    objective_met: bool
    report_json: Path
    report_md: Path


class AssessmentResult(BaseModel):
    bundle: str
    target: str
    campaigns: list[CampaignResult]
