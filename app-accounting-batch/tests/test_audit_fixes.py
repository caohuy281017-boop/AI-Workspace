"""Tests for the 5 critical audit fixes."""

import pytest
import io
import math
from fastapi.testclient import TestClient
from core_shared.domain import FileReference
from app_accounting_batch.api import create_app
from app_accounting_batch.persistence import SQLiteInvoiceRepository
from app_accounting_batch.smart_extractor import (
    _normalize_extraction_values,
    extract_with_heuristics,
)


def test_no_data_fabrication_heuristics():
    """Verify that unparseable text does NOT fabricate dates like 2026-08-09 or fake totals."""
    empty_text = "[No extractable text found in file test.png]"
    values, warnings = extract_with_heuristics(empty_text, "test.png")

    assert values["invoice_date"] == ""
    assert values["total_amount"] == 0.0
    assert any("Không thể trích xuất chữ" in w or "Chưa nhận diện" in w for w in warnings)


def test_large_identifier_is_not_used_as_total():
    values, warnings = extract_with_heuristics(
        "MST: 0317333953\nSo tai khoan: 1234567890123",
        "invoice.pdf",
    )

    assert values["total_amount"] == 0.0
    assert values["subtotal"] == 0.0
    assert values["tax_amount"] == 0.0
    assert values["items"] == []
    assert warnings


def test_labeled_amounts_are_extracted_without_calculation():
    text = (
        "Tiền trước thuế: 1.000.000\n"
        "Tiền thuế GTGT: 80.000\n"
        "Tổng thanh toán: 1.080.000"
    )

    values, _ = extract_with_heuristics(text, "invoice.pdf")

    assert values["subtotal"] == 1_000_000
    assert values["tax_amount"] == 80_000
    assert values["total_amount"] == 1_080_000
    assert values["items"] == []


def test_invalid_gemini_values_are_normalized_safely():
    values, warnings = _normalize_extraction_values({
        "supplier_name": ["not", "a", "string"],
        "total_amount": "not-a-number",
        "tax_amount": -10,
        "items": "not-a-list",
        "unexpected": "discard me",
    })

    assert values["supplier_name"] == ""
    assert values["total_amount"] == 0.0
    assert values["tax_amount"] == 0.0
    assert values["items"] == []
    assert "unexpected" not in values
    assert warnings


def test_non_finite_gemini_amount_is_rejected():
    values, warnings = _normalize_extraction_values({"total_amount": float("inf")})

    assert values["total_amount"] == 0.0
    assert math.isfinite(values["total_amount"])
    assert warnings


def test_labeled_amount_uses_first_number_after_its_label():
    values, _ = extract_with_heuristics(
        "Subtotal: 1,000,000; invoice number 12345",
        "invoice.pdf",
    )

    assert values["subtotal"] == 1_000_000


def test_overlapping_amount_label_does_not_fill_two_fields():
    values, _ = extract_with_heuristics(
        "Grand total tax amount: 80,000",
        "invoice.pdf",
    )

    assert values["tax_amount"] == 80_000
    assert values["total_amount"] == 0.0


def test_overlapping_vietnamese_label_prefers_the_longer_label():
    values, _ = extract_with_heuristics(
        "Tổng cộng tiền hàng: 1.000.000",
        "invoice.pdf",
    )

    assert values["subtotal"] == 1_000_000
    assert values["total_amount"] == 0.0


def test_later_amount_label_on_the_same_line_is_still_detected():
    values, _ = extract_with_heuristics(
        "Tổng cộng tiền hàng: 1.000.000; Tổng cộng: 1.080.000",
        "invoice.pdf",
    )

    assert values["subtotal"] == 1_000_000
    assert values["total_amount"] == 1_080_000


def test_excel_export_approval_filter_only(tmp_path):
    """Verify that export_batch ONLY exports approved invoices (status == 'approved')."""
    db_file = tmp_path / "test_audit.db"
    repo = SQLiteInvoiceRepository(str(db_file))
    app = create_app(repo)
    client = TestClient(app)

    # Save a batch with 1 approved item and 1 needs_review item
    batch_id = "b-audit-1"
    repo.save_batch(batch_id, [
        {
            "file_id": "f-unapproved",
            "file_name": "unapproved.pdf",
            "status": "needs_review",
            "extraction": {"supplier_name": "Chưa Duyệt Corp", "total_amount": 99999.0},
            "warnings": [],
            "errors": []
        },
        {
            "file_id": "f-approved",
            "file_name": "approved.pdf",
            "status": "approved",
            "extraction": {"supplier_name": "Đã Duyệt Corp", "total_amount": 50000.0},
            "warnings": [],
            "errors": []
        }
    ])

    # Test GET export
    response = client.get(f"/api/v1/accounting/batches/{batch_id}/export.xlsx")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(response.content))
    ws = wb["Invoices"]
    rows = list(ws.iter_rows(values_only=True))
    
    # Rows: 1 header + 1 approved record (unapproved record must NOT be present!)
    assert len(rows) == 2
    assert rows[1][3] == "Đã Duyệt Corp"


def test_excel_export_fails_when_zero_approved(tmp_path):
    """Verify that export API returns 400 when 0 invoices are approved."""
    db_file = tmp_path / "test_audit_zero.db"
    repo = SQLiteInvoiceRepository(str(db_file))
    app = create_app(repo)
    client = TestClient(app)

    batch_id = "b-zero"
    repo.save_batch(batch_id, [
        {
            "file_id": "f-review-only",
            "file_name": "review.pdf",
            "status": "needs_review",
            "extraction": {"supplier_name": "Test", "total_amount": 100.0},
            "warnings": [],
            "errors": []
        }
    ])

    response = client.get(f"/api/v1/accounting/batches/{batch_id}/export.xlsx")
    assert response.status_code == 400
    assert "Không có hóa đơn nào" in response.json()["detail"]


def test_excel_export_excludes_approved_items_with_processing_errors(tmp_path):
    repo = SQLiteInvoiceRepository(str(tmp_path / "test_error_export.db"))
    app = create_app(repo, storage_dir=tmp_path / "storage")
    client = TestClient(app)
    repo.save_batch("b-errors", [{
        "file_id": "f-errors",
        "file_name": "broken.pdf",
        "status": "approved",
        "extraction": {"supplier_name": "Edited", "total_amount": 123.0},
        "warnings": [],
        "errors": ["parse failed"],
    }])

    response = client.get("/api/v1/accounting/batches/b-errors/export.xlsx")

    assert response.status_code == 400
