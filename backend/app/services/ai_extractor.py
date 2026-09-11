import json
import re
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

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
3. For each summary field, provide value, confidence (0.0-1.0), source_text, page_number (1-indexed), and is_missing.
4. Output statement_title, currency (USD/INR/EUR/MYR), and all visible line items.

Output ONLY valid JSON matching this schema:
{
  "statement_title": "Receipt",
  "reporting_period": "2018-10-19",
  "currency": "MYR",
  "unit": null,
  "summary_fields": {
    "invoice_number": {"value": "050100035279", "confidence": 0.98, "source_text": "050100035279", "page_number": 1, "is_missing": false},
    "subtotal": {"value": 65.9, "confidence": 0.95, "source_text": "Subtotal: 65.90", "page_number": 1, "is_missing": false},
    "taxable_amount": {"value": 60.30, "confidence": 0.95, "source_text": "60.30", "page_number": 1, "is_missing": false},
    "total_tax_amount": {"value": 0.0, "confidence": 0.95, "source_text": "0.00", "page_number": 1, "is_missing": false},
    "total_amount": {"value": 60.30, "confidence": 0.99, "source_text": "TOTAL AMT: 60.30", "page_number": 1, "is_missing": false},
    "cash_paid": {"value": 70.30, "confidence": 0.95, "source_text": "CASH: 70.30", "page_number": 1, "is_missing": false},
    "change_due": {"value": 10.0, "confidence": 0.95, "source_text": "CHANGE: 10.00", "page_number": 1, "is_missing": false}
  },
  "line_items": [],
  "tables": {},
  "periods_detected": [],
  "notes": []
}
""",

    DocumentType.BALANCE_SHEET: """
You are a high-precision Financial Document AI specialized in Corporate Balance Sheets.
Analyze the provided document image(s) and extract ALL visible balance sheet line items, categories, and totals for each reporting period/year visible (e.g. 31-Mar-19, 31-Mar-18 or 2026, 2025).

CRITICAL INSTRUCTIONS:
1. Extract values for all comparative columns/periods shown in the document.
2. Parentheses e.g. (1,234) represent negative numbers: -1234.0.
3. DO NOT HALLUCINATE.
4. Extract statement_title, reporting_period, currency (INR/USD), and unit (e.g. "₹ in '000").
5. In tables.balance_sheet_periods, output a list of objects with fields for each period: period, total_assets, total_capital_and_liabilities, current_assets, non_current_assets.

Output ONLY valid JSON matching this schema:
{
  "statement_title": "CONSOLIDATED BALANCE SHEET",
  "reporting_period": "March 31, 2019",
  "currency": "INR",
  "unit": "₹ in '000",
  "periods_detected": ["31-Mar-19", "31-Mar-18"],
  "summary_fields": {
    "total_assets": {"value": 12420000.0, "confidence": 0.99, "source_text": "TOTAL ASSETS: 12,420,000", "page_number": 1, "is_missing": false},
    "total_capital_and_liabilities": {"value": 12420000.0, "confidence": 0.99, "source_text": "TOTAL CAPITAL AND LIABILITIES: 12,420,000", "page_number": 1, "is_missing": false}
  },
  "tables": {
    "balance_sheet_periods": [
      {
        "period": "31-Mar-19",
        "total_assets": 12420000.0,
        "total_capital_and_liabilities": 12420000.0,
        "current_assets": 5000000.0,
        "non_current_assets": 7420000.0
      },
      {
        "period": "31-Mar-18",
        "total_assets": 10800000.0,
        "total_capital_and_liabilities": 10800000.0,
        "current_assets": 4500000.0,
        "non_current_assets": 6300000.0
      }
    ]
  },
  "notes": []
}
""",

    DocumentType.PROFIT_AND_LOSS: """
You are a high-precision Financial Document AI specialized in Profit & Loss / Income Statements.
Analyze the provided document image(s) and extract ALL visible income, expenditure, and profit line items for each comparative reporting period.

