import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
import pymupdf

from backend.app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "version" in data
    assert "services" in data

def test_openapi_docs_available():
    response_docs = client.get("/docs")
    assert response_docs.status_code == 200
    response_openapi = client.get("/openapi.json")
    assert response_openapi.status_code == 200
    assert "paths" in response_openapi.json()

def test_process_invalid_file_type():
    file_bytes = b"Just plain text not supported"
    files = {"file": ("notes.txt", file_bytes, "text/plain")}
    data = {"document_type": "invoice"}
    response = client.post("/api/v1/documents/process", data=data, files=files)
    assert response.status_code == 400
    assert "File validation failed" in response.json().get("detail", {}).get("error", "")

def test_process_valid_image_document():
    # Create simple in-memory receipt image
    img = Image.new("RGB", (300, 300), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    content = buf.getvalue()
    
    files = {"file": ("test_receipt.png", content, "image/png")}
    data = {"document_type": "invoice"}
    
    response = client.post("/api/v1/documents/process", data=data, files=files)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["document_name"] == "test_receipt.png"
    assert res_json["document_type"] == "invoice"
    assert "file_validation" in res_json
    assert "extracted_data" in res_json
    assert "validation" in res_json
    assert "processing_metadata" in res_json

def test_get_document_list_and_by_name():
    # 1. Process a document
    img = Image.new("RGB", (200, 200), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    content = buf.getvalue()
    
    doc_name = "sample_test_doc_1.png"
    files = {"file": (doc_name, content, "image/png")}
    data = {"document_type": "balance_sheet"}
    
    post_res = client.post("/api/v1/documents/process", data=data, files=files)
    assert post_res.status_code == 200
    
    # 2. Get list of documents
    list_res = client.get("/api/v1/documents")
    assert list_res.status_code == 200
    list_json = list_res.json()
    assert list_json["total"] >= 1
    assert any(item["document_name"] == doc_name for item in list_json["items"])
    
    # 3. Get document by name
    get_res = client.get(f"/api/v1/documents/{doc_name}")
    assert get_res.status_code == 200
    get_json = get_res.json()
    assert get_json["document_name"] == doc_name
    assert get_json["document_type"] == "balance_sheet"

def test_get_nonexistent_document():
    response = client.get("/api/v1/documents/non_existent_file_999.pdf")
    assert response.status_code == 404
