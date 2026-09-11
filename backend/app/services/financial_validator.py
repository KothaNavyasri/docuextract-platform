import math
from typing import List, Dict, Any, Optional
from backend.app.schemas.document import DocumentType, ExtractedData
from backend.app.schemas.validation import (
    ValidationCheck,
    ValidationStatus,
    DocumentValidationSummary
)
from backend.app.core.logging import logger

TOLERANCE_DEFAULT = 1.0  # Allow rounding differences in financial reports

def to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        inner_val = val.get("value")
        if inner_val is not None:
            return to_float(inner_val)
        return None
    if hasattr(val, "value"):
        return to_float(val.value)
    if isinstance(val, str):
        cleaned = val.strip().replace(",", "").replace("$", "").replace("₹", "").replace("€", "")
        if cleaned.startswith("(") and cleaned.endswith(")"):
            try:
                return -float(cleaned[1:-1])
            except ValueError:
                return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None

def check_equality(
    check_id: str,
    formula_name: str,
    formula_description: str,
    calculated_value: Optional[float],
    reported_value: Optional[float],
    operands: Dict[str, Any],
    tolerance: float = TOLERANCE_DEFAULT,
    not_applicable_reason: str = "Required fields are missing."
) -> ValidationCheck:
    """Generates a consistent ValidationCheck object."""
    if calculated_value is None or reported_value is None:
        return ValidationCheck(
            check_id=check_id,
            formula_name=formula_name,
            formula_description=formula_description,
            operands=operands,
            calculated_value=calculated_value,
            reported_value=reported_value,
            variance=None,
            status=ValidationStatus.NOT_APPLICABLE,
            tolerance=tolerance,
            explanation=f"NOT APPLICABLE: {not_applicable_reason}"
        )
    
    variance = round(abs(calculated_value - reported_value), 4)
    # Check absolute tolerance or relative tolerance <= 0.001 (0.1%)
    max_val = max(abs(reported_value), abs(calculated_value), 1.0)
    rel_diff = variance / max_val
    is_pass = variance <= tolerance or rel_diff <= 0.001
    
    status = ValidationStatus.PASS if is_pass else ValidationStatus.FAIL
    explanation = (
        f"PASSED: Calculated value {calculated_value:,.2f} matches reported value {reported_value:,.2f} (Variance: {variance:,.2f} <= {tolerance})."
        if is_pass else
        f"FAILED: Calculated value {calculated_value:,.2f} does not reconcile with reported value {reported_value:,.2f} (Variance: {variance:,.2f} > {tolerance})."
    )
    
    return ValidationCheck(
        check_id=check_id,
        formula_name=formula_name,
        formula_description=formula_description,
        operands=operands,
        calculated_value=round(calculated_value, 4),
        reported_value=round(reported_value, 4),
        variance=variance,
        status=status,
        tolerance=tolerance,
        explanation=explanation
    )