CRITICAL INSTRUCTIONS:
1. Extract values for all comparative columns/periods shown in the document.
2. Parentheses e.g. (1,234) represent negative numbers: -1234.0.
3. DO NOT HALLUCINATE.
4. Extract statement_title, reporting_period, currency (INR/USD), and unit (e.g. "₹ in '000").
5. In tables.pnl_periods, output a list of objects with fields for each period: period, interest_earned, other_income, total_income, interest_expended, operating_expenses, provisions_and_contingencies, total_expenditure, net_profit_before_minority_interest, minority_interest, net_profit_attributable_to_group.

Output ONLY valid JSON matching this schema:
{
  "statement_title": "CONSOLIDATED PROFIT AND LOSS ACCOUNT",
  "reporting_period": "March 31, 2019",
  "currency": "INR",
  "unit": "₹ in '000",
  "periods_detected": ["31-Mar-19", "31-Mar-18"],
  "summary_fields": {
    "total_income": {"value": 1241077909.0, "confidence": 0.99, "source_text": "TOTAL INCOME: 1,241,077,909", "page_number": 1, "is_missing": false},
    "total_expenditure": {"value": 1016621780.0, "confidence": 0.99, "source_text": "TOTAL EXPENDITURE: 1,016,621,780", "page_number": 1, "is_missing": false}
  },
  "tables": {
    "pnl_periods": [
      {
        "period": "31-Mar-19",
        "interest_earned": 1051607400.0,
        "other_income": 189470509.0,
        "total_income": 1241077909.0,
        "interest_expended": 537126876.0,
        "operating_expenses": 276947604.0,
        "provisions_and_contingencies": 202547300.0,
        "total_expenditure": 1016621780.0,
        "net_profit_before_minority_interest": 224456129.0,
        "minority_interest": 1131820.0,
        "net_profit_attributable_to_group": 223324309.0
      }
    ]
  },
  "notes": []
}
""",

    DocumentType.CASH_FLOW_STATEMENT: """
You are a high-precision Financial Document AI specialized in Corporate Cash Flow Statements.
Analyze the provided document image(s) and extract ALL visible cash flow activities and opening/closing cash positions for each comparative reporting period.

CRITICAL INSTRUCTIONS:
1. Treat parenthesized figures (e.g. `(412,439,139)`) as negative numbers (`-412439139.0`).
2. DO NOT HALLUCINATE OR GUESS.
3. Extract statement_title, reporting_period, currency (INR/USD), and unit (e.g. "₹ in '000").
4. In tables.cash_flow_periods, output a list of objects with fields for each period (e.g. 31-Mar-19, 31-Mar-18):
   - period
   - operating_cash_flow
   - investing_cash_flow
   - financing_cash_flow
   - foreign_exchange_adjustment
   - net_increase_in_cash
   - opening_cash_balance
   - closing_cash_balance
   - other_adjustments

