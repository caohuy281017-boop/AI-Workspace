"""Invoice Validation Engine.

Pure business logic — no FastAPI, no SQLite, no I/O dependencies.
Designed to be called from service.py after extraction and on every PATCH.

Architecture:
- ValidationIssue: structured error/warning/info record
- InvoiceValidator: runs all validation rules and returns a list of issues
- validate_invoice(): convenience entry point

NULL POLICY: Fields that are None are treated as "not found in document".
Some rules require a field — if it is None, the rule generates a specific
MISSING_* warning rather than a false arithmetic error.

Financial Precision:
- All monetary comparisons use Decimal (never float) to avoid floating-point drift.
- VND: tolerance ±1đ (no sub-unit)
- Other currencies: tolerance ±0.02 of the stated unit

MST Validation:
- Vietnamese tax codes: 10 digits (company) or 13 digits "XXXXXXXXXX-XXX" (branch)
- No algorithmic checksum enforced here (Bộ Tài chính format only)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Tolerance constants
# ---------------------------------------------------------------------------

_VND_TOLERANCE = Decimal("1")        # ±1 VND
_DEFAULT_TOLERANCE = Decimal("0.02") # ±0.02 for USD/EUR/etc.

# ---------------------------------------------------------------------------
# Error codes — stable identifiers used by frontend and audit log
# ---------------------------------------------------------------------------

CODE_TOTAL_MISSING          = "TOTAL_MISSING"
CODE_TOTAL_MISMATCH         = "TOTAL_MISMATCH"
CODE_LINE_SUM_MISMATCH      = "LINE_SUM_MISMATCH"
CODE_UNIT_PRICE_MISMATCH    = "UNIT_PRICE_MISMATCH"
CODE_MST_FORMAT_INVALID     = "MST_FORMAT_INVALID"
CODE_DATE_INVALID           = "DATE_INVALID"
CODE_DATE_FUTURE            = "DATE_FUTURE"
CODE_DUPLICATE_INVOICE      = "DUPLICATE_INVOICE"
CODE_CURRENCY_MISSING       = "CURRENCY_MISSING"
CODE_SUPPLIER_MISSING       = "SUPPLIER_MISSING"
CODE_ITEMS_EMPTY            = "ITEMS_EMPTY"
CODE_LINE_AMOUNT_MISSING    = "LINE_AMOUNT_MISSING"
CODE_LINE_DESC_MISSING      = "LINE_DESC_MISSING"


# ---------------------------------------------------------------------------
# ValidationIssue
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    """A single validation finding on an invoice.

    Attributes:
        code:       Stable identifier for the rule that fired (CODE_* constants).
        severity:   "error" → blocks export unless overridden with reason.
                    "warning" → shown but does not block export.
                    "info"    → informational only.
        field:      Dot-path of the field involved ("total_amount", "items.2.amount", …).
                    None when the issue spans the whole invoice.
        message:    Human-readable explanation in Vietnamese for the accounting user.
        expected:   The value the validator expected (for display in UI tooltip).
        actual:     The value extracted from the document.
        difference: Numeric difference when applicable, else None.
    """
    code: str
    severity: str               # "error" | "warning" | "info"
    field: Optional[str]
    message: str
    expected: Any = None
    actual: Any = None
    difference: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
            "expected": str(self.expected) if self.expected is not None else None,
            "actual": str(self.actual) if self.actual is not None else None,
            "difference": str(self.difference) if self.difference is not None else None,
        }


# ---------------------------------------------------------------------------
# MST format validation
# ---------------------------------------------------------------------------

_MST_COMPANY_RE = re.compile(r'^\d{10}$')
_MST_BRANCH_RE  = re.compile(r'^\d{10}-\d{3}$')

def _is_valid_mst(mst: str) -> bool:
    """Return True if mst matches Vietnamese tax code format (10 or 13 digits)."""
    mst = mst.strip()
    return bool(_MST_COMPANY_RE.match(mst) or _MST_BRANCH_RE.match(mst))


# ---------------------------------------------------------------------------
# Decimal helpers
# ---------------------------------------------------------------------------

def _to_decimal(val: Any) -> Optional[Decimal]:
    """Convert a float/int/str to Decimal, or return None if not convertible."""
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except InvalidOperation:
        return None


def _tolerance_for(currency: Optional[str]) -> Decimal:
    """Return the acceptable arithmetic tolerance for the given currency."""
    if currency and currency.upper() == "VND":
        return _VND_TOLERANCE
    return _DEFAULT_TOLERANCE


# ---------------------------------------------------------------------------
# InvoiceValidator
# ---------------------------------------------------------------------------

class InvoiceValidator:
    """Run all validation rules on a single extracted invoice dict.

    Usage:
        issues = InvoiceValidator().validate(extraction_dict)

    The extraction_dict is the normalized dict produced by
    _normalize_extraction_values() in smart_extractor.py.

    Duplicate detection requires a lookup callback; pass it via
    set_duplicate_checker().
    """

    def __init__(self) -> None:
        self._duplicate_checker: Optional[Any] = None  # callable or None

    def set_duplicate_checker(self, checker: Any) -> None:
        """Set a callable(supplier_tax_id, invoice_series, invoice_number, invoice_date)
        that returns True when a matching invoice already exists in the database.
        """
        self._duplicate_checker = checker

    # ── Public entry point ────────────────────────────────────────────────

    def validate(self, data: dict[str, Any]) -> list[ValidationIssue]:
        """Run all rules and return a list of ValidationIssue objects."""
        issues: list[ValidationIssue] = []
        currency = data.get("currency")
        tolerance = _tolerance_for(currency)

        self._check_total_present(data, issues)
        self._check_supplier(data, issues)
        self._check_currency(data, issues)
        self._check_date(data, issues)
        self._check_mst(data, "supplier_tax_id", issues)
        self._check_mst(data, "buyer_tax_id", issues)
        self._check_total_arithmetic(data, tolerance, issues)
        self._check_line_sum(data, tolerance, issues)
        self._check_line_unit_price(data, tolerance, issues)
        self._check_line_fields(data, issues)
        self._check_duplicate(data, issues)

        return issues

    # ── Individual rules ──────────────────────────────────────────────────

    @staticmethod
    def _check_total_present(data: dict[str, Any], issues: list[ValidationIssue]) -> None:
        if data.get("total_amount") is None:
            issues.append(ValidationIssue(
                code=CODE_TOTAL_MISSING,
                severity="error",
                field="total_amount",
                message="Không tìm thấy tổng tiền thanh toán. Vui lòng nhập thủ công.",
            ))

    @staticmethod
    def _check_supplier(data: dict[str, Any], issues: list[ValidationIssue]) -> None:
        if not data.get("supplier_name"):
            issues.append(ValidationIssue(
                code=CODE_SUPPLIER_MISSING,
                severity="warning",
                field="supplier_name",
                message="Không đọc được tên nhà cung cấp.",
            ))

    @staticmethod
    def _check_currency(data: dict[str, Any], issues: list[ValidationIssue]) -> None:
        if data.get("currency") is None:
            issues.append(ValidationIssue(
                code=CODE_CURRENCY_MISSING,
                severity="warning",
                field="currency",
                message="Không xác định được đơn vị tiền tệ. Vui lòng kiểm tra và bổ sung.",
            ))

    @staticmethod
    def _check_date(data: dict[str, Any], issues: list[ValidationIssue]) -> None:
        raw = data.get("invoice_date")
        if raw is None:
            return  # DATE_MISSING is not enforced — optional field
        # Attempt ISO 8601 parse
        parsed: Optional[date] = None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
            try:
                parsed = datetime.strptime(raw, fmt).date()
                break
            except ValueError:
                continue
        if parsed is None:
            issues.append(ValidationIssue(
                code=CODE_DATE_INVALID,
                severity="warning",
                field="invoice_date",
                message=f"Ngày hóa đơn '{raw}' không đúng định dạng (cần YYYY-MM-DD hoặc DD/MM/YYYY).",
                actual=raw,
            ))
            return
        if parsed > date.today():
            issues.append(ValidationIssue(
                code=CODE_DATE_FUTURE,
                severity="warning",
                field="invoice_date",
                message=f"Ngày hóa đơn ({raw}) nằm trong tương lai — kiểm tra lại.",
                actual=raw,
                expected=f"≤ {date.today().isoformat()}",
            ))

    @staticmethod
    def _check_mst(data: dict[str, Any], field_key: str, issues: list[ValidationIssue]) -> None:
        mst = data.get(field_key)
        if mst is None:
            return  # Not present — handled by other rules if needed
        if not _is_valid_mst(str(mst)):
            label = "MST nhà cung cấp" if field_key == "supplier_tax_id" else "MST người mua"
            issues.append(ValidationIssue(
                code=CODE_MST_FORMAT_INVALID,
                severity="warning",
                field=field_key,
                message=f"{label} '{mst}' không đúng định dạng VN (10 số hoặc 10-3 số cho chi nhánh).",
                actual=mst,
                expected="XXXXXXXXXX hoặc XXXXXXXXXX-XXX",
            ))

    @staticmethod
    def _check_total_arithmetic(
        data: dict[str, Any],
        tolerance: Decimal,
        issues: list[ValidationIssue],
    ) -> None:
        """Check: subtotal + tax_amount ≈ total_amount (within tolerance)."""
        subtotal = _to_decimal(data.get("subtotal"))
        tax = _to_decimal(data.get("tax_amount"))
        total = _to_decimal(data.get("total_amount"))
        discount = _to_decimal(data.get("discount_amount")) or Decimal("0")
        fees = _to_decimal(data.get("fees")) or Decimal("0")

        if subtotal is None or tax is None or total is None:
            return  # Cannot compute — missing operand(s)

        expected_total = subtotal - discount + fees + tax
        diff = abs(total - expected_total)

        if diff > tolerance:
            issues.append(ValidationIssue(
                code=CODE_TOTAL_MISMATCH,
                severity="error",
                field="total_amount",
                message=(
                    f"Tổng tiền không khớp: tiền hàng ({subtotal:,}) "
                    f"- chiết khấu ({discount:,}) + phí ({fees:,}) + thuế ({tax:,}) "
                    f"= {expected_total:,}, nhưng trích xuất được {total:,} "
                    f"(chênh lệch {diff:,})."
                ),
                expected=str(expected_total),
                actual=str(total),
                difference=str(diff),
            ))

    @staticmethod
    def _check_line_sum(
        data: dict[str, Any],
        tolerance: Decimal,
        issues: list[ValidationIssue],
    ) -> None:
        """Check: sum of line item amounts ≈ subtotal (within tolerance)."""
        subtotal = _to_decimal(data.get("subtotal"))
        items = data.get("items")
        if subtotal is None or not items:
            return

        line_total = Decimal("0")
        any_amount = False
        for it in items:
            amt = _to_decimal(it.get("amount"))
            if amt is not None:
                any_amount = True
                line_total += amt

        if not any_amount:
            return  # No line amounts to sum

        diff = abs(line_total - subtotal)
        if diff > tolerance:
            issues.append(ValidationIssue(
                code=CODE_LINE_SUM_MISMATCH,
                severity="warning",
                field="items",
                message=(
                    f"Tổng thành tiền các dòng hàng ({line_total:,}) "
                    f"≠ tiền trước thuế ({subtotal:,}) "
                    f"(chênh lệch {diff:,})."
                ),
                expected=str(subtotal),
                actual=str(line_total),
                difference=str(diff),
            ))

    @staticmethod
    def _check_line_unit_price(
        data: dict[str, Any],
        tolerance: Decimal,
        issues: list[ValidationIssue],
    ) -> None:
        """Check: quantity × unit_price ≈ amount for each line (within tolerance)."""
        items = data.get("items")
        if not items:
            return

        for idx, it in enumerate(items):
            qty   = _to_decimal(it.get("quantity"))
            price = _to_decimal(it.get("unit_price"))
            amt   = _to_decimal(it.get("amount"))

            if qty is None or price is None or amt is None:
                continue  # Cannot verify — missing operand

            expected_amt = (qty * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            diff = abs(amt - expected_amt)

            if diff > tolerance:
                desc = it.get("description") or f"dòng {idx + 1}"
                issues.append(ValidationIssue(
                    code=CODE_UNIT_PRICE_MISMATCH,
                    severity="warning",
                    field=f"items.{idx}.amount",
                    message=(
                        f"'{desc}': {qty} × {price:,} = {expected_amt:,}, "
                        f"nhưng thành tiền ghi {amt:,} (chênh lệch {diff:,})."
                    ),
                    expected=str(expected_amt),
                    actual=str(amt),
                    difference=str(diff),
                ))

    @staticmethod
    def _check_line_fields(data: dict[str, Any], issues: list[ValidationIssue]) -> None:
        """Warn on line items where critical fields are missing."""
        items = data.get("items")
        if not items:
            return

        for idx, it in enumerate(items):
            if it.get("description") is None:
                issues.append(ValidationIssue(
                    code=CODE_LINE_DESC_MISSING,
                    severity="warning",
                    field=f"items.{idx}.description",
                    message=f"Dòng hàng {idx + 1}: không đọc được tên hàng hóa/dịch vụ.",
                ))
            if it.get("amount") is None:
                issues.append(ValidationIssue(
                    code=CODE_LINE_AMOUNT_MISSING,
                    severity="info",
                    field=f"items.{idx}.amount",
                    message=f"Dòng hàng {idx + 1}: không đọc được thành tiền.",
                ))

    def _check_duplicate(self, data: dict[str, Any], issues: list[ValidationIssue]) -> None:
        """Detect duplicate invoice: same supplier MST + series + number + date."""
        if self._duplicate_checker is None:
            return

        mst    = data.get("supplier_tax_id")
        series = data.get("invoice_series")
        number = data.get("invoice_number")
        dt     = data.get("invoice_date")

        # Need at least MST + number to check duplicate meaningfully
        if not mst or not number:
            return

        if self._duplicate_checker(mst, series, number, dt):
            issues.append(ValidationIssue(
                code=CODE_DUPLICATE_INVOICE,
                severity="error",
                field="invoice_number",
                message=(
                    f"Trùng hóa đơn: MST {mst}, ký hiệu '{series}', "
                    f"số '{number}', ngày '{dt}' đã có trong hệ thống."
                ),
                actual=f"{mst}/{series}/{number}/{dt}",
            ))


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def validate_invoice(
    data: dict[str, Any],
    duplicate_checker: Optional[Any] = None,
) -> list[ValidationIssue]:
    """Validate a single extracted invoice dict.

    Args:
        data: Normalized extraction dict from _normalize_extraction_values().
        duplicate_checker: Optional callable(mst, series, number, date) → bool.

    Returns:
        List of ValidationIssue (may be empty if all checks pass).
    """
    validator = InvoiceValidator()
    if duplicate_checker:
        validator.set_duplicate_checker(duplicate_checker)
    return validator.validate(data)