def validate_invoice(extracted: ExtractedData) -> List[ValidationCheck]:
    checks: List[ValidationCheck] = []
    fields = extracted.summary_fields
    
    subtotal = to_float(fields.get("subtotal"))
    taxable_amount = to_float(fields.get("taxable_amount"))
    total_tax = to_float(fields.get("total_tax_amount"))
    total_amount = to_float(fields.get("total_amount"))
    cash_paid = to_float(fields.get("cash_paid"))
    change_due = to_float(fields.get("change_due"))
    
    # 1. Line items: Quantity * Unit Price ≈ Line Total
    if extracted.line_items:
        for idx, item in enumerate(extracted.line_items):
            q = to_float(item.quantity)
            p = to_float(item.unit_price)
            t = to_float(item.line_total)
            calc_t = (q * p) if (q is not None and p is not None) else None
            
            checks.append(check_equality(
                check_id=f"INV_LINE_ITEM_{idx+1}",
                formula_name="Line Item Total Calculation",
                formula_description=f"Quantity × Unit Price ≈ Line Total for Item {idx+1} ('{item.item_description or 'Item'}')",
                calculated_value=calc_t,
                reported_value=t,
                operands={"quantity": q, "unit_price": p, "reported_line_total": t},
                not_applicable_reason="Line item quantity, unit price, or total not available."
            ))
            
        # 2. Sum of line totals reconciles with subtotal / total
        line_totals = [to_float(item.line_total) for item in extracted.line_items if to_float(item.line_total) is not None]
        if line_totals and len(line_totals) == len(extracted.line_items):
            sum_lines = sum(line_totals)
            target_reported = subtotal if subtotal is not None else total_amount
            checks.append(check_equality(
                check_id="INV_SUM_LINE_ITEMS",
                formula_name="Sum of Line Items Reconciliation",
                formula_description="Sum of all item line totals ≈ Subtotal / Total Amount",
                calculated_value=sum_lines,
                reported_value=target_reported,
                operands={"line_totals": line_totals, "sum_of_lines": sum_lines, "target_reported": target_reported},
                not_applicable_reason="Line items or subtotal/total not fully extracted."
            ))
    else:
        checks.append(ValidationCheck(
            check_id="INV_SUM_LINE_ITEMS",
            formula_name="Sum of Line Items Reconciliation",
            formula_description="Sum of all item line totals ≈ Subtotal / Total Amount",
            operands={},
            status=ValidationStatus.NOT_APPLICABLE,
            explanation="NOT APPLICABLE: No line items table detected on invoice."
        ))

    # 3. Tax Reconciliation: Taxable Amount + Tax ≈ Total (or Subtotal + Tax ≈ Total)
    base_amount = taxable_amount if taxable_amount is not None else subtotal
    if base_amount is not None and total_tax is not None and total_amount is not None:
        calc_total = base_amount + total_tax
        checks.append(check_equality(
            check_id="INV_TAX_RECONCILIATION",
            formula_name="Taxable Amount & Tax to Total Reconciliation",
            formula_description="Base / Taxable Amount + Total Tax Amount ≈ Total Amount",
            calculated_value=calc_total,
            reported_value=total_amount,
            operands={"base_taxable_amount": base_amount, "total_tax": total_tax, "total_amount": total_amount}
        ))
    else:
        checks.append(check_equality(
            check_id="INV_TAX_RECONCILIATION",
            formula_name="Taxable Amount & Tax to Total Reconciliation",
            formula_description="Base / Taxable Amount + Total Tax Amount ≈ Total Amount",
            calculated_value=None,
            reported_value=total_amount,
            operands={"base_taxable_amount": base_amount, "total_tax": total_tax, "total_amount": total_amount},
            not_applicable_reason="Tax amount or base subtotal missing on invoice."
        ))

    # 4. Cash Paid - Total ≈ Change Due
    if cash_paid is not None and total_amount is not None and change_due is not None:
        calc_change = cash_paid - total_amount
        checks.append(check_equality(
            check_id="INV_CASH_CHANGE_RECONCILIATION",
            formula_name="Cash Paid to Change Reconciliation",
            formula_description="Cash Paid - Total Amount ≈ Change Due",
            calculated_value=calc_change,
            reported_value=change_due,
            operands={"cash_paid": cash_paid, "total_amount": total_amount, "reported_change": change_due}
        ))
    else:
        checks.append(check_equality(
            check_id="INV_CASH_CHANGE_RECONCILIATION",
            formula_name="Cash Paid to Change Reconciliation",
            formula_description="Cash Paid - Total Amount ≈ Change Due",
            calculated_value=None,
            reported_value=change_due,
            operands={"cash_paid": cash_paid, "total_amount": total_amount, "change_due": change_due},
            not_applicable_reason="Payment amount or change due not specified on invoice."
        ))

    return checks

