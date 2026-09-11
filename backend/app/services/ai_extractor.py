import json
import re
from typing import Dict, Any, List, Optional
from PIL import Image
import google.generativeai as genai

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.schemas.document import DocumentType, ExtractedData, LineItem, ExtractedField

DOCUMENT_PROMPTS = {
    DocumentType.INVOICE: """
You are a high-precision Financial Document AI specialized in Invoices and Receipts.
Analyze the provided document image(s) and extract ALL visible structured financial data.

CRITICAL INSTRUCTIONS:
1. Extract ALL visible header information, line items, totals, payment details, and tax breakdowns.
2. DO NOT HALLUCINATE OR GUESS. If a field or value is missing, unclear, or unreadable, set its value to null and is_missing to true.
3. For each summary field, provide:
   - "value": extracted numeric or string value (convert amounts to standard float numbers where possible, e.g. 1250.50).
   - "confidence": confidence score between 0.0 and 1.0.
   - "source_text": exact text snippet visible on the document.
   - "page_number": page number (1-indexed) where the field was found.
   - "is_missing": boolean (true if missing/null).
4. For all line items in the table, extract:
   - item_description
   - quantity (float or null)
   - unit_price (float or null)
   - line_total (float or null)
   - tax_rate (float or null)
   - raw_text
   - page_number
5. Summary fields to extract if visible (plus any other visible fields in custom_fields):
   - invoice_number
   - invoice_date
   - due_date
   - vendor_name
   - vendor_address
   - customer_name
   - customer_address
   - subtotal (sum of line items before tax/discounts)
   - total_tax_amount
   - tax_rate
   - taxable_amount
   - discount_amount
   - total_amount (final payable invoice total)
   - cash_paid (or amount_paid)
   - change_due (or balance_due)
   - payment_terms
   - currency (e.g. USD, EUR, INR, GBP)

Output ONLY valid JSON matching this structure:
{
  "summary_fields": {
    "invoice_number": {"value": "...", "confidence": 0.99, "source_text": "...", "page_number": 1, "is_missing": false},
    "subtotal": {"value": 100.00, "confidence": 0.95, "source_text": "Subtotal: $100.00", "page_number": 1, "is_missing": false},
    "taxable_amount": {"value": 100.00, "confidence": 0.95, "source_text": "...", "page_number": 1, "is_missing": false},
    "total_tax_amount": {"value": 10.00, "confidence": 0.95, "source_text": "Tax (10%): $10.00", "page_number": 1, "is_missing": false},
    "total_amount": {"value": 110.00, "confidence": 0.98, "source_text": "Total: $110.00", "page_number": 1, "is_missing": false},
    "cash_paid": {"value": 120.00, "confidence": 0.95, "source_text": "Cash Paid: $120.00", "page_number": 1, "is_missing": false},
    "change_due": {"value": 10.00, "confidence": 0.95, "source_text": "Change: $10.00", "page_number": 1, "is_missing": false}
  },
  "line_items": [
    {
      "item_description": "Widget A",
      "quantity": 2.0,
      "unit_price": 50.0,
      "line_total": 100.0,
      "tax_rate": 0.1,
      "raw_text": "2 x Widget A @ $50 = $100",
      "page_number": 1
    }
  ],
  "tables": {
    "line_items": [...]
  },
  "currency": "USD",
  "notes": ["..."]
}
""",

    DocumentType.BALANCE_SHEET: """
You are a high-precision Financial Document AI specialized in Corporate Balance Sheets.
Analyze the provided document image(s) and extract ALL visible balance sheet line items, categories, and totals for each reporting period/year visible (e.g. 2026, 2025, 2024, etc.).

CRITICAL INSTRUCTIONS:
1. Extract values for all comparative columns/periods shown in the document.
2. Parentheses e.g. (1,234) represent negative numbers: -1234.0.
3. DO NOT HALLUCINATE. If a line item or figure is missing or unreadable, set value to null.
4. For each key field, provide value, confidence, source_text, page_number, and is_missing.
5. In tables["balance_sheet"], output the full line-by-line financial statement with columns for each period.
6. Summary fields to extract for the primary/latest period:
   - period_ended (date / year)
   - total_assets
   - total_capital_and_liabilities (or total_equity_and_liabilities)
   - total_current_assets
   - total_non_current_assets
   - total_current_liabilities
   - total_non_current_liabilities
   - total_equity / shareholder_funds
   - share_capital
   - reserves_and_surplus
   - cash_and_bank_balances

Output ONLY valid JSON matching this structure:
{
  "summary_fields": {
    "period_ended": {"value": "March 31, 2026", "confidence": 0.98, "source_text": "As at 31st March 2026", "page_number": 1, "is_missing": false},
    "total_assets": {"value": 5000000.0, "confidence": 0.99, "source_text": "TOTAL ASSETS: 5,000,000", "page_number": 1, "is_missing": false},
    "total_capital_and_liabilities": {"value": 5000000.0, "confidence": 0.99, "source_text": "TOTAL CAPITAL AND LIABILITIES: 5,000,000", "page_number": 1, "is_missing": false}
  },
  "periods_detected": ["2026", "2025"],
  "tables": {
    "balance_sheet_periods": [
      {
        "period": "2026",
        "total_assets": 5000000.0,
        "total_capital_and_liabilities": 5000000.0,
        "current_assets": 2000000.0,
        "non_current_assets": 3000000.0,
        "current_liabilities": 1500000.0,
        "non_current_liabilities": 1500000.0,
        "equity": 2000000.0
      }
    ],
    "full_statement_rows": [
      {
        "particulars": "Cash and Cash Equivalents",
        "schedule": "6",
        "values": {"2026": 500000.0, "2025": 450000.0}
      }
    ]
  },
  "currency": "INR",
  "notes": []
}
""",

    DocumentType.PROFIT_AND_LOSS: """
You are a high-precision Financial Document AI specialized in Profit & Loss / Income Statements (including banking/corporate formats).
Analyze the provided document image(s) and extract ALL visible income, expenditure, and profit line items.

CRITICAL INSTRUCTIONS:
1. Extract values for all comparative columns/periods shown in the document.
2. Parentheses e.g. (1,234) represent negative numbers: -1234.0.
3. DO NOT HALLUCINATE.
4. Summary fields to extract for the primary/latest period:
   - period_ended (date / year)
   - interest_earned
   - other_income
   - total_income
   - interest_expended
   - operating_expenses
   - provisions_and_contingencies
   - total_expenditure
   - net_profit_before_minority_interest (or operating profit / profit before tax)
   - minority_interest
   - net_profit_attributable_to_group (or consolidated net profit for the year)
   - earnings_per_share

Output ONLY valid JSON matching this structure:
{
  "summary_fields": {
    "interest_earned": {"value": 150000.0, "confidence": 0.98, "source_text": "Interest Earned: 150,000", "page_number": 1, "is_missing": false},
    "other_income": {"value": 50000.0, "confidence": 0.98, "source_text": "Other Income: 50,000", "page_number": 1, "is_missing": false},
    "total_income": {"value": 200000.0, "confidence": 0.99, "source_text": "TOTAL INCOME: 200,000", "page_number": 1, "is_missing": false},
    "interest_expended": {"value": 80000.0, "confidence": 0.98, "source_text": "Interest Expended: 80,000", "page_number": 1, "is_missing": false},
    "operating_expenses": {"value": 40000.0, "confidence": 0.98, "source_text": "Operating Expenses: 40,000", "page_number": 1, "is_missing": false},
    "provisions_and_contingencies": {"value": 20000.0, "confidence": 0.98, "source_text": "Provisions: 20,000", "page_number": 1, "is_missing": false},
    "total_expenditure": {"value": 140000.0, "confidence": 0.99, "source_text": "TOTAL EXPENDITURE: 140,000", "page_number": 1, "is_missing": false},
    "net_profit_before_minority_interest": {"value": 60000.0, "confidence": 0.98, "source_text": "Net Profit before Minority Interest: 60,000", "page_number": 1, "is_missing": false},
    "minority_interest": {"value": 5000.0, "confidence": 0.98, "source_text": "Minority Interest: 5,000", "page_number": 1, "is_missing": false},
    "net_profit_attributable_to_group": {"value": 55000.0, "confidence": 0.99, "source_text": "Net Profit attributable to Group: 55,000", "page_number": 1, "is_missing": false}
  },
  "periods_detected": ["2026", "2025"],
  "tables": {
    "pnl_periods": [
      {
        "period": "2026",
        "interest_earned": 150000.0,
        "other_income": 50000.0,
        "total_income": 200000.0,
        "interest_expended": 80000.0,
        "operating_expenses": 40000.0,
        "provisions_and_contingencies": 20000.0,
        "total_expenditure": 140000.0,
        "net_profit_before_minority_interest": 60000.0,
        "minority_interest": 5000.0,
        "net_profit_attributable_to_group": 55000.0
      }
    ],
    "full_statement_rows": []
  },
  "currency": "INR",
  "notes": []
}
""",

    DocumentType.CASH_FLOW_STATEMENT: """
You are a high-precision Financial Document AI specialized in Cash Flow Statements.
Analyze the provided document image(s) and extract ALL visible cash flow activities and opening/closing cash positions.

CRITICAL INSTRUCTIONS:
1. Treat parenthesized figures (e.g. `(45,000)`) as negative numbers (`-45000.0`).
2. DO NOT HALLUCINATE OR GUESS. If a field is not present, set value to null.
3. Summary fields to extract for the primary/latest period:
   - period_ended (date / year)
   - operating_cash_flow (Net cash generated from / used in operating activities)
   - investing_cash_flow (Net cash generated from / used in investing activities)
   - financing_cash_flow (Net cash generated from / used in financing activities)
   - foreign_exchange_adjustment (Effect of exchange rate changes / translation adjustments)
   - net_increase_in_cash (Net increase / decrease in cash and cash equivalents)
   - opening_cash_balance (Cash and cash equivalents at beginning of year / period)
   - closing_cash_balance (Cash and cash equivalents at end of year / period)
   - other_adjustments (Cash and cash equivalents acquired in amalgamation / business combinations etc.)

Output ONLY valid JSON matching this structure:
{
  "summary_fields": {
    "operating_cash_flow": {"value": 120000.0, "confidence": 0.98, "source_text": "Net Cash from Operating Activities: 120,000", "page_number": 1, "is_missing": false},
    "investing_cash_flow": {"value": -50000.0, "confidence": 0.98, "source_text": "Net Cash used in Investing Activities: (50,000)", "page_number": 1, "is_missing": false},
    "financing_cash_flow": {"value": -30000.0, "confidence": 0.98, "source_text": "Net Cash used in Financing Activities: (30,000)", "page_number": 2, "is_missing": false},
    "foreign_exchange_adjustment": {"value": 0.0, "confidence": 0.90, "source_text": "FX Adjustment: 0", "page_number": 2, "is_missing": false},
    "net_increase_in_cash": {"value": 40000.0, "confidence": 0.99, "source_text": "Net Increase in Cash: 40,000", "page_number": 2, "is_missing": false},
    "opening_cash_balance": {"value": 100000.0, "confidence": 0.98, "source_text": "Cash at Beginning of Year: 100,000", "page_number": 2, "is_missing": false},
    "closing_cash_balance": {"value": 140000.0, "confidence": 0.99, "source_text": "Cash at End of Year: 140,000", "page_number": 2, "is_missing": false}
  },
  "periods_detected": ["2026", "2025"],
  "tables": {
    "cash_flow_periods": [
      {
        "period": "2026",
        "operating_cash_flow": 120000.0,
        "investing_cash_flow": -50000.0,
        "financing_cash_flow": -30000.0,
        "foreign_exchange_adjustment": 0.0,
        "net_increase_in_cash": 40000.0,
        "opening_cash_balance": 100000.0,
        "closing_cash_balance": 140000.0
      }
    ],
    "full_statement_rows": []
  },
  "currency": "INR",
  "notes": []
}
"""
}

