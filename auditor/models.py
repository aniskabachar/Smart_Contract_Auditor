from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from openenv.core.env_server.types import (
    Action as OpenEnvAction,
    Observation as OpenEnvObservation,
    State as OpenEnvState,
)

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class VulnerabilityType(str, Enum):
    REENTRANCY = "reentrancy"
    INTEGER_OVERFLOW = "integer_overflow"
    ACCESS_CONTROL = "access_control"
    TX_ORIGIN = "tx_origin"
    TIMESTAMP_DEPENDENCE = "timestamp_dependence"
    SELFDESTRUCT = "selfdestruct"
    UNINITIALIZED_STORAGE = "uninitialized_storage"
    UNCHECKED_CALLS = "unchecked_calls"
    BAD_RANDOMNESS = "bad_randomness"
    DENIAL_OF_SERVICE = "denial_of_service"
    FRONT_RUNNING = "front_running"
    SHORT_ADDRESS = "short_address"
    OTHER = "other"

class DetectedVulnerability(BaseModel):
    type: VulnerabilityType
    location: str
    severity: Severity = Severity.MEDIUM
    explanation: str

class Action(OpenEnvAction):
    vulnerabilities: list[DetectedVulnerability] = Field(default_factory=list)

class Observation(OpenEnvObservation):
    contract_code: str
    task_id: str
    contract_id: str
    task_level: str
    objective: str
    context: str
    attempt_number: int
    allowed_vulnerability_types: list[str]
    info: dict[str, Any] = Field(default_factory=dict)

class AuditorState(OpenEnvState):
    task_id: str | None = None
    contract_id: str | None = None
    difficulty: str | None = None
    done: bool = False
    info: dict[str, Any] = Field(default_factory=dict)

class StepResult(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: dict[str, Any]
