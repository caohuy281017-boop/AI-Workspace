"""Tests for real Accounting Batch components."""

import pytest
from platform_core.domain import FileReference
from accounting_app.pdf_parser import PDFTextParser
from accounting_app.smart_extractor import extract_with_heuristics, SmartInvoiceExtractor
from accounting_app.persistence import SQLiteInvoiceRepository
from accounting_app.schema import INVOICE_SCHEMA_V1, SCHEMA_VERSION


def test_pdf_text_parser(tmp_path):
    ref = FileReference("f1", "ws1", "test.pdf", "application/pdf", 100, "uri1")
    parser = PDFTextParser()
    doc = parser.parse(ref, b"Hello PDF Invoice Content\nTotal: 1,650,000 VND\nMST: 0101234567")

    assert doc.source.file_id == "f1"
    assert len(doc.blocks) >= 1
    assert "1,650,000" in doc.blocks[0].text


def test_binary_pdf_is_never_decoded_as_plain_text():
    ref = FileReference("f-binary", "ws1", "scan.pdf", "application/pdf", 32, "uri")
    doc = PDFTextParser().parse(ref, b"%PDF-1.4\x00\xff 1966-2.1 00002559")

    assert doc.parser == "unreadable-document"
    assert doc.blocks[0].text.startswith("[No extractable text found")
    assert "%PDF" not in doc.blocks[0].text


def test_image_bytes_are_never_decoded_as_plain_text():
    ref = FileReference("f-image", "ws1", "scan.jpg", "image/jpeg", 24, "uri")
    doc = PDFTextParser().parse(ref, b"\xff\xd8\xff fake invoice 12345")

    assert doc.parser == "unreadable-document"
    assert doc.blocks[0].text.startswith("[No extractable text found")


def test_extract_with_heuristics():
    text = "HOA DON MAI LINH\nMST: 0101234567\nTong tien: 1.650.000 VND\nNgay: 01/08/2026"
    values, warnings = extract_with_heuristics(text, "HOA_DON_MAI_LINH.pdf")

    assert values["supplier_tax_id"] == "0101234567"
    assert values["total_amount"] == 1650000.0
    assert values["currency"] == "VND"


def test_sqlite_repository(tmp_path):
    db_file = tmp_path / "test_acc.db"
    repo = SQLiteInvoiceRepository(str(db_file))

    batch = repo.save_batch("b-100", [
        {
            "file_id": "f-1",
            "file_name": "inv1.pdf",
            "status": "needs_review",
            "extraction": {"total_amount": 500.0, "currency": "USD"},
            "warnings": [],
            "errors": []
        }
    ])

    assert batch["batch_id"] == "b-100"
    assert len(batch["items"]) == 1
    assert batch["items"][0]["extraction"]["total_amount"] == 500.0

    # Test update
    updated = repo.update_item("b-100", "f-1", {"status": "approved", "total_amount": 550.0})
    assert updated["status"] == "approved"
    assert updated["extraction"]["total_amount"] == 550.0

    # Reload from DB to verify persistence
    reloaded = repo.get_batch("b-100")
    assert reloaded["items"][0]["status"] == "approved"
    assert reloaded["items"][0]["extraction"]["total_amount"] == 550.0
