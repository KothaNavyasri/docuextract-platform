from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum

class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class ValidationCheck(BaseModel):
    check_id: str
    formula_name: str
    formula_description: str
    operands: Dict[str, Any] = Field(default_factory=dict)
    calculated_value: Optional[float] = None
    reported_value: Optional[float] = None
    variance: Optional[float] = None
    status: ValidationStatus
    tolerance: float = 0.05
    explanation: str

class DocumentValidationSummary(BaseModel):
    overall_status: ValidationStatus
    passed_count: int = 0
    failed_count: int = 0
    not_applicable_count: int = 0
    total_checks: int = 0
    checks: List[ValidationCheck] = Field(default_factory=list)
