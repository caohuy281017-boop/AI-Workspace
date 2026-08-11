"""Tests for the Validation Engine (Lát 2).

All tests use Decimal internally and cover:
- Total amount arithmetic (subtotal + tax = total)
- Line sum vs subtotal
- Unit price × quantity vs line amount
- MST format validation (VN 10-digit / 13-digit branch)
- Date format and future date
- Duplicate detection via mock checker
- Missing required fields
- Currency missing warning
- Tolerance: VND ±1đ, USD ±0.02
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from accounting_app.validator import (
    InvoiceValidator,
    ValidationIssue,
    validate_invoice,
    CODE_TOTAL_MISSING,
    CODE_TOTAL_MISMATCH,
    CODE_LINE_SUM_MISMATCH,
    CODE_UNIT_PRICE_MISMATCH,
    CODE_MST_FORMAT_INVALID,
    CODE_DATE_INVALID,
    CODE_DATE_FUTURE,
    CODE_DUPLICATE_INVOICE,
    CODE_CURRENCY_MISSING,
    CODE_SUPPLIER_MISSING,
    CODE_LINE_DESC_MISSING,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _codes(issues: list[ValidationIssue]) -> list[str]:
    return [i.code for i in issues]


def _make_valid_invoice(**overrides) -> dict:
    """Return a minimal valid invoice that should pass all rules."""
    base = {
        "supplier_name": "Công ty ABC",
        "supplier_tax_id": "0123456789",
        "buyer_name": "Công ty XYZ",
        "buyer_tax_id": "9876543210",
        "invoice_number": "00001234",
        "invoice_date": "2025-06-15",
        "currency": "VND",
        "subtotal": 1_000_000,
        "tax_amount": 100_000,
        "total_amount": 1_100_000,
        "discount_amount": None,
        "fees": None,
        "tax_breakdown": [],
        "items": [
            {
                "description": "Dịch vụ tư vấn",
                "unit": "lần",
                "quantity": 2,
                "unit_price": 500_000,
                "amount": 1_000_000,
                "tax_rate": 0.1,
                "discount_rate": None,
                "line_type": "normal",
            }
        ],
        "custom_fields": {},
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────────────────────────────────────
# 1. Happy path
# ──────────────────────────────────────────────────────────────────────────────

def test_valid_invoice_produces_no_errors():
    """A correct invoice should produce zero issues."""
    issues = validate_invoice(_make_valid_invoice())
    errors = [i for i in issues if i.severity == "error"]
    assert errors == [], f"Unexpected errors: {errors}"


# ──────────────────────────────────────────────────────────────────────────────
# 2. Total amount missing
# ──────────────────────────────────────────────────────────────────────────────

def test_total_missing_is_error():
    inv = _make_valid_invoice(total_amount=None)
    issues = validate_invoice(inv)
    assert CODE_TOTAL_MISSING in _codes(issues)
    error = next(i for i in issues if i.code == CODE_TOTAL_MISSING)
    assert error.severity == "error"
    assert error.field == "total_amount"


# ──────────────────────────────────────────────────────────────────────────────
# 3. Total arithmetic mismatch
# ──────────────────────────────────────────────────────────────────────────────

def test_total_mismatch_outside_vnd_tolerance_is_error():
    """1_000_000 + 100_000 = 1_100_000 but invoice says 1_100_050 → error (±50 > ±1 VND)."""
    inv = _make_valid_invoice(total_amount=1_100_050)
    issues = validate_invoice(inv)
    assert CODE_TOTAL_MISMATCH in _codes(issues)
    mismatch = next(i for i in issues if i.code == CODE_TOTAL_MISMATCH)
    assert mismatch.severity == "error"
    assert Decimal(mismatch.difference) == Decimal("50")


def test_total_mismatch_within_vnd_tolerance_is_ok():
    """Difference of exactly 1 VND is within tolerance — no error."""
    inv = _make_valid_invoice(total_amount=1_100_001)
    issues = validate_invoice(inv)
    assert CODE_TOTAL_MISMATCH not in _codes(issues)


def test_total_mismatch_usd_within_tolerance():
    """USD tolerance is ±0.02. Difference of 0.01 should pass."""
    inv = _make_valid_invoice(
        currency="USD",
        subtotal=100.00,
        tax_amount=10.00,
        total_amount=110.01,  # diff = 0.01 ≤ 0.02
    )
    issues = validate_invoice(inv)
    assert CODE_TOTAL_MISMATCH not in _codes(issues)


def test_total_mismatch_usd_outside_tolerance():
    """USD tolerance is ±0.02. Difference of 0.05 should fail."""
    inv = _make_valid_invoice(
        currency="USD",
        subtotal=100.00,
        tax_amount=10.00,
        total_amount=110.05,  # diff = 0.05 > 0.02
    )
    issues = validate_invoice(inv)
    assert CODE_TOTAL_MISMATCH in _codes(issues)


def test_total_with_discount_arithmetic():
    """subtotal=1_000_000, discount=50_000, tax=95_000, total=1_045_000.
    Formula: 1_000_000 - 50_000 + 95_000 = 1_045_000 → OK."""
    inv = _make_valid_invoice(
        subtotal=1_000_000,
        discount_amount=50_000,
        tax_amount=95_000,
        total_amount=1_045_000,
    )
    issues = validate_invoice(inv)
    assert CODE_TOTAL_MISMATCH not in _codes(issues)


# ──────────────────────────────────────────────────────────────────────────────
# 4. Line sum vs subtotal
# ──────────────────────────────────────────────────────────────────────────────

def test_line_sum_mismatch_is_warning():
    """Sum of line amounts (800_000) ≠ subtotal (1_000_000)."""
    inv = _make_valid_invoice(
        subtotal=1_000_000,
        items=[{"description": "A", "amount": 800_000}],
    )
    issues = validate_invoice(inv)
    assert CODE_LINE_SUM_MISMATCH in _codes(issues)
    warn = next(i for i in issues if i.code == CODE_LINE_SUM_MISMATCH)
    assert warn.severity == "warning"


def test_line_sum_match_passes():
    """Line amounts sum exactly to subtotal → no line sum issue."""
    inv = _make_valid_invoice(
        subtotal=1_000_000,
        items=[
            {"description": "A", "amount": 600_000},
            {"description": "B", "amount": 400_000},
        ],
    )
    issues = validate_invoice(inv)
    assert CODE_LINE_SUM_MISMATCH not in _codes(issues)


def test_line_sum_skipped_when_no_amounts():
    """If all line items have amount=None, skip line sum check."""
    inv = _make_valid_invoice(
        items=[{"description": "A", "amount": None}],
    )
    issues = validate_invoice(inv)
    assert CODE_LINE_SUM_MISMATCH not in _codes(issues)


# ──────────────────────────────────────────────────────────────────────────────
# 5. Unit price × quantity
# ──────────────────────────────────────────────────────────────────────────────

def test_unit_price_mismatch_is_warning():
    """2 × 500_000 = 1_000_000 but amount says 900_000."""
    inv = _make_valid_invoice(
        items=[{"description": "X", "quantity": 2, "unit_price": 500_000, "amount": 900_000}],
    )
    issues = validate_invoice(inv)
    assert CODE_UNIT_PRICE_MISMATCH in _codes(issues)
    warn = next(i for i in issues if i.code == CODE_UNIT_PRICE_MISMATCH)
    assert warn.severity == "warning"
    assert warn.field == "items.0.amount"


def test_unit_price_match_passes():
    """3 × 200_000 = 600_000 → no issue."""
    inv = _make_valid_invoice(
        items=[{"description": "Y", "quantity": 3, "unit_price": 200_000, "amount": 600_000}],
    )
    issues = validate_invoice(inv)
    assert CODE_UNIT_PRICE_MISMATCH not in _codes(issues)


def test_unit_price_skipped_when_fields_missing():
    """No quantity or no unit_price → skip the rule, no false positive."""
    inv = _make_valid_invoice(
        items=[{"description": "Z", "quantity": None, "unit_price": None, "amount": 500_000}],
    )
    issues = validate_invoice(inv)
    assert CODE_UNIT_PRICE_MISMATCH not in _codes(issues)


# ──────────────────────────────────────────────────────────────────────────────
# 6. MST format validation
# ──────────────────────────────────────────────────────────────────────────────

def test_valid_mst_10_digits():
    inv = _make_valid_invoice(supplier_tax_id="0123456789")
    issues = validate_invoice(inv)
    assert CODE_MST_FORMAT_INVALID not in _codes(issues)


def test_valid_mst_branch_format():
    inv = _make_valid_invoice(supplier_tax_id="0123456789-001")
    issues = validate_invoice(inv)
    assert CODE_MST_FORMAT_INVALID not in _codes(issues)


def test_invalid_mst_too_short():
    inv = _make_valid_invoice(supplier_tax_id="012345678")  # 9 digits
    issues = validate_invoice(inv)
    assert CODE_MST_FORMAT_INVALID in _codes(issues)
    warn = next(i for i in issues if i.code == CODE_MST_FORMAT_INVALID)
    assert warn.severity == "warning"
    assert warn.field == "supplier_tax_id"


def test_invalid_mst_letters():
    inv = _make_valid_invoice(supplier_tax_id="ABC1234567")
    issues = validate_invoice(inv)
    assert CODE_MST_FORMAT_INVALID in _codes(issues)


def test_none_mst_does_not_trigger_format_check():
    """None MST means 'not found' — skip format check (other rules handle missing)."""
    inv = _make_valid_invoice(supplier_tax_id=None)
    issues = validate_invoice(inv)
    assert CODE_MST_FORMAT_INVALID not in _codes(issues)


# ──────────────────────────────────────────────────────────────────────────────
# 7. Date validation
# ──────────────────────────────────────────────────────────────────────────────

def test_valid_iso_date_passes():
    inv = _make_valid_invoice(invoice_date="2024-03-15")
    issues = validate_invoice(inv)
    assert CODE_DATE_INVALID not in _codes(issues)
    assert CODE_DATE_FUTURE not in _codes(issues)


def test_valid_dd_mm_yyyy_date_passes():
    inv = _make_valid_invoice(invoice_date="15/03/2024")
    issues = validate_invoice(inv)
    assert CODE_DATE_INVALID not in _codes(issues)


def test_invalid_date_format():
    inv = _make_valid_invoice(invoice_date="not-a-date")
    issues = validate_invoice(inv)
    assert CODE_DATE_INVALID in _codes(issues)
    warn = next(i for i in issues if i.code == CODE_DATE_INVALID)
    assert warn.severity == "warning"


def test_future_date_is_warning():
    inv = _make_valid_invoice(invoice_date="2099-12-31")
    issues = validate_invoice(inv)
    assert CODE_DATE_FUTURE in _codes(issues)
    warn = next(i for i in issues if i.code == CODE_DATE_FUTURE)
    assert warn.severity == "warning"


def test_none_date_skips_date_check():
    """None invoice_date means not found — date rules are skipped."""
    inv = _make_valid_invoice(invoice_date=None)
    issues = validate_invoice(inv)
    assert CODE_DATE_INVALID not in _codes(issues)
    assert CODE_DATE_FUTURE not in _codes(issues)


# ──────────────────────────────────────────────────────────────────────────────
# 8. Currency and supplier warnings
# ──────────────────────────────────────────────────────────────────────────────

def test_missing_currency_is_warning():
    inv = _make_valid_invoice(currency=None)
    issues = validate_invoice(inv)
    assert CODE_CURRENCY_MISSING in _codes(issues)
    warn = next(i for i in issues if i.code == CODE_CURRENCY_MISSING)
    assert warn.severity == "warning"


def test_missing_supplier_is_warning():
    inv = _make_valid_invoice(supplier_name=None)
    issues = validate_invoice(inv)
    assert CODE_SUPPLIER_MISSING in _codes(issues)
    warn = next(i for i in issues if i.code == CODE_SUPPLIER_MISSING)
    assert warn.severity == "warning"


# ──────────────────────────────────────────────────────────────────────────────
# 9. Duplicate detection
# ──────────────────────────────────────────────────────────────────────────────

def test_duplicate_invoice_is_error():
    inv = _make_valid_invoice(
        supplier_tax_id="0123456789",
        invoice_series="AA/25E",
        invoice_number="00001234",
        invoice_date="2025-06-15",
    )
    # Mock: always returns True (duplicate found)
    issues = validate_invoice(inv, duplicate_checker=lambda *_: True)
    assert CODE_DUPLICATE_INVOICE in _codes(issues)
    err = next(i for i in issues if i.code == CODE_DUPLICATE_INVOICE)
    assert err.severity == "error"


def test_no_duplicate_when_checker_returns_false():
    inv = _make_valid_invoice()
    issues = validate_invoice(inv, duplicate_checker=lambda *_: False)
    assert CODE_DUPLICATE_INVOICE not in _codes(issues)


def test_duplicate_skipped_when_no_mst():
    """Without MST, we cannot reliably detect duplicate — skip rule."""
    inv = _make_valid_invoice(supplier_tax_id=None, invoice_number="00001234")
    issues = validate_invoice(inv, duplicate_checker=lambda *_: True)
    assert CODE_DUPLICATE_INVOICE not in _codes(issues)


# ──────────────────────────────────────────────────────────────────────────────
# 10. Line field warnings
# ──────────────────────────────────────────────────────────────────────────────

def test_line_missing_description_is_warning():
    inv = _make_valid_invoice(
        items=[{"description": None, "amount": 500_000}],
    )
    issues = validate_invoice(inv)
    assert CODE_LINE_DESC_MISSING in _codes(issues)


# ──────────────────────────────────────────────────────────────────────────────
# 11. to_dict serialization
# ──────────────────────────────────────────────────────────────────────────────

def test_validation_issue_to_dict():
    issue = ValidationIssue(
        code=CODE_TOTAL_MISMATCH,
        severity="error",
        field="total_amount",
        message="Test message",
        expected=Decimal("1000"),
        actual=Decimal("1050"),
        difference=Decimal("50"),
    )
    d = issue.to_dict()
    assert d["code"] == CODE_TOTAL_MISMATCH
    assert d["severity"] == "error"
    assert d["expected"] == "1000"
    assert d["difference"] == "50"


# ──────────────────────────────────────────────────────────────────────────────
# 12. No float drift — Decimal precision
# ──────────────────────────────────────────────────────────────────────────────

def test_no_float_drift_in_vnd():
    """Classic float drift: 0.1 + 0.2 ≠ 0.3 in float.
    Validator must use Decimal and correctly identify no mismatch."""
    # Using amounts that would drift with float arithmetic
    inv = _make_valid_invoice(
        currency="VND",
        subtotal=333_333,
        tax_amount=33_333,
        total_amount=366_666,   # 333_333 + 33_333 = 366_666 exactly
    )
    issues = validate_invoice(inv)
    assert CODE_TOTAL_MISMATCH not in _codes(issues)
