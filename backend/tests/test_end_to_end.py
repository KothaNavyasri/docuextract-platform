import os
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "New Dataset 1", "New Dataset")

def test_process_dataset_balance_sheet_if_exists():
    bs_file = os.path.join(SAMPLE_DIR, "Balance Sheet", "Consolidated Balance Sheet 2026.pdf")
    if not os.path.exists(bs_file):
        pytest.skip("Dataset file not found")
        
    with open(bs_file, "rb") as f:
        file_bytes = f.read()
        
    files = {"file": ("Consolidated Balance Sheet 2026.pdf", file_bytes, "application/pdf")}
    data = {"document_type": "balance_sheet"}
    
    response = client.post("/api/v1/documents/process", data=data, files=files)
    assert response.status_code == 200
    res = response.json()
    assert res["document_name"] == "Consolidated Balance Sheet 2026.pdf"
    assert res["file_validation"]["is_valid"] is True
    assert res["file_validation"]["page_count"] == 1

def test_process_dataset_invoice_if_exists():
    inv_file = os.path.join(SAMPLE_DIR, "Invoices", "X00016469619.jpg")
    if not os.path.exists(inv_file):
        pytest.skip("Dataset file not found")
        
    with open(inv_file, "rb") as f:
        file_bytes = f.read()
        
    files = {"file": ("X00016469619.jpg", file_bytes, "image/jpeg")}
    data = {"document_type": "invoice"}
    
    response = client.post("/api/v1/documents/process", data=data, files=files)
    assert response.status_code == 200
    res = response.json()
    assert res["document_name"] == "X00016469619.jpg"
    assert res["file_validation"]["is_valid"] is True