def clean_json_response(raw_text: str) -> str:
    """Removes markdown code blocks and returns clean JSON string."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()

def parse_extracted_json(json_str: str, doc_type: DocumentType) -> ExtractedData:
    """Parses and standardizes the AI extracted JSON into ExtractedData schema."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}. Raw text: {json_str[:500]}")
        # Try to find JSON block
        match = re.search(r'\{.*\}', json_str, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
        else:
            raise ValueError(f"AI response did not contain valid JSON: {str(e)}")

    summary_fields = {}
    for k, v in data.get("summary_fields", {}).items():
        if isinstance(v, dict):
            summary_fields[k] = ExtractedField(
                value=v.get("value"),
                confidence=v.get("confidence", 0.9),
                source_text=v.get("source_text"),
                page_number=v.get("page_number", 1),
                is_missing=v.get("is_missing", v.get("value") is None)
            )
        else:
            summary_fields[k] = ExtractedField(
                value=v,
                confidence=0.9,
                source_text=str(v),
                page_number=1,
                is_missing=v is None
            )

    line_items = []
    for item in data.get("line_items", []):
        line_items.append(LineItem(
            item_description=item.get("item_description"),
            quantity=item.get("quantity"),
            unit_price=item.get("unit_price"),
            line_total=item.get("line_total"),
            tax_rate=item.get("tax_rate"),
            raw_text=item.get("raw_text"),
            page_number=item.get("page_number", 1)
        ))

    return ExtractedData(
        summary_fields=summary_fields,
        tables=data.get("tables", {}),
        line_items=line_items if line_items else None,
        periods_detected=data.get("periods_detected", []),
        currency=data.get("currency", "USD"),
        notes=data.get("notes", [])
    )

async def extract_document_with_ai(
    images: List[Image.Image],
    native_text_by_page: Dict[int, str],
    doc_type: DocumentType,
    filename: str
) -> Tuple[ExtractedData, str, str]:
    """
    Extracts document data using Gemini Vision / AI or structured native fallback.
    Returns:
        (ExtractedData, ocr_engine_name, ai_model_name)
    """
    gemini_key = settings.effective_gemini_key
    
    if gemini_key:
        try:
            genai.configure(api_key=gemini_key)
            model_name = settings.GEMINI_MODEL
            model = genai.GenerativeModel(model_name)
            
            prompt = DOCUMENT_PROMPTS.get(doc_type, DOCUMENT_PROMPTS[DocumentType.INVOICE])
            
            # Combine instructions with native text hints if any
            full_prompt = prompt + "\n\nAdditional Extracted Native Text:\n"
            for pnum, text in native_text_by_page.items():
                if text.strip():
                    full_prompt += f"--- Page {pnum} Text ---\n{text[:2000]}\n"
            
            # Prepare contents: prompt + images
            contents = [full_prompt]
            for img in images:
                contents.append(img)
                
            logger.info(f"Invoking Gemini model '{model_name}' for {filename} ({doc_type.value}) with {len(images)} pages...")
            response = model.generate_content(
                contents,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json"
                )
            )
            
            cleaned_text = clean_json_response(response.text)
            extracted = parse_extracted_json(cleaned_text, doc_type)
            extracted.raw_text_by_page = {str(k): v for k, v in native_text_by_page.items()}
            
            return extracted, "Gemini Vision OCR + PyMuPDF", model_name
        except Exception as e:
            logger.error(f"Gemini AI extraction failed: {str(e)}. Falling back to deterministic document parser.")
            
    # Deterministic Rule-Based & Regex OCR Extractor Fallback
    logger.info(f"Using deterministic fallback document parser for {filename} ({doc_type.value})...")
    extracted = fallback_deterministic_extractor(native_text_by_page, doc_type, filename)
    extracted.raw_text_by_page = {str(k): v for k, v in native_text_by_page.items()}
    return extracted, "PyMuPDF Native Text Parser", "Deterministic Schema Parser v1.0"

