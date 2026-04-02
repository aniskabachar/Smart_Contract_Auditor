from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

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

class DetectedVulnerability(BaseModel):
    type: VulnerabilityType
    location: str
    severity: Severity
    explanation: str

class Action(BaseModel):
    vulnerabilities: List[DetectedVulnerability]

class Observation(BaseModel):
    contract_code: str
    task_level: str
    context: str
    attempt_number: int

class StepResult(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: dict