def validate_balance_sheet(extracted: ExtractedData) -> List[ValidationCheck]:
    checks: List[ValidationCheck] = []
    
    # Check if multi-period table exists
    bs_periods = []
    if isinstance(extracted.tables, dict):
        bs_periods = extracted.tables.get("balance_sheet_periods", [])
    elif isinstance(extracted.tables, list):
        bs_periods = extracted.tables
        
    if bs_periods:
        for idx, row in enumerate(bs_periods):
            period = str(row.get("period", f"Period {idx+1}"))
            assets = to_float(row.get("total_assets"))
            cap_liab = to_float(row.get("total_capital_and_liabilities") or row.get("total_equity_and_liabilities"))
            
            # Primary Balance Sheet Rule: Total Capital & Liabilities ≈ Total Assets
            checks.append(check_equality(
                check_id=f"BS_ASSETS_EQ_LIAB_{period}",
                formula_name=f"Balance Sheet Equality ({period})",
                formula_description=f"Total Capital & Liabilities ≈ Total Assets for {period}",
                calculated_value=cap_liab,
                reported_value=assets,
                operands={"period": period, "total_capital_and_liabilities": cap_liab, "total_assets": assets},
                not_applicable_reason=f"Missing Total Assets or Total Liabilities for {period}."
            ))
            
            # Component validation if available: Current Assets + Non-Current Assets = Total Assets
            curr_a = to_float(row.get("current_assets"))
            non_curr_a = to_float(row.get("non_current_assets"))
            if curr_a is not None and non_curr_a is not None:
                calc_tot_a = curr_a + non_curr_a
                checks.append(check_equality(
                    check_id=f"BS_ASSET_COMPONENTS_{period}",
                    formula_name=f"Total Assets Component Reconciliation ({period})",
                    formula_description=f"Current Assets + Non-Current Assets ≈ Total Assets for {period}",
                    calculated_value=calc_tot_a,
                    reported_value=assets,
                    operands={"current_assets": curr_a, "non_current_assets": non_curr_a, "total_assets": assets}
                ))
    else:
        fields = extracted.summary_fields
        assets = to_float(fields.get("total_assets"))
        cap_liab = to_float(fields.get("total_capital_and_liabilities") or fields.get("total_equity_and_liabilities"))
        period = str(fields.get("period_ended", "Latest Period"))
        
        checks.append(check_equality(
            check_id="BS_ASSETS_EQ_LIAB",
            formula_name="Balance Sheet Equality",
            formula_description="Total Capital & Liabilities ≈ Total Assets",
            calculated_value=cap_liab,
            reported_value=assets,
            operands={"period": period, "total_capital_and_liabilities": cap_liab, "total_assets": assets},
            not_applicable_reason="Missing Total Assets or Total Liabilities in extracted summary."
        ))

    return checks

