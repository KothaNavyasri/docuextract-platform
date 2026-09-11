from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, Float
from backend.app.db.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class DocumentRecord(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_name = Column(String(255), index=True, nullable=False)
    document_type = Column(String(50), index=True, nullable=False)
    processing_status = Column(String(50), nullable=False, default="SUCCESS")
    file_type = Column(String(20), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    page_count = Column(Integer, nullable=False, default=1)
    is_scanned = Column(Boolean, default=False)
    file_hash = Column(String(64), nullable=True)
    
    # Validation summary fields for rapid querying
    validation_status = Column(String(50), nullable=False, default="NOT_APPLICABLE")
    total_checks = Column(Integer, default=0)
    passed_checks = Column(Integer, default=0)
    failed_checks = Column(Integer, default=0)
    
    # Stored JSON payloads
    file_validation_json = Column(JSON, nullable=False)
    extracted_data_json = Column(JSON, nullable=False)
    validation_json = Column(JSON, nullable=False)
    processing_metadata_json = Column(JSON, nullable=False)
    
    created_at = Column(DateTime, default=utc_now, index=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
