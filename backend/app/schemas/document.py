from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from datetime import datetime, timezone
from backend.app.schemas.validation import DocumentValidationSummary

def utc_now():
    return datetime.now(timezone.utc)

class DocumentType(str, Enum):
    INVOICE = "invoice"
    BALANCE_SHEET = "balance_sheet"
    PROFIT_AND_LOSS = "profit_and_loss"
    CASH_FLOW_STATEMENT = "cash_flow_statement"

class ProcessingStatus(str, Enum):
    SUCCESS = "SUCCESS"
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    FAILED = "FAILED"

class FileValidationResult(BaseModel):
    is_valid: bool
    filename: str
    file_type: str
    file_size_bytes: int
    page_count: int
    is_scanned: bool
    errors: List[str] = Field(default_factory=list)

class ExtractedField(BaseModel):
    value: Optional[Any] = None
    confidence: Optional[float] = None
    source_text: Optional[str] = None
    page_number: Optional[int] = None
    is_missing: bool = False

class LineItem(BaseModel):
    label: Optional[str] = None
    item_description: Optional[str] = None
    values: Optional[Dict[str, Optional[float]]] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    tax_rate: Optional[float] = None
    raw_text: Optional[str] = None
    evidence: Optional[str] = None
    page_number: Optional[int] = 1
    confidence: Optional[float] = 0.95


class ExtractedData(BaseModel):
    statement_title: Optional[str] = None
    reporting_period: Optional[str] = None
    summary_fields: Dict[str, Union[ExtractedField, Any]] = Field(default_factory=dict)
    tables: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(default_factory=dict)
    line_items: Optional[List[LineItem]] = None
    raw_text_by_page: Dict[str, str] = Field(default_factory=dict)
    periods_detected: Optional[List[str]] = Field(default_factory=list)
    currency: Optional[str] = "INR"
    unit: Optional[str] = None
    notes: Optional[List[str]] = Field(default_factory=list)

class ProcessingMetadata(BaseModel):
    extracted_at: datetime = Field(default_factory=utc_now)
    processing_duration_ms: float
    ocr_engine: str
    ai_model: str
    pages_processed: int
    file_hash: Optional[str] = None

class DocumentProcessResponse(BaseModel):
    id: Optional[int] = None
    document_name: str
    document_type: DocumentType
    processing_status: ProcessingStatus
    file_validation: FileValidationResult
    extracted_data: ExtractedData
    validation: DocumentValidationSummary
    processing_metadata: ProcessingMetadata

class DocumentSummaryResponse(BaseModel):
    id: int
    document_name: str
    document_type: DocumentType
    processing_status: ProcessingStatus
    created_at: datetime
    page_count: int
    validation_status: str
    total_checks: int
    passed_checks: int
    failed_checks: int

class DocumentListResponse(BaseModel):
    total: int
    items: List[DocumentSummaryResponse]