def validate_profit_and_loss(extracted: ExtractedData) -> List[ValidationCheck]:
    checks: List[ValidationCheck] = []
    
    pnl_periods = []
    if isinstance(extracted.tables, dict):
        pnl_periods = extracted.tables.get("pnl_periods", [])
    elif isinstance(extracted.tables, list):
        pnl_periods = extracted.tables
        
    if pnl_periods:
        for idx, row in enumerate(pnl_periods):
            period = str(row.get("period", f"Period {idx+1}"))
            
            interest_earned = to_float(row.get("interest_earned"))
            other_income = to_float(row.get("other_income"))
            total_income = to_float(row.get("total_income"))
            
            interest_expended = to_float(row.get("interest_expended"))
            operating_expenses = to_float(row.get("operating_expenses"))
            provisions = to_float(row.get("provisions_and_contingencies") or row.get("provisions"))
            total_expenditure = to_float(row.get("total_expenditure"))
            
            net_profit_before_minority = to_float(row.get("net_profit_before_minority_interest") or row.get("operating_profit"))
            minority_interest = to_float(row.get("minority_interest")) or 0.0
            net_profit_group = to_float(row.get("net_profit_attributable_to_group") or row.get("net_profit"))
            
            # Rule 1: Interest Earned + Other Income ≈ Total Income
            calc_income = (interest_earned + other_income) if (interest_earned is not None and other_income is not None) else None
            checks.append(check_equality(
                check_id=f"PNL_TOTAL_INCOME_{period}",
                formula_name=f"Total Income Reconciliation ({period})",
                formula_description=f"Interest Earned + Other Income ≈ Total Income for {period}",
                calculated_value=calc_income,
                reported_value=total_income,
                operands={"period": period, "interest_earned": interest_earned, "other_income": other_income, "total_income": total_income},
                not_applicable_reason="Interest earned or other income not present."
            ))
            
            # Rule 2: Total Expenditure Reconciliation
            calc_exp = None
            if interest_expended is not None and operating_expenses is not None:
                calc_exp = interest_expended + operating_expenses + (provisions or 0.0)
            checks.append(check_equality(
                check_id=f"PNL_TOTAL_EXPENDITURE_{period}",
                formula_name=f"Total Expenditure Reconciliation ({period})",
                formula_description=f"Interest Expended + Operating Expenses + Provisions ≈ Total Expenditure for {period}",
                calculated_value=calc_exp,
                reported_value=total_expenditure,
                operands={"period": period, "interest_expended": interest_expended, "operating_expenses": operating_expenses, "provisions": provisions, "total_expenditure": total_expenditure},
                not_applicable_reason="Expenditure breakdown components not present."
            ))
            
            # Rule 3: Total Income - Total Expenditure ≈ Net Profit before Minority
            calc_pbt = (total_income - total_expenditure) if (total_income is not None and total_expenditure is not None) else None
            checks.append(check_equality(
                check_id=f"PNL_PROFIT_BEFORE_MINORITY_{period}",
                formula_name=f"Net Profit before Minority Interest ({period})",
                formula_description=f"Total Income - Total Expenditure ≈ Net Profit before Minority Interest for {period}",
                calculated_value=calc_pbt,
                reported_value=net_profit_before_minority,
                operands={"period": period, "total_income": total_income, "total_expenditure": total_expenditure, "reported_net_profit_before_minority": net_profit_before_minority},
                not_applicable_reason="Total Income, Total Expenditure, or Net Profit before Minority missing."
            ))
            
            # Rule 4: Group Net Profit
            calc_group_profit = (net_profit_before_minority - minority_interest) if net_profit_before_minority is not None else None
            checks.append(check_equality(
                check_id=f"PNL_NET_PROFIT_GROUP_{period}",
                formula_name=f"Consolidated Net Profit attributable to Group ({period})",
                formula_description=f"Profit before Minority Interest - Minority Interest ≈ Consolidated Net Profit for {period}",
                calculated_value=calc_group_profit,
                reported_value=net_profit_group,
                operands={"period": period, "net_profit_before_minority": net_profit_before_minority, "minority_interest": minority_interest, "reported_net_profit_group": net_profit_group},
                not_applicable_reason="Minority interest or net profit breakdown not available."
            ))
    else:
        fields = extracted.summary_fields
        interest_earned = to_float(fields.get("interest_earned"))
        other_income = to_float(fields.get("other_income"))
        total_income = to_float(fields.get("total_income"))
        
        calc_income = (interest_earned + other_income) if (interest_earned is not None and other_income is not None) else None
        checks.append(check_equality(
            check_id="PNL_TOTAL_INCOME",
            formula_name="Total Income Reconciliation",
            formula_description="Interest Earned + Other Income ≈ Total Income",
            calculated_value=calc_income,
            reported_value=total_income,
            operands={"interest_earned": interest_earned, "other_income": other_income, "total_income": total_income},
            not_applicable_reason="Income components not extracted."
        ))

    return checks

