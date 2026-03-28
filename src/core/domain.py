from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ActionType(str, Enum):
    ENUMERATE = "enumerate"
    ANALYZE = "analyze"
    ASSUME_ROLE = "assume_role"
    ACCESS_RESOURCE = "access_resource"


class TargetType(str, Enum):
    FIXTURE = "fixture"
    AWS = "aws"


class Technique(BaseModel):
    mitre_id: str
    mitre_name: str
    tactic: str
    platform: str


class Objective(BaseModel):
    description: str
    target: str
    success_criteria: Dict[str, Any]


class PlannerConfig(BaseModel):
    backend: str = "mock"
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    timeout: Optional[int] = None


class Scope(BaseModel):
    target: TargetType = TargetType.FIXTURE
    allowed_actions: List[ActionType]
    allowed_resources: List[str]
    max_steps: int = 5
    planner: PlannerConfig | None = None
    dry_run: bool = False
    aws_account_ids: List[str] = Field(default_factory=list)
    allowed_regions: List[str] = Field(default_factory=list)
    allowed_services: List[str] = Field(default_factory=list)
    authorized_by: Optional[str] = None
    authorized_at: Optional[str] = None
    authorization_document: Optional[str] = None

    @model_validator(mode="after")
    def validate_target_requirements(self) -> "Scope":
        if self.target == TargetType.AWS:
            if not self.dry_run:
                raise ValueError("AWS target currently requires dry_run=true.")
            required_lists = [
                ("aws_account_ids", self.aws_account_ids),
                ("allowed_regions", self.allowed_regions),
                ("allowed_services", self.allowed_services),
            ]
            for name, value in required_lists:
                if not value:
                    raise ValueError(f"AWS target requires {name}.")
            required_strings = [
                ("authorized_by", self.authorized_by),
                ("authorized_at", self.authorized_at),
                ("authorization_document", self.authorization_document),
            ]
            for name, value in required_strings:
                if not value:
                    raise ValueError(f"AWS target requires {name}.")
        return self


class Action(BaseModel):
    action_type: ActionType
    actor: str
    target: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    technique: Technique | None = None
    tool: Optional[str] = None


class Decision(BaseModel):
    action: Action
    reason: str
    planner_metadata: Dict[str, Any] = Field(default_factory=dict)


class Observation(BaseModel):
    success: bool
    details: Dict[str, Any] = Field(default_factory=dict)
