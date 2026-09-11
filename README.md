# Intelligent Document Extraction, Validation & API Platform
### AI Engineer Internship Technical Case Study

An end-to-end, production-grade AI platform for multi-format financial document ingestion, multimodal vision OCR, schema extraction with anti-hallucination guardrails, deterministic mathematical reconciliation, persistent relational storage, and interactive web visualization.

---

## 🌟 Solution Overview

The platform automates the extraction and validation of critical financial documents:
1. **Invoices / Receipts**: Line items, quantities, unit prices, subtotal, tax reconciliation, cash paid, and change due.
2. **Balance Sheets**: Period-by-period equality between Total Assets and Total Capital & Liabilities, plus component assets breakdown.
3. **Profit & Loss Statements**: Interest earned, other income, operating expenditures, provisions, PBT, and minority interest attribution.
4. **Cash Flow Statements**: Operating, investing, and financing cash flows, FX translation adjustments, and opening/closing cash continuity (with parenthesized negative handling).

---

## 🏛️ System Architecture

```
User / Evaluator
       │
       ▼
Frontend Web Dashboard (HTML5 / Vanilla CSS / Modern JS)
       │
       ▼  REST API (multipart/form-data)
FastAPI Backend Layer (Swagger / OpenAPI 3.1)
       │
       ├──► 1. File & Page Validator (PDF, JPG, PNG, <= 3 Pages, Integrity Check)
       │
       ├──► 2. OCR / Image Engine (PyMuPDF 200+ DPI Pixmaps & Native Text)
       │
       ├──► 3. Multimodal AI Extraction (Google Gemini Vision 2.5 Flash / Schema Parser)
       │
       ├──► 4. Structured JSON & Anti-Hallucination Parser (Null Enforcement & Evidence Mapping)
       │
       ├──► 5. Financial Validation Engine (Deterministic Mathematical Reconciliations)
       │
       ├──► 6. Persistent Storage (SQLite / PostgreSQL with SQLAlchemy ORM)
       │
       ▼
Dashboard / Client API Response
```

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Backend API** | Python 3.11+, FastAPI, Uvicorn, Pydantic v2 |
| **OCR & Vision** | PyMuPDF (Fitz), Pillow, Google Gemini Vision API (`gemini-2.5-flash`) |
| **Financial Engine** | Deterministic Python Validation Rules with Tolerance Handling |
| **Database** | SQLAlchemy 2.0 ORM, SQLite (file persistence) / PostgreSQL |
| **Frontend UI** | HTML5, Vanilla CSS3 (Custom Properties, Glassmorphism, Dark Mode), Vanilla JS |
| **Testing** | Pytest, FastAPI TestClient, Starlette, AnyIO |
| **Container & Cloud** | Docker, Render / Railway / Vercel deployment configs |

---

## 🚀 Setup & Local Execution

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend server)

### 2. Backend Setup
```bash
# Navigate to project root
cd neo_stats_assessment

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment variables (optional for local testing)
cp .env.example .env

# Run FastAPI backend server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend will be live at `http://127.0.0.1:8000` with interactive Swagger docs at `http://127.0.0.1:8000/docs`.

### 3. Frontend Setup
```bash
# Start frontend server
cd frontend
node server.js
```
The frontend dashboard will be available at `http://localhost:3000`.

---

## 🔑 Environment Variables

| Variable | Description | Default |
|---|---|---|
| `HOST` | Backend host address | `0.0.0.0` |
| `PORT` | Backend listening port | `8000` |
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///./documents.db` |
| `GEMINI_API_KEY` | Google Gemini Vision API Key | Optional (falls back to native parser) |
| `GEMINI_MODEL` | Gemini Model Identifier | `gemini-2.5-flash` |
| `MAX_PAGES` | Maximum allowed document pages | `3` |

---

## 📡 API Endpoints Reference

### 1. `GET /api/v1/health`
Checks backend readiness, database connection, and subsystem statuses.

### 2. `POST /api/v1/documents/process`
Ingests document and executes end-to-end extraction and validation.
- **Content-Type**: `multipart/form-data`
- **Form Parameters**:
  - `file`: PDF, JPG, or PNG document (up to 3 pages)
  - `document_type`: `invoice`, `balance_sheet`, `profit_and_loss`, or `cash_flow_statement`

### 3. `GET /api/v1/documents`
Lists all processed documents with pagination (`skip`, `limit`) and type filtering.

### 4. `GET /api/v1/documents/{document_name}`
Retrieves full extracted entities, tables, formula cards, and raw JSON by filename or database ID.

---

## 💡 Financial Validation Logic

### 1. Invoices
- $\text{Line Total} \approx \text{Quantity} \times \text{Unit Price}$ (evaluated per line)
- $\text{Subtotal} \approx \sum \text{Line Totals}$
- $\text{Taxable Amount} + \text{Total Tax} \approx \text{Total Amount}$
- $\text{Cash Paid} - \text{Total Amount} \approx \text{Change Due}$

### 2. Balance Sheets
- $\text{Total Capital \& Liabilities} \approx \text{Total Assets}$ (evaluated independently per comparative year)
- $\text{Current Assets} + \text{Non-Current Assets} \approx \text{Total Assets}$

### 3. Profit & Loss Statements
- $\text{Interest Earned} + \text{Other Income} \approx \text{Total Income}$
- $\text{Interest Expended} + \text{Operating Expenses} + \text{Provisions} \approx \text{Total Expenditure}$
- $\text{Total Income} - \text{Total Expenditure} \approx \text{Net Profit before Minority Interest}$
- $\text{Net Profit before Minority Interest} - \text{Minority Interest} \approx \text{Consolidated Net Profit}$

### 4. Cash Flow Statements
- $\text{Operating Cash} + \text{Investing Cash} + \text{Financing Cash} + \text{FX} \approx \text{Net Increase in Cash}$
- $\text{Opening Cash} + \text{Net Increase in Cash} + \text{Adjustments} \approx \text{Closing Cash}$
- Parenthesized accounting values e.g. `(45,000)` are parsed as `-45000.0`. Missing operands return `NOT_APPLICABLE`.

---

## 🧪 Testing

Run the automated test suite covering 21 validation, file integrity, and endpoint tests:
```bash
python -m pytest backend/tests/ -v
```

---

## 📦 Deliverables & Documentation

- **Architecture Documentation**: [`docs/architecture.md`](docs/architecture.md)
- **Technical Presentation (18 Slides)**: [`docs/presentation.pptx`](docs/presentation.pptx)
- **Sample JSON Outputs**:
  - [`sample_outputs/invoice_sample.json`](sample_outputs/invoice_sample.json)
  - [`sample_outputs/balance_sheet_sample.json`](sample_outputs/balance_sheet_sample.json)
  - [`sample_outputs/profit_loss_sample.json`](sample_outputs/profit_loss_sample.json)
  - [`sample_outputs/cash_flow_sample.json`](sample_outputs/cash_flow_sample.json)

---

## 🤖 AI Coding Assistant Usage Declaration

This project was engineered and structured in collaboration with Antigravity AI, utilizing Google Gemini models for architectural design, schema modeling, test automation, and code generation.
