from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.app.db.models import DocumentRecord
from backend.app.schemas.document import DocumentProcessResponse, DocumentType, ProcessingStatus

def create_document_record(db: Session, doc_data: DocumentProcessResponse) -> DocumentRecord:
    db_doc = DocumentRecord(
        document_name=doc_data.document_name,
        document_type=doc_data.document_type.value if hasattr(doc_data.document_type, "value") else str(doc_data.document_type),
        processing_status=doc_data.processing_status.value if hasattr(doc_data.processing_status, "value") else str(doc_data.processing_status),
        file_type=doc_data.file_validation.file_type,
        file_size_bytes=doc_data.file_validation.file_size_bytes,
        page_count=doc_data.file_validation.page_count,
        is_scanned=doc_data.file_validation.is_scanned,
        file_hash=doc_data.processing_metadata.file_hash,
        validation_status=doc_data.validation.overall_status.value if hasattr(doc_data.validation.overall_status, "value") else str(doc_data.validation.overall_status),
        total_checks=doc_data.validation.total_checks,
        passed_checks=doc_data.validation.passed_count,
        failed_checks=doc_data.validation.failed_count,
        file_validation_json=doc_data.file_validation.model_dump(),
        extracted_data_json=doc_data.extracted_data.model_dump(),
        validation_json=doc_data.validation.model_dump(),
        processing_metadata_json=doc_data.processing_metadata.model_dump(mode="json"),
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return db_doc

def get_document_by_name(db: Session, document_name: str) -> Optional[DocumentRecord]:
    return db.query(DocumentRecord).filter(DocumentRecord.document_name == document_name).order_by(desc(DocumentRecord.created_at)).first()

def get_document_by_id(db: Session, doc_id: int) -> Optional[DocumentRecord]:
    return db.query(DocumentRecord).filter(DocumentRecord.id == doc_id).first()

def get_all_documents(db: Session, skip: int = 0, limit: int = 100, doc_type: Optional[str] = None) -> Tuple[int, List[DocumentRecord]]:
    query = db.query(DocumentRecord)
    if doc_type:
        query = query.filter(DocumentRecord.document_type == doc_type)
    total = query.count()
    items = query.order_by(desc(DocumentRecord.created_at)).offset(skip).limit(limit).all()
    return total, items
