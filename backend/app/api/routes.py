import time
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.database import get_db
from backend.app.db import crud
from backend.app.schemas.document import (
    DocumentType,
    ProcessingStatus,
    DocumentProcessResponse,
    DocumentListResponse,
    DocumentSummaryResponse,
    ProcessingMetadata,
    ExtractedData,
    FileValidationResult
)
from backend.app.schemas.validation import DocumentValidationSummary, ValidationStatus
from backend.app.services.file_validator import validate_and_inspect_file, compute_file_hash
from backend.app.services.ocr_engine import extract_pages_as_images_and_text
from backend.app.services.ai_extractor import (
    extract_document_with_ai,
    process_invoice_document,
    process_cash_flow_document,
    process_balance_sheet_document,
    process_profit_and_loss_document
)
from backend.app.services.financial_validator import perform_financial_validation

def utc_now():
    return datetime.now(timezone.utc)

router = APIRouter()

@router.get("/health", tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint to verify backend operational readiness and DB connectivity."""
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "timestamp": utc_now().isoformat(),
        "version": settings.VERSION,
        "database": db_status,
        "services": {
            "file_validator": "active",
            "ocr_engine": "active (PyMuPDF)",
            "ai_engine": "active (Gemini/Vision + Schema Parser)",
            "financial_validator": "active"
        }
    }

@router.post("/documents/process", response_model=DocumentProcessResponse, status_code=status.HTTP_200_OK, tags=["Documents"])
async def process_document(
    file: UploadFile = File(..., description="PDF, JPG, or PNG document file up to 3 pages"),
    document_type: DocumentType = Form(..., description="Type of financial document"),
    db: Session = Depends(get_db)
):
    """
    Upload and process a financial document (Invoice, Balance Sheet, P&L, Cash Flow).
    Performs file integrity validation, OCR/Vision extraction, AI schema extraction,
    deterministic financial calculations, and saves the result to persistent database storage.
    """
    start_time = time.time()
    filename = file.filename or "uploaded_document"
    logger.info(f"Received document processing request for '{filename}' with type '{document_type.value}'")

    try:
        file_content = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to read uploaded file content: {str(e)}"
        )

    # 1. File & Page Validation
    is_valid, file_val_result = validate_and_inspect_file(
        filename=filename,
        content=file_content,
        content_type=file.content_type
    )

    if not is_valid:
        error_msg = "; ".join(file_val_result.errors)
        logger.warning(f"File validation failed for '{filename}': {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "File validation failed",
                "filename": filename,
                "reasons": file_val_result.errors,
                "file_validation": file_val_result.model_dump()
            }
        )

    file_hash = compute_file_hash(file_content)
    logger.info(f"Processing '{filename}' | Size: {len(file_content)} bytes | SHA256: {file_hash[:12]}... | Type: {document_type.value}")

    # 2. Extract Images & Native Text
    try:
        images, text_by_page = extract_pages_as_images_and_text(file_content, filename)
    except Exception as e:
        logger.error(f"OCR/Image extraction error on '{filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse document pages or images: {str(e)}"
        )

    # 3. Document-Type Routing Handler (strictly driven by user selection)
    try:
        if document_type == DocumentType.INVOICE:
            extracted_data, ocr_engine_name, ai_model_name = await process_invoice_document(
                images=images,
                native_text_by_page=text_by_page,
                filename=filename
            )
        elif document_type == DocumentType.CASH_FLOW_STATEMENT:
            extracted_data, ocr_engine_name, ai_model_name = await process_cash_flow_document(
                images=images,
                native_text_by_page=text_by_page,
                filename=filename
            )
        elif document_type == DocumentType.BALANCE_SHEET:
            extracted_data, ocr_engine_name, ai_model_name = await process_balance_sheet_document(
                images=images,
                native_text_by_page=text_by_page,
                filename=filename
            )
        elif document_type == DocumentType.PROFIT_AND_LOSS:
            extracted_data, ocr_engine_name, ai_model_name = await process_profit_and_loss_document(
                images=images,
                native_text_by_page=text_by_page,
                filename=filename
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported document type: {document_type}"
            )
    except Exception as e:
        logger.error(f"Extraction error on '{filename}' for document type '{document_type.value}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document data extraction error: {str(e)}"
        )


    # 4. Financial Validation Engine
    try:
        validation_summary = perform_financial_validation(document_type, extracted_data)
    except Exception as e:
        logger.error(f"Financial validation exception on '{filename}': {e}")
        validation_summary = DocumentValidationSummary(
            overall_status=ValidationStatus.FAIL,
            passed_count=0,
            failed_count=1,
            not_applicable_count=0,
            total_checks=1,
            checks=[]
        )

    duration_ms = round((time.time() - start_time) * 1000, 2)
    
    # 5. Determine Overall Processing Status
    if validation_summary.overall_status == ValidationStatus.PASS:
        proc_status = ProcessingStatus.VALIDATION_PASSED
    elif validation_summary.overall_status == ValidationStatus.FAIL:
        proc_status = ProcessingStatus.VALIDATION_FAILED
    else:
        proc_status = ProcessingStatus.SUCCESS

    metadata = ProcessingMetadata(
        extracted_at=utc_now(),
        processing_duration_ms=duration_ms,
        ocr_engine=ocr_engine_name,
        ai_model=ai_model_name,
        pages_processed=len(images),
        file_hash=file_hash
    )

    response_data = DocumentProcessResponse(
        document_name=filename,
        document_type=document_type,
        processing_status=proc_status,
        file_validation=file_val_result,
        extracted_data=extracted_data,
        validation=validation_summary,
        processing_metadata=metadata
    )

    # 6. Save to Persistent DB
    try:
        db_doc = crud.create_document_record(db, response_data)
        response_data.id = db_doc.id
        logger.info(f"Persisted '{filename}' as Document #{db_doc.id} | Hash: {file_hash[:12]} | Validation: {validation_summary.overall_status.value}")
    except Exception as e:
        logger.error(f"Failed to persist document to database: {e}")

    return response_data


@router.get("/documents", response_model=DocumentListResponse, tags=["Documents"])
async def list_documents(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    db: Session = Depends(get_db)
):
    """Retrieve list of previously processed documents with summary statistics."""
    total, items = crud.get_all_documents(db, skip=skip, limit=limit, doc_type=document_type)
    
    summary_items = [
        DocumentSummaryResponse(
            id=item.id,
            document_name=item.document_name,
            document_type=DocumentType(item.document_type),
            processing_status=ProcessingStatus(item.processing_status) if item.processing_status in [s.value for s in ProcessingStatus] else ProcessingStatus.SUCCESS,
            created_at=item.created_at,
            page_count=item.page_count,
            validation_status=item.validation_status,
            total_checks=item.total_checks,
            passed_checks=item.passed_checks,
            failed_checks=item.failed_checks
        )
        for item in items
    ]

    return DocumentListResponse(
        total=total,
        items=summary_items
    )

@router.get("/documents/{document_name}", response_model=DocumentProcessResponse, tags=["Documents"])
async def get_document(document_name: str, db: Session = Depends(get_db)):
    """
    Retrieve full details, extracted fields, line items, and financial validation results
    for a specific processed document by filename or ID.
    """
    doc_record = None
    if document_name.isdigit():
        doc_record = crud.get_document_by_id(db, int(document_name))
        
    if not doc_record:
        doc_record = crud.get_document_by_name(db, document_name)

    if not doc_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_name}' was not found in the database."
        )

    return DocumentProcessResponse(
        id=doc_record.id,
        document_name=doc_record.document_name,
        document_type=DocumentType(doc_record.document_type),
        processing_status=ProcessingStatus(doc_record.processing_status) if doc_record.processing_status in [s.value for s in ProcessingStatus] else ProcessingStatus.SUCCESS,
        file_validation=FileValidationResult(**doc_record.file_validation_json),
        extracted_data=ExtractedData(**doc_record.extracted_data_json),
        validation=DocumentValidationSummary(**doc_record.validation_json),
        processing_metadata=ProcessingMetadata(**doc_record.processing_metadata_json)
    )