def validate_cash_flow(extracted: ExtractedData) -> List[ValidationCheck]:
    checks: List[ValidationCheck] = []
    
    cf_periods = []
    if isinstance(extracted.tables, dict):
        cf_periods = extracted.tables.get("cash_flow_periods", [])
    elif isinstance(extracted.tables, list):
        cf_periods = extracted.tables
        
    if cf_periods:
        for idx, row in enumerate(cf_periods):
            period = str(row.get("period", f"Period {idx+1}"))
            
            ocf = to_float(row.get("operating_cash_flow"))
            icf = to_float(row.get("investing_cash_flow"))
            fcf = to_float(row.get("financing_cash_flow"))
            fx = to_float(row.get("foreign_exchange_adjustment")) or 0.0
            net_inc = to_float(row.get("net_increase_in_cash"))
            
            opening = to_float(row.get("opening_cash_balance"))
            closing = to_float(row.get("closing_cash_balance"))
            adjustments = to_float(row.get("other_adjustments")) or 0.0
            
            # Rule 1: Operating Cash Flow + Investing Cash Flow + Financing Cash Flow + FX/Translation Adjustment ≈ Net Increase in Cash
            calc_net = None
            if ocf is not None and icf is not None and fcf is not None:
                calc_net = ocf + icf + fcf + fx
                
            checks.append(check_equality(
                check_id=f"CF_NET_INCREASE_{period}",
                formula_name=f"Net Increase in Cash Reconciliation ({period})",
                formula_description=f"Operating ({ocf or 0:,.0f}) + Investing ({icf or 0:,.0f}) + Financing ({fcf or 0:,.0f}) + FX ({fx or 0:,.0f}) ≈ Net Increase ({net_inc or 0:,.0f})",
                calculated_value=calc_net,
                reported_value=net_inc,
                operands={"period": period, "operating_cash_flow": ocf, "investing_cash_flow": icf, "financing_cash_flow": fcf, "fx_adjustment": fx, "reported_net_increase": net_inc},
                not_applicable_reason="One or more cash flow activity totals missing."
            ))
            
            # Rule 2: Opening Cash + Net Increase in Cash + applicable adjustments ≈ Closing Cash
            calc_closing = None
            effective_net = net_inc if net_inc is not None else calc_net
            if opening is not None and effective_net is not None:
                calc_closing = opening + effective_net + adjustments
                
            checks.append(check_equality(
                check_id=f"CF_CLOSING_CASH_{period}",
                formula_name=f"Closing Cash Balance Reconciliation ({period})",
                formula_description=f"Opening Cash ({opening or 0:,.0f}) + Net Increase ({effective_net or 0:,.0f}) ≈ Closing Cash ({closing or 0:,.0f})",
                calculated_value=calc_closing,
                reported_value=closing,
                operands={"period": period, "opening_cash": opening, "net_increase": effective_net, "adjustments": adjustments, "reported_closing_cash": closing},
                not_applicable_reason="Opening or closing cash balances missing."
            ))
    else:
        fields = extracted.summary_fields
        ocf = to_float(fields.get("operating_cash_flow"))
        icf = to_float(fields.get("investing_cash_flow"))
        fcf = to_float(fields.get("financing_cash_flow"))
        fx = to_float(fields.get("foreign_exchange_adjustment")) or 0.0
        net_inc = to_float(fields.get("net_increase_in_cash"))
        opening = to_float(fields.get("opening_cash_balance"))
        closing = to_float(fields.get("closing_cash_balance"))
        
        calc_net = (ocf + icf + fcf + fx) if (ocf is not None and icf is not None and fcf is not None) else None
        checks.append(check_equality(
            check_id="CF_NET_INCREASE",
            formula_name="Net Increase in Cash Reconciliation",
            formula_description="Operating + Investing + Financing Cash Flow + FX ≈ Net Increase in Cash",
            calculated_value=calc_net,
            reported_value=net_inc,
            operands={"operating_cash_flow": ocf, "investing_cash_flow": icf, "financing_cash_flow": fcf, "fx_adjustment": fx, "reported_net_increase": net_inc},
            not_applicable_reason="Operating, Investing, or Financing cash flows not present."
        ))
        
        calc_closing = (opening + net_inc) if (opening is not None and net_inc is not None) else None
        checks.append(check_equality(
            check_id="CF_CLOSING_CASH",
            formula_name="Closing Cash Balance Reconciliation",
            formula_description="Opening Cash + Net Increase in Cash ≈ Closing Cash",
            calculated_value=calc_closing,
            reported_value=closing,
            operands={"opening_cash": opening, "net_increase": net_inc, "reported_closing_cash": closing},
            not_applicable_reason="Opening or closing cash balances missing."
        ))

    return checks

def perform_financial_validation(doc_type: DocumentType, extracted: ExtractedData) -> DocumentValidationSummary:
    """Dispatches financial validation based on document type and aggregates summary."""
    if doc_type == DocumentType.INVOICE:
        checks = validate_invoice(extracted)
    elif doc_type == DocumentType.BALANCE_SHEET:
        checks = validate_balance_sheet(extracted)
    elif doc_type == DocumentType.PROFIT_AND_LOSS:
        checks = validate_profit_and_loss(extracted)
    elif doc_type == DocumentType.CASH_FLOW_STATEMENT:
        checks = validate_cash_flow(extracted)
    else:
        checks = []
        
    passed = sum(1 for c in checks if c.status == ValidationStatus.PASS)
    failed = sum(1 for c in checks if c.status == ValidationStatus.FAIL)
    not_app = sum(1 for c in checks if c.status == ValidationStatus.NOT_APPLICABLE)
    total = len(checks)
    
    if failed > 0:
        overall = ValidationStatus.FAIL
    elif passed > 0:
        overall = ValidationStatus.PASS
    else:
        overall = ValidationStatus.NOT_APPLICABLE
        
    return DocumentValidationSummary(
        overall_status=overall,
        passed_count=passed,
        failed_count=failed,
        not_applicable_count=not_app,
        total_checks=total,
        checks=checks
    )
