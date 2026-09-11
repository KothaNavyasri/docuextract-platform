import io
import hashlib
from typing import Tuple, Optional
import pymupdf
from PIL import Image

from backend.app.core.config import settings
from backend.app.schemas.document import FileValidationResult
from backend.app.core.logging import logger

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/octet-stream"  # sometimes sent by browsers for binary
}

def validate_and_inspect_file(filename: str, content: bytes, content_type: Optional[str] = None) -> Tuple[bool, FileValidationResult]:
    errors = []
    file_size = len(content)
    
    # 1. Empty file check
    if file_size == 0:
        errors.append("File is empty (0 bytes).")
        return False, FileValidationResult(
            is_valid=False,
            filename=filename,
            file_type="unknown",
            file_size_bytes=0,
            page_count=0,
            is_scanned=False,
            errors=errors
        )
    
    # 2. File size max limit check
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        errors.append(f"File size ({file_size / (1024*1024):.2f}MB) exceeds maximum limit of {settings.MAX_FILE_SIZE_MB}MB.")
    
    # 3. Extension check
    ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"Unsupported file extension '{ext}'. Only .pdf, .jpg, .jpeg, and .png are allowed.")
        return False, FileValidationResult(
            is_valid=False,
            filename=filename,
            file_type=ext.lstrip(".") or "unknown",
            file_size_bytes=file_size,
            page_count=0,
            is_scanned=False,
            errors=errors
        )
    
    page_count = 1
    is_scanned = False
    
    # 4. Deep format & integrity inspection
    if ext == ".pdf":
        try:
            pdf_doc = pymupdf.open(stream=content, filetype="pdf")
            page_count = len(pdf_doc)
            
            if page_count == 0:
                errors.append("PDF document contains no pages.")
            elif page_count > settings.MAX_PAGES:
                errors.append(f"Document contains {page_count} pages, which exceeds the maximum allowed limit of {settings.MAX_PAGES} pages.")
            
            # Check if native or scanned
            has_native_text = False
            for page in pdf_doc:
                text = page.get_text()
                if text and len(text.strip()) > 30:
                    has_native_text = True
                    break
            is_scanned = not has_native_text
            pdf_doc.close()
        except Exception as e:
            errors.append(f"Corrupted or invalid PDF file: {str(e)}")
            logger.error(f"Failed to parse PDF file '{filename}': {str(e)}")
    else:
        # Image file validation
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()  # verify integrity
            # Reopen for mode check since verify closes/invalidates img stream
            img = Image.open(io.BytesIO(content))
            page_count = 1
            is_scanned = True
        except Exception as e:
            errors.append(f"Corrupted or invalid image file: {str(e)}")
            logger.error(f"Failed to parse image file '{filename}': {str(e)}")
            
    is_valid = len(errors) == 0
    file_type = "pdf" if ext == ".pdf" else "image"
    
    result = FileValidationResult(
        is_valid=is_valid,
        filename=filename,
        file_type=file_type,
        file_size_bytes=file_size,
        page_count=page_count,
        is_scanned=is_scanned,
        errors=errors
    )
    return is_valid, result

def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
