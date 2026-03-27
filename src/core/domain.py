from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    ENUMERATE = "enumerate"
    ANALYZE = "analyze"
    ASSUME_ROLE = "assume_role"
    ACCESS_RESOURCE = "access_resource"


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
    allowed_actions: List[ActionType]
    allowed_resources: List[str]
    max_steps: int = 5
    planner: PlannerConfig | None = None


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


class Observation(BaseModel):
    success: bool
    details: Dict[str, Any] = Field(default_factory=dict)
