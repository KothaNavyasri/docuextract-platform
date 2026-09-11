import pytest
from backend.app.schemas.document import DocumentType, ExtractedData, LineItem, ExtractedField
from backend.app.schemas.validation import ValidationStatus
from backend.app.services.financial_validator import perform_financial_validation

def test_invoice_validation_pass():
    extracted = ExtractedData(
        summary_fields={
            "subtotal": ExtractedField(value=100.0),
            "taxable_amount": ExtractedField(value=100.0),
            "total_tax_amount": ExtractedField(value=10.0),
            "total_amount": ExtractedField(value=110.0),
            "cash_paid": ExtractedField(value=120.0),
            "change_due": ExtractedField(value=10.0)
        },
        line_items=[
            LineItem(item_description="Widget A", quantity=2.0, unit_price=50.0, line_total=100.0)
        ]
    )
    summary = perform_financial_validation(DocumentType.INVOICE, extracted)
    assert summary.overall_status == ValidationStatus.PASS
    assert summary.failed_count == 0
    assert summary.passed_count >= 3

def test_invoice_validation_fail_variance():
    extracted = ExtractedData(
        summary_fields={
            "subtotal": ExtractedField(value=100.0),
            "total_tax_amount": ExtractedField(value=10.0),
            "total_amount": ExtractedField(value=150.0),  # Intentionally incorrect: 100 + 10 != 150
        },
        line_items=[
            LineItem(item_description="Widget A", quantity=2.0, unit_price=50.0, line_total=100.0)
        ]
    )
    summary = perform_financial_validation(DocumentType.INVOICE, extracted)
    assert summary.overall_status == ValidationStatus.FAIL
    assert summary.failed_count >= 1

def test_invoice_validation_not_applicable_when_missing():
    extracted = ExtractedData(
        summary_fields={
            "total_amount": ExtractedField(value=100.0)
        }
    )
    summary = perform_financial_validation(DocumentType.INVOICE, extracted)
    assert summary.overall_status == ValidationStatus.NOT_APPLICABLE
    assert summary.not_applicable_count > 0

def test_balance_sheet_validation_pass():
    extracted = ExtractedData(
        tables={
            "balance_sheet_periods": [
                {
                    "period": "2026",
                    "total_assets": 5000000.0,
                    "total_capital_and_liabilities": 5000000.0,
                    "current_assets": 2000000.0,
                    "non_current_assets": 3000000.0
                },
                {
                    "period": "2025",
                    "total_assets": 4200000.0,
                    "total_capital_and_liabilities": 4200000.0
                }
            ]
        }
    )
    summary = perform_financial_validation(DocumentType.BALANCE_SHEET, extracted)
    assert summary.overall_status == ValidationStatus.PASS
    assert summary.failed_count == 0
    assert summary.passed_count >= 2

def test_balance_sheet_validation_fail():
    extracted = ExtractedData(
        tables={
            "balance_sheet_periods": [
                {
                    "period": "2026",
                    "total_assets": 5000000.0,
                    "total_capital_and_liabilities": 4500000.0 # 5M != 4.5M
                }
            ]
        }
    )
    summary = perform_financial_validation(DocumentType.BALANCE_SHEET, extracted)
    assert summary.overall_status == ValidationStatus.FAIL
    assert summary.failed_count == 1

def test_profit_and_loss_validation_pass():
    extracted = ExtractedData(
        tables={
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
            ]
        }
    )
    summary = perform_financial_validation(DocumentType.PROFIT_AND_LOSS, extracted)
    assert summary.overall_status == ValidationStatus.PASS
    assert summary.failed_count == 0
    assert summary.passed_count == 4

def test_cash_flow_validation_pass_with_negatives():
    extracted = ExtractedData(
        tables={
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
            ]
        }
    )
    summary = perform_financial_validation(DocumentType.CASH_FLOW_STATEMENT, extracted)
    assert summary.overall_status == ValidationStatus.PASS
    assert summary.failed_count == 0
    assert summary.passed_count == 2
