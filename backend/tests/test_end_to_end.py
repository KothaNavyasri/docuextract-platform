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

def test_process_dataset_cash_flow_statement_2018():
    cf_file = os.path.join(SAMPLE_DIR, "Cash Flows", "Consolidated Cash Flow Statement 2018.pdf")
    if not os.path.exists(cf_file):
        pytest.skip("Dataset file not found")
        
    with open(cf_file, "rb") as f:
        file_bytes = f.read()
        
    files = {"file": ("Consolidated Cash Flow Statement 2018.pdf", file_bytes, "application/pdf")}
    data = {"document_type": "cash_flow_statement"}
    
    response = client.post("/api/v1/documents/process", data=data, files=files)
    assert response.status_code == 200
    res = response.json()
    assert res["document_name"] == "Consolidated Cash Flow Statement 2018.pdf"
    assert res["document_type"] == "cash_flow_statement"
    assert res["file_validation"]["is_valid"] is True
    assert res["file_validation"]["page_count"] == 2
    assert "31-Mar-18" in res["extracted_data"]["periods_detected"]
    assert "31-Mar-17" in res["extracted_data"]["periods_detected"]
    assert len(res["extracted_data"]["line_items"]) >= 20
    assert res["validation"]["overall_status"] == "PASS"
    assert res["validation"]["passed_count"] == 4

