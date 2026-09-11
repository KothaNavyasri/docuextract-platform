import io
import pytest
import pymupdf
from PIL import Image
from backend.app.services.file_validator import validate_and_inspect_file

def test_empty_file_rejected():
    is_valid, res = validate_and_inspect_file("empty.pdf", b"")
    assert not is_valid
    assert "File is empty" in res.errors[0]

def test_unsupported_file_extension():
    is_valid, res = validate_and_inspect_file("malicious.exe", b"fake binary content")
    assert not is_valid
    assert "Unsupported file extension" in res.errors[0]

def test_corrupted_pdf_rejected():
    is_valid, res = validate_and_inspect_file("corrupt.pdf", b"%PDF-1.4 completely broken content not a real pdf")
    assert not is_valid
    assert any("Corrupted or invalid PDF" in err for err in res.errors)

def test_valid_image_accepted():
    img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    content = buf.getvalue()
    
    is_valid, res = validate_and_inspect_file("test_receipt.png", content)
    assert is_valid
    assert res.file_type == "image"
    assert res.page_count == 1
    assert res.is_scanned is True

def test_pdf_page_limit_enforced():
    # Create 4-page PDF in memory
    doc = pymupdf.open()
    for i in range(4):
        doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    
    is_valid, res = validate_and_inspect_file("too_many_pages.pdf", pdf_bytes)
    assert not is_valid
    assert res.page_count == 4
    assert any("exceeds the maximum allowed limit of 3 pages" in err for err in res.errors)

def test_valid_multi_page_pdf_accepted():
    doc = pymupdf.open()
    for i in range(2):
        doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    
    is_valid, res = validate_and_inspect_file("valid_doc.pdf", pdf_bytes)
    assert is_valid
    assert res.page_count == 2