def fallback_deterministic_extractor(native_text_by_page: Dict[int, str], doc_type: DocumentType, filename: str) -> ExtractedData:
    """
    Deterministic rule-based extractor that handles text-based PDFs and test datasets.
    """
    all_text = "\n".join(native_text_by_page.values())
    summary_fields: Dict[str, ExtractedField] = {}
    tables: Dict[str, List[Dict[str, Any]]] = {}
    line_items: List[LineItem] = []
    
    # Helper to parse float from string with commas and brackets
    def parse_num(s: str) -> Optional[float]:
        if not s:
            return None
        s = s.strip().replace(",", "").replace("$", "").replace("₹", "").replace("€", "")
        if s.startswith("(") and s.endswith(")"):
            try:
                return -float(s[1:-1])
            except ValueError:
                return None
        try:
            return float(s)
        except ValueError:
            return None

    if doc_type == DocumentType.INVOICE:
        # Regex search for invoice fields
        inv_match = re.search(r'invoice\s*(?:no|number|#)?[:\s]+([A-Za-z0-9\-]+)', all_text, re.IGNORECASE)
        if inv_match:
            summary_fields["invoice_number"] = ExtractedField(value=inv_match.group(1), confidence=0.9, source_text=inv_match.group(0), page_number=1)
            
        total_match = re.search(r'total\s*(?:amount)?[:\s]+([\$₹€]?\s*[0-9,]+\.?[0-9]*)', all_text, re.IGNORECASE)
        if total_match:
            val = parse_num(total_match.group(1))
            summary_fields["total_amount"] = ExtractedField(value=val, confidence=0.95, source_text=total_match.group(0), page_number=1)
            
        subtotal_match = re.search(r'subtotal[:\s]+([\$₹€]?\s*[0-9,]+\.?[0-9]*)', all_text, re.IGNORECASE)
        if subtotal_match:
            val = parse_num(subtotal_match.group(1))
            summary_fields["subtotal"] = ExtractedField(value=val, confidence=0.95, source_text=subtotal_match.group(0), page_number=1)
            
        tax_match = re.search(r'tax\s*(?:amount)?[:\s]+([\$₹€]?\s*[0-9,]+\.?[0-9]*)', all_text, re.IGNORECASE)
        if tax_match:
            val = parse_num(tax_match.group(1))
            summary_fields["total_tax_amount"] = ExtractedField(value=val, confidence=0.95, source_text=tax_match.group(0), page_number=1)

    elif doc_type == DocumentType.BALANCE_SHEET:
        summary_fields["total_assets"] = ExtractedField(value=None, confidence=0.0, is_missing=True)
        summary_fields["total_capital_and_liabilities"] = ExtractedField(value=None, confidence=0.0, is_missing=True)

    elif doc_type == DocumentType.PROFIT_AND_LOSS:
        summary_fields["total_income"] = ExtractedField(value=None, confidence=0.0, is_missing=True)
        summary_fields["total_expenditure"] = ExtractedField(value=None, confidence=0.0, is_missing=True)

    elif doc_type == DocumentType.CASH_FLOW_STATEMENT:
        summary_fields["operating_cash_flow"] = ExtractedField(value=None, confidence=0.0, is_missing=True)
        summary_fields["net_increase_in_cash"] = ExtractedField(value=None, confidence=0.0, is_missing=True)
        summary_fields["closing_cash_balance"] = ExtractedField(value=None, confidence=0.0, is_missing=True)

    return ExtractedData(
        summary_fields=summary_fields,
        tables=tables,
        line_items=line_items if line_items else None,
        currency="USD" if "$" in all_text else "INR",
        notes=["Processed via fallback extraction engine."]
    )
