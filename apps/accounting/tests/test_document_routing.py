"""Unit tests for Document Routing (Lát 5).

Tests text quality scoring and model routing:
- Clean digital PDF text -> text_only
- Scanned PDF / images -> multimodal_vision
- Corrupted/garbage text -> multimodal_vision
- Short text (<50 chars) -> multimodal_vision
- Keyword recognition in Vietnamese & English
"""

from __future__ import annotations

import pytest

from accounting_app.router import (
    DocumentRoutingDecision,
    assess_text_quality,
)


def test_clean_digital_vietnamese_invoice_routes_to_text_only():
    """A clean electronic invoice with all standard markers should route to text_only."""
    sample_text = """
    CÔNG TY CỔ PHẦN CÔNG NGHỆ VÀ TRUYỀN THÔNG ABC
    Mã số thuế: 0101234567
    Địa chỉ: Tầng 5, Tòa nhà Landmark, Hà Nội
    
    HÓA ĐƠN GIÁ TRỊ GIA TĂNG (VAT)
    Ký hiệu: 1C26TAP - Số: 00008228
    Ngày 15 tháng 06 năm 2025
    
    Tên người mua: CÔNG TY TNHH THƯƠNG MẠI XYZ
    Mã số thuế người mua: 0317333953
    
    STT | Tên hàng hóa, dịch vụ | ĐVT | Số lượng | Đơn giá | Thành tiền
    1   | Dịch vụ phần mềm đám mây | Tháng | 1 | 5.000.000 | 5.000.000
    2   | Phí hỗ trợ kỹ thuật 24/7 | Gói   | 1 | 1.000.000 | 1.000.000
    
    Cộng tiền hàng: 6.000.000 VND
    Thuế suất GTGT: 10% - Tiền thuế GTGT: 600.000 VND
    Tổng cộng tiền thanh toán: 6.600.000 VND
    """
    decision = assess_text_quality(sample_text, media_type="application/pdf", filename="inv_001.pdf")

    assert decision.mode == "text_only"
    assert decision.text_quality_score >= 0.70
    assert decision.has_scanned_indicator is False
    assert decision.char_count > 200
    assert decision.printable_ratio > 0.90


def test_clean_english_invoice_routes_to_text_only():
    sample_text = """
    ACME CORPORATION PTE LTD
    Tax ID / VAT: 9988776655
    123 Technology Drive, Singapore
    
    TAX INVOICE
    Invoice Number: INV-2025-0899
    Date: 2025-07-20
    
    Bill To: Global Logistics Inc
    Tax Code: 1122334455
    
    Description | Quantity | Unit Price | Amount
    Cloud Hosting Subscription | 1 | 1200.00 | 1200.00
    
    Subtotal: $1,200.00
    Tax Amount (8%): $96.00
    Total Amount: $1,296.00
    Currency: USD
    """
    decision = assess_text_quality(sample_text, media_type="application/pdf", filename="invoice.pdf")

    assert decision.mode == "text_only"
    assert decision.text_quality_score >= 0.70
    assert decision.has_scanned_indicator is False


def test_image_file_always_routes_to_vision():
    """Any image input (PNG, JPG, TIFF) must route to multimodal_vision."""
    dummy_text = "Some short text recognized by OCR"
    decision = assess_text_quality(dummy_text, media_type="image/png", filename="bill.png")

    assert decision.mode == "multimodal_vision"
    assert decision.has_scanned_indicator is True


def test_empty_or_scan_marker_routes_to_vision():
    empty_text = "[No extractable text found in file scan.pdf]"
    decision = assess_text_quality(empty_text, media_type="application/pdf", filename="scan.pdf")

    assert decision.mode == "multimodal_vision"
    assert decision.text_quality_score < 0.20
    assert decision.has_scanned_indicator is True


def test_none_text_routes_to_vision():
    decision = assess_text_quality(None, media_type="application/pdf", filename="blank.pdf")
    assert decision.mode == "multimodal_vision"
    assert decision.text_quality_score == 0.0


def test_short_unclear_text_routes_to_vision():
    """Text under 50 characters is too short to be a valid invoice text layer."""
    short_text = "Page 1 of 1 / Scanned by CamScanner"
    decision = assess_text_quality(short_text, media_type="application/pdf", filename="cam.pdf")

    assert decision.mode == "multimodal_vision"
    assert decision.text_quality_score < 0.70


def test_corrupted_ocr_control_chars_routes_to_vision():
    """Text with excessive control/unprintable characters should be downgraded to vision."""
    corrupted_text = "Hóa đơn \x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\x10\x11\x12 tiền hàng \x13\x14\x15"
    decision = assess_text_quality(corrupted_text, media_type="application/pdf", filename="corrupt.pdf")

    assert decision.mode == "multimodal_vision"
    assert decision.text_quality_score < 0.70


def test_routing_decision_to_dict_serialization():
    decision = DocumentRoutingDecision(
        mode="text_only",
        text_quality_score=0.92345,
        char_count=450,
        printable_ratio=0.99,
        keyword_density=0.8,
        has_scanned_indicator=False,
        reason="Clean electronic PDF",
    )
    d = decision.to_dict()
    assert d["mode"] == "text_only"
    assert d["text_quality_score"] == 0.923
    assert d["char_count"] == 450
    assert d["has_scanned_indicator"] is False