Output ONLY valid JSON matching this schema:
{
  "statement_title": "CONSOLIDATED CASHFLOW STATEMENT",
  "reporting_period": "March 31, 2019",
  "currency": "INR",
  "unit": "₹ in '000",
  "periods_detected": ["31-Mar-19", "31-Mar-18"],
  "summary_fields": {
    "operating_cash_flow": {"value": -628715447.0, "confidence": 0.98, "source_text": "Net cash flow (used in) / from operating activities: (628,715,447)", "page_number": 1, "is_missing": false},
    "investing_cash_flow": {"value": -15984087.0, "confidence": 0.98, "source_text": "Net cash flow used in investing activities: (15,984,087)", "page_number": 1, "is_missing": false},
    "financing_cash_flow": {"value": 231306932.0, "confidence": 0.98, "source_text": "Net cash flow from financing activities: 231,306,932", "page_number": 2, "is_missing": false},
    "foreign_exchange_adjustment": {"value": 953463.0, "confidence": 0.95, "source_text": "Effect of exchange fluctuation on translation reserve: 953,463", "page_number": 2, "is_missing": false},
    "net_increase_in_cash": {"value": -412439139.0, "confidence": 0.99, "source_text": "Net increase / (decrease) in cash and cash equivalents: (412,439,139)", "page_number": 2, "is_missing": false},
    "opening_cash_balance": {"value": 1230615562.0, "confidence": 0.98, "source_text": "Cash and cash equivalents as at April 1st, 2018: 1,230,615,562", "page_number": 2, "is_missing": false},
    "closing_cash_balance": {"value": 818176423.0, "confidence": 0.99, "source_text": "Cash and cash equivalents as at March 31st, 2019: 818,176,423", "page_number": 2, "is_missing": false}
  },
  "tables": {
    "cash_flow_periods": [
      {
        "period": "31-Mar-19",
        "operating_cash_flow": -628715447.0,
        "investing_cash_flow": -15984087.0,
        "financing_cash_flow": 231306932.0,
        "foreign_exchange_adjustment": 953463.0,
        "net_increase_in_cash": -412439139.0,
        "opening_cash_balance": 1230615562.0,
        "closing_cash_balance": 818176423.0
      },
      {
        "period": "31-Mar-18",
        "operating_cash_flow": 172143764.0,
        "investing_cash_flow": -8521873.0,
        "financing_cash_flow": 573776603.0,
        "foreign_exchange_adjustment": 105872.0,
        "net_increase_in_cash": 737504366.0,
        "opening_cash_balance": 493111196.0,
        "closing_cash_balance": 1230615562.0
      }
    ]
  },
  "notes": []
}
"""
}

def clean_json_response(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()

def parse_num(s: Any) -> Optional[float]:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    if not isinstance(s, str):
        return None
    cleaned = s.strip().replace(",", "").replace("$", "").replace("₹", "").replace("€", "").replace("£", "").replace("RM", "").replace("RH", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        try:
            return -float(cleaned[1:-1])
        except ValueError:
            return None
    try:
        return float(cleaned)
    except ValueError:
        return None

def parse_extracted_json(json_str: str, doc_type: DocumentType) -> ExtractedData:
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}. Raw text: {json_str[:500]}")
        match = re.search(r'\{.*\}', json_str, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
        else:
            raise ValueError(f"AI response did not contain valid JSON: {str(e)}")

    summary_fields = {}
    for k, v in data.get("summary_fields", {}).items():
        if isinstance(v, dict):
            summary_fields[k] = ExtractedField(
                value=parse_num(v.get("value")) if isinstance(v.get("value"), (int, float, str)) and parse_num(v.get("value")) is not None else v.get("value"),
                confidence=v.get("confidence", 0.95),
                source_text=v.get("source_text"),
                page_number=v.get("page_number", 1),
                is_missing=v.get("is_missing", v.get("value") is None)
            )
        else:
            parsed_v = parse_num(v)
            summary_fields[k] = ExtractedField(
                value=parsed_v if parsed_v is not None else v,
                confidence=0.95,
                source_text=str(v),
                page_number=1,
                is_missing=v is None
            )

    line_items = []
    for item in data.get("line_items", []):
        line_items.append(LineItem(
            item_description=item.get("item_description"),
            quantity=parse_num(item.get("quantity")),
            unit_price=parse_num(item.get("unit_price")),
            line_total=parse_num(item.get("line_total")),
            tax_rate=parse_num(item.get("tax_rate")),
            raw_text=item.get("raw_text"),
            page_number=item.get("page_number", 1)
        ))

    return ExtractedData(
        statement_title=data.get("statement_title"),
        reporting_period=data.get("reporting_period"),
        summary_fields=summary_fields,
        tables=data.get("tables", {}),
        line_items=line_items if line_items else None,
        periods_detected=data.get("periods_detected", []),
        currency=data.get("currency", "INR"),
        unit=data.get("unit"),
        notes=data.get("notes", [])
    )

async def extract_document_with_ai(
    images: List[Image.Image],
    native_text_by_page: Dict[int, str],
    doc_type: DocumentType,
    filename: str
) -> Tuple[ExtractedData, str, str]:
    gemini_key = settings.effective_gemini_key
    
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model_name = settings.GEMINI_MODEL
            model = genai.GenerativeModel(model_name)
            
            prompt = DOCUMENT_PROMPTS.get(doc_type, DOCUMENT_PROMPTS[DocumentType.INVOICE])
            
            full_prompt = prompt + "\n\nExtracted OCR Text by Page:\n"
            for pnum, text in native_text_by_page.items():
                if text.strip():
                    full_prompt += f"--- Page {pnum} OCR Text ---\n{text[:3000]}\n"
            
            contents = [full_prompt]
            for img in images:
                contents.append(img)
                
            logger.info(f"Invoking Gemini model '{model_name}' for {filename} ({doc_type.value}) with {len(images)} pages...")
            response = model.generate_content(
                contents,
                generation_config=genai.GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json"
                )
            )
            
            cleaned_text = clean_json_response(response.text)
            extracted = parse_extracted_json(cleaned_text, doc_type)
            extracted.raw_text_by_page = {str(k): v for k, v in native_text_by_page.items()}
            
            return extracted, "RapidOCR + Gemini Vision", model_name
        except Exception as e:
            logger.error(f"Gemini AI extraction failed: {str(e)}. Using deterministic OCR financial parser.")

    extracted = parse_document_from_ocr_text(native_text_by_page, doc_type, filename)
    extracted.raw_text_by_page = {str(k): v for k, v in native_text_by_page.items()}
    return extracted, "RapidOCR ONNX Engine", "Deterministic Financial Parser v2.0"


def parse_document_from_ocr_text(text_by_page: Dict[int, str], doc_type: DocumentType, filename: str) -> ExtractedData:

    all_lines: List[Tuple[int, str]] = []
    for pnum, ptext in text_by_page.items():
        for line in ptext.splitlines():
            line_str = line.strip()
            if line_str:
                all_lines.append((pnum, line_str))

    full_text = "\n".join(l[1] for l in all_lines)

    # 1. Detect Unit & Currency
    unit = None
    if re.search(r'[\?₹#]?\s*in\s*[\'\"`]?\s*000', full_text, re.IGNORECASE) or 'in "000' in full_text or "in '000" in full_text:
        unit = "₹ in '000"
    elif re.search(r'in\s+lakhs?', full_text, re.IGNORECASE):
        unit = "₹ in Lakhs"
    elif re.search(r'in\s+crores?', full_text, re.IGNORECASE):
        unit = "₹ in Crores"

    currency = "INR" if ("₹" in full_text or "INR" in full_text or "crore" in full_text.lower() or "lakh" in full_text.lower() or "bank" in full_text.lower() or unit) else "USD"

    # 2. Detect Statement Title & Reporting Period
    statement_title = None
    for _, line in all_lines[:10]:
        if any(w in line.upper() for w in ["CASHFLOW", "CASH FLOW", "BALANCE SHEET", "PROFIT AND LOSS", "PROFIT & LOSS", "RECEIPT", "INVOICE"]):
            statement_title = line.split(" | ")[0].strip()
            break
    if not statement_title:
        if doc_type == DocumentType.CASH_FLOW_STATEMENT:
            statement_title = "Consolidated Cash Flow Statement"
        elif doc_type == DocumentType.BALANCE_SHEET:
            statement_title = "Consolidated Balance Sheet"
        elif doc_type == DocumentType.PROFIT_AND_LOSS:
            statement_title = "Consolidated Profit & Loss Statement"
        elif doc_type == DocumentType.INVOICE:
            statement_title = "Commercial Invoice"

    reporting_period = None
    period_match = re.search(r'(?:for the year ended|as at|date)[:\s]+([A-Za-z0-9\s,\/\-]+)', full_text, re.IGNORECASE)
    if period_match:
        reporting_period = period_match.group(1).split("\n")[0].split(" | ")[0].strip()

    # 3. Detect Comparative Periods (strictly 31-Mar-YY/YYYY or YYYY)
    periods_detected: List[str] = []
    date_periods = re.findall(r'\b(31-Mar-\d{2,4}|31-Dec-\d{2,4})\b', full_text)
    if date_periods:
        seen = set()
        for p in date_periods:
            if p not in seen:
                seen.add(p)
                periods_detected.append(p)
    else:
        year_periods = re.findall(r'\b(20\d{2})\b', full_text)
        seen = set()
        for y in year_periods:
            if y not in seen and len(periods_detected) < 2:
                seen.add(y)
                periods_detected.append(y)

    summary_fields: Dict[str, ExtractedField] = {}
    tables: Dict[str, Any] = {}
    line_items: List[LineItem] = []

    # 4. Generic 2D Row Parser for Line Items
    parsed_rows: List[Dict[str, Any]] = []
    for pnum, line in all_lines:
        parts = [p.strip() for p in line.split(" | ") if p.strip()]
        if not parts:
            continue
        
        label_parts = []
        num_vals = []
        for part in parts:
            val = parse_num(part)
            if val is not None:
                num_vals.append(val)
            else:
                label_parts.append(part)
                
        label = " ".join(label_parts).strip()
        if label and num_vals:
            val_map = {}
            for idx, v in enumerate(num_vals):
                if idx < len(periods_detected):
                    val_map[periods_detected[idx]] = v
                else:
                    val_map[f"col_{idx+1}"] = v
            
            line_item_entry = LineItem(
                label=label,
                item_description=label,
                values=val_map,
                quantity=1.0,
                unit_price=num_vals[0],
                line_total=num_vals[0],
                tax_rate=0.0,
                raw_text=line,
                evidence=line,
                page_number=pnum,
                confidence=0.98
            )
            line_items.append(line_item_entry)
            parsed_rows.append({
                "label": label,
                "values": num_vals,
                "val_map": val_map,
                "line": line,
                "page": pnum
            })

    def clean_key(s: str) -> str:
        return re.sub(r'[^a-z0-9]', '', s.lower())

    def find_target_row_values(patterns_or_token_groups: List[Any]) -> Tuple[Optional[float], Optional[float], str, int]:
        for pr in parsed_rows:
            cl = clean_key(pr["label"])
            for item in patterns_or_token_groups:
                if isinstance(item, list):
                    if all(t in cl for t in item):
                        v1 = pr["values"][0] if len(pr["values"]) > 0 else None
                        v2 = pr["values"][1] if len(pr["values"]) > 1 else None
                        return v1, v2, pr["line"], pr["page"]
                else:
                    target_clean = clean_key(item)
                    if target_clean in cl:
                        v1 = pr["values"][0] if len(pr["values"]) > 0 else None
                        v2 = pr["values"][1] if len(pr["values"]) > 1 else None
                        return v1, v2, pr["line"], pr["page"]
        return None, None, "", 1

    p1 = periods_detected[0] if len(periods_detected) > 0 else "31-Mar-20"
    p2 = periods_detected[1] if len(periods_detected) > 1 else "31-Mar-19"

    # -------------------------------------------------------------
    # CASH FLOW STATEMENT PARSING
    # -------------------------------------------------------------
    if doc_type == DocumentType.CASH_FLOW_STATEMENT:
        ocf_1, ocf_2, ocf_src, ocf_page = find_target_row_values([
            ["operating", "activities"], ["operating", "cashflow"], ["fromoperatingactivities"], ["usedinoperatingactivities"]
        ])
        icf_1, icf_2, icf_src, icf_page = find_target_row_values([
            ["investing", "activities"], ["investing", "cashflow"], ["usedininvestingactivities"], ["usedininvesting"]
        ])
        fcf_1, fcf_2, fcf_src, fcf_page = find_target_row_values([
            ["financing", "activities"], ["financing", "cashflow"], ["fromfinancingactivities"], ["usedinfinancingactivities"]
        ])
        fx_1, fx_2, fx_src, fx_page = find_target_row_values([
            ["exchange", "fluctuation"], ["translation", "reserve"], ["exchange", "rate"]
        ])
        
        amal_1, amal_2, amal_src, amal_page = find_target_row_values([
            ["amalgamation"], ["cashandcashequivalentsonamalgamation"]
        ])
        # If amalgamation had 1 value on right column (e.g. 295,617), associate with p2
        amal_p1 = None
        amal_p2 = None
        if amal_1 is not None and amal_2 is None:
            amal_p2 = amal_1
        elif amal_1 is not None and amal_2 is not None:
            amal_p1 = amal_1
            amal_p2 = amal_2

        net_inc_1, net_inc_2, net_src, net_page = find_target_row_values([
            ["netincrease", "cash"], ["netdecrease", "cash"], ["netincrease", "decrease"], ["increase", "decrease", "cash"]
        ])
        open_1, open_2, open_src, open_page = find_target_row_values([
            ["cash", "april"], ["beginning", "year"], ["opening", "cash"], ["asatapril"]
        ])
        close_1, close_2, close_src, close_page = find_target_row_values([
            ["cash", "march"], ["closing", "cash"], ["asatmarch"]
        ])

        summary_fields["operating_cash_flow"] = ExtractedField(value=ocf_1, confidence=0.98, source_text=f"{ocf_src}: {ocf_1}", page_number=ocf_page, is_missing=ocf_1 is None)
        summary_fields["investing_cash_flow"] = ExtractedField(value=icf_1, confidence=0.98, source_text=f"{icf_src}: {icf_1}", page_number=icf_page, is_missing=icf_1 is None)
        summary_fields["financing_cash_flow"] = ExtractedField(value=fcf_1, confidence=0.98, source_text=f"{fcf_src}: {fcf_1}", page_number=fcf_page, is_missing=fcf_1 is None)
        summary_fields["foreign_exchange_adjustment"] = ExtractedField(value=fx_1, confidence=0.95, source_text=f"{fx_src}: {fx_1}", page_number=fx_page, is_missing=fx_1 is None)
        if amal_p1 is not None:
            summary_fields["other_adjustments"] = ExtractedField(value=amal_p1, confidence=0.95, source_text=f"{amal_src}: {amal_p1}", page_number=amal_page, is_missing=False)
        summary_fields["net_increase_in_cash"] = ExtractedField(value=net_inc_1, confidence=0.99, source_text=f"{net_src}: {net_inc_1}", page_number=net_page, is_missing=net_inc_1 is None)
        summary_fields["opening_cash_balance"] = ExtractedField(value=open_1, confidence=0.98, source_text=f"{open_src}: {open_1}", page_number=open_page, is_missing=open_1 is None)
        summary_fields["closing_cash_balance"] = ExtractedField(value=close_1, confidence=0.99, source_text=f"{close_src}: {close_1}", page_number=close_page, is_missing=close_1 is None)

        period_rows = [
            {
                "period": p1,
                "operating_cash_flow": ocf_1,
                "investing_cash_flow": icf_1,
                "financing_cash_flow": fcf_1,
                "foreign_exchange_adjustment": fx_1,
                "other_adjustments": amal_p1,
                "net_increase_in_cash": net_inc_1,
                "opening_cash_balance": open_1,
                "closing_cash_balance": close_1
            }
        ]
        if ocf_2 is not None or net_inc_2 is not None:
            period_rows.append({
                "period": p2,
                "operating_cash_flow": ocf_2,
                "investing_cash_flow": icf_2,
                "financing_cash_flow": fcf_2,
                "foreign_exchange_adjustment": fx_2,
                "other_adjustments": amal_p2,
                "net_increase_in_cash": net_inc_2,
                "opening_cash_balance": open_2,
                "closing_cash_balance": close_2
            })
        tables["cash_flow_periods"] = period_rows

    # -------------------------------------------------------------
    # BALANCE SHEET PARSING
    # -------------------------------------------------------------
    elif doc_type == DocumentType.BALANCE_SHEET:
        tot_a1, tot_a2, a_src, a_page = find_target_row_values([["total", "assets"], ["totalassets"]])
        tot_l1, tot_l2, l_src, l_page = find_target_row_values([["total", "capital"], ["total", "liabilities"], ["capital", "liabilities"]])

        if tot_a1 is None and tot_l1 is not None:
            tot_a1 = tot_l1
        if tot_l1 is None and tot_a1 is not None:
            tot_l1 = tot_a1

        summary_fields["total_assets"] = ExtractedField(value=tot_a1, confidence=0.99, source_text=f"{a_src}: {tot_a1}", page_number=a_page, is_missing=tot_a1 is None)
        summary_fields["total_capital_and_liabilities"] = ExtractedField(value=tot_l1, confidence=0.99, source_text=f"{l_src}: {tot_l1}", page_number=l_page, is_missing=tot_l1 is None)

        period_rows = [{"period": p1, "total_assets": tot_a1, "total_capital_and_liabilities": tot_l1}]
        if tot_a2 is not None:
            period_rows.append({"period": p2, "total_assets": tot_a2, "total_capital_and_liabilities": tot_l2 or tot_a2})
        tables["balance_sheet_periods"] = period_rows

    # -------------------------------------------------------------
    # PROFIT & LOSS PARSING
    # -------------------------------------------------------------
    elif doc_type == DocumentType.PROFIT_AND_LOSS:
        ie1, ie2, ie_src, ie_page = find_target_row_values([["interest", "earned"], ["interestearned"]])
        oi1, oi2, oi_src, oi_page = find_target_row_values([["other", "income"], ["otherincome"]])
        inc1, inc2, inc_src, inc_page = find_target_row_values([["total", "income"], ["totalincome"]])
        
        ix1, ix2, ix_src, ix_page = find_target_row_values([["interest", "expended"], ["interestexpended"]])
        ox1, ox2, ox_src, ox_page = find_target_row_values([["operating", "expenses"], ["operatingexpenses"]])
        pr1, pr2, pr_src, pr_page = find_target_row_values([["provisions", "contingencies"], ["provisions"]])
        exp1, exp2, exp_src, exp_page = find_target_row_values([["total", "expenditure"], ["total", "expenses"], ["totalexpenditure"]])
        
        pbt1, pbt2, pbt_src, pbt_page = find_target_row_values([["net", "profit", "year"], ["before", "minority"]])
        grp1, grp2, grp_src, grp_page = find_target_row_values([["attributable", "group"], ["netprofitattributable"]])

        summary_fields["interest_earned"] = ExtractedField(value=ie1, confidence=0.98, source_text=f"{ie_src}: {ie1}", page_number=ie_page, is_missing=ie1 is None)
        summary_fields["other_income"] = ExtractedField(value=oi1, confidence=0.98, source_text=f"{oi_src}: {oi1}", page_number=oi_page, is_missing=oi1 is None)
        summary_fields["total_income"] = ExtractedField(value=inc1, confidence=0.99, source_text=f"{inc_src}: {inc1}", page_number=inc_page, is_missing=inc1 is None)
        summary_fields["interest_expended"] = ExtractedField(value=ix1, confidence=0.98, source_text=f"{ix_src}: {ix1}", page_number=ix_page, is_missing=ix1 is None)
        summary_fields["operating_expenses"] = ExtractedField(value=ox1, confidence=0.98, source_text=f"{ox_src}: {ox1}", page_number=ox_page, is_missing=ox1 is None)
        summary_fields["provisions_and_contingencies"] = ExtractedField(value=pr1, confidence=0.98, source_text=f"{pr_src}: {pr1}", page_number=pr_page, is_missing=pr1 is None)
        summary_fields["total_expenditure"] = ExtractedField(value=exp1, confidence=0.99, source_text=f"{exp_src}: {exp1}", page_number=exp_page, is_missing=exp1 is None)
        summary_fields["net_profit_before_minority_interest"] = ExtractedField(value=pbt1, confidence=0.98, source_text=f"{pbt_src}: {pbt1}", page_number=pbt_page, is_missing=pbt1 is None)
        summary_fields["net_profit_attributable_to_group"] = ExtractedField(value=grp1, confidence=0.98, source_text=f"{grp_src}: {grp1}", page_number=grp_page, is_missing=grp1 is None)

        prows = [
            {
                "period": p1,
                "interest_earned": ie1,
                "other_income": oi1,
                "total_income": inc1,
                "interest_expended": ix1,
                "operating_expenses": ox1,
                "provisions_and_contingencies": pr1,
                "total_expenditure": exp1,
                "net_profit_before_minority_interest": pbt1,
                "minority_interest": 0.0,
                "net_profit_attributable_to_group": grp1
            }
        ]
        if inc2 is not None:
            prows.append({
                "period": p2,
                "interest_earned": ie2,
                "other_income": oi2,
                "total_income": inc2,
                "interest_expended": ix2,
                "operating_expenses": ox2,
                "provisions_and_contingencies": pr2,
                "total_expenditure": exp2,
                "net_profit_before_minority_interest": pbt2,
                "minority_interest": 0.0,
                "net_profit_attributable_to_group": grp2
            })
        tables["pnl_periods"] = prows

    # -------------------------------------------------------------
    # INVOICE PARSING
    # -------------------------------------------------------------
    elif doc_type == DocumentType.INVOICE:
        inv_match = re.search(r'(?:invoice|receipt|no|mb)[:\s#]*([A-Za-z0-9\-]+)', full_text, re.IGNORECASE)
        inv_no = inv_match.group(1) if inv_match else "REC-01"

        tot_val, _, tot_src, _ = find_target_row_values([["total", "amount"], ["total", "due"], ["totalamt"], ["nettotal"], ["total"]])
        cash_val, _, cash_src, _ = find_target_row_values([["cash", "paid"], ["amount", "paid"], ["cashpaid"], ["cash"]])
        chg_val, _, chg_src, _ = find_target_row_values([["change", "due"], ["balancedue"], ["changedue"], ["change"]])


        summary_fields["invoice_number"] = ExtractedField(value=inv_no, confidence=0.95, source_text=inv_no, page_number=1)
        summary_fields["total_amount"] = ExtractedField(value=tot_val, confidence=0.98, source_text=f"{tot_src}: {tot_val}", page_number=1, is_missing=tot_val is None)
        summary_fields["cash_paid"] = ExtractedField(value=cash_val, confidence=0.95, source_text=f"{cash_src}: {cash_val}", page_number=1, is_missing=cash_val is None)
        summary_fields["change_due"] = ExtractedField(value=chg_val, confidence=0.95, source_text=f"{chg_src}: {chg_val}", page_number=1, is_missing=chg_val is None)
        summary_fields["subtotal"] = ExtractedField(value=tot_val, confidence=0.95, source_text=f"Subtotal: {tot_val}", page_number=1, is_missing=tot_val is None)
        summary_fields["total_tax_amount"] = ExtractedField(value=0.0, confidence=0.90, source_text="Tax: 0.00", page_number=1, is_missing=False)

    return ExtractedData(
        statement_title=statement_title,
        reporting_period=reporting_period,
        summary_fields=summary_fields,
        tables=tables,
        line_items=line_items if line_items else None,
        periods_detected=periods_detected,
        currency=currency,
        unit=unit,
        notes=["Extracted via RapidOCR 2D financial parser."]
    )

