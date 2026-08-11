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


from accounting_app.router import classify_document, detect_magic_format
from accounting_app.service import AccountingBatchService, UploadedInvoice
from accounting_app.job_worker import JobWorker
from accounting_app.persistence import SQLiteInvoiceRepository
from accounting_app.pdf_parser import PDFTextParser
from accounting_app.smart_extractor import SmartInvoiceExtractor
from platform_core.domain import ContentBlock, FileReference, ParsedDocument


def test_classify_document_valid_types():
    pdf_res = classify_document("invoice.pdf", "application/pdf", b"%PDF-1.4 sample content")
    assert pdf_res.format == "pdf"
    assert pdf_res.media_type == "application/pdf"
    assert pdf_res.is_image is False

    jpg_res = classify_document("bill.jpg", "image/jpeg", b"\xFF\xD8\xFF\xE0 sample jpeg")
    assert jpg_res.format == "jpeg"
    assert jpg_res.media_type == "image/jpeg"
    assert jpg_res.is_image is True

    png_res = classify_document("doc.png", "image/png", b"\x89PNG\r\n\x1a\n\x00 sample png")
    assert png_res.format == "png"
    assert png_res.media_type == "image/png"
    assert png_res.is_image is True

    webp_res = classify_document("doc.webp", "image/webp", b"RIFF\x00\x00\x00\x00WEBPVP8 sample")
    assert webp_res.format == "webp"
    assert webp_res.media_type == "image/webp"
    assert webp_res.is_image is True

    tiff_res = classify_document("doc.tiff", "image/tiff", b"II*\x00 sample tiff")
    assert tiff_res.format == "tiff"
    assert tiff_res.media_type == "image/tiff"
    assert tiff_res.is_image is True


def test_classify_document_mismatches_rejected():
    # 1. .jpg with PDF bytes
    with pytest.raises(ValueError, match="FILE_TYPE_MISMATCH"):
        classify_document("invoice.jpg", "image/jpeg", b"%PDF-1.4 fake pdf inside jpg")

    # 2. .pdf with JPEG bytes
    with pytest.raises(ValueError, match="FILE_TYPE_MISMATCH"):
        classify_document("invoice.pdf", "application/pdf", b"\xFF\xD8\xFF fake jpg inside pdf")

    # 3. MIME application/pdf with JPG bytes
    with pytest.raises(ValueError, match="FILE_TYPE_MISMATCH"):
        classify_document("invoice.jpg", "application/pdf", b"\xFF\xD8\xFF image bytes")

    # 4. Unknown extension
    with pytest.raises(ValueError, match="FILE_TYPE_MISMATCH"):
        classify_document("invoice.exe", "application/octet-stream", b"MZ fake exe")


class MockParserSpy:
    def __init__(self):
        self.called_count = 0

    def parse(self, source, content):
        self.called_count += 1
        return ParsedDocument(source=source, blocks=(), parser="mock-pdf-parser")


class MockExtractorSpy:
    def extract(self, document, schema_name, schema_version, schema, raw_bytes):
        from platform_core.domain import ExtractionResult
        return ExtractionResult(
            source_file_id=document.source.file_id,
            schema_name=schema_name,
            schema_version=schema_version,
            values={"supplier_name": "Test Co", "total_amount": 1000.0},
            provider="mock-extractor",
            warnings=(),
        )


def test_image_does_not_call_pdf_parser_in_service(tmp_path):
    repo = SQLiteInvoiceRepository(str(tmp_path / "test.db"))
    parser_spy = MockParserSpy()
    service = AccountingBatchService(
        repository=repo,
        storage_dir=tmp_path / "storage",
        parser=parser_spy,
        extractor_factory=lambda *_args, **_kwargs: MockExtractorSpy(),
        allowed_media_types={"image/jpeg": {".jpg", ".jpeg"}, "application/pdf": {".pdf"}},
        max_file_bytes=10 * 1024 * 1024,
    )

    uploads = [
        UploadedInvoice(
            name="receipt.jpg",
            safe_name="receipt.jpg",
            media_type="image/jpeg",
            content=b"\xFF\xD8\xFF\xE0 sample jpeg bytes",
        )
    ]
    batch = service.create_batch(uploads)
    assert len(batch["items"]) == 1
    assert parser_spy.called_count == 0  # CRITICAL: PDF parser was NOT called for image!


def test_pdf_calls_pdf_parser_in_service(tmp_path):
    repo = SQLiteInvoiceRepository(str(tmp_path / "test.db"))
    parser_spy = MockParserSpy()
    service = AccountingBatchService(
        repository=repo,
        storage_dir=tmp_path / "storage",
        parser=parser_spy,
        extractor_factory=lambda *_args, **_kwargs: MockExtractorSpy(),
        allowed_media_types={"application/pdf": {".pdf"}},
        max_file_bytes=10 * 1024 * 1024,
    )

    uploads = [
        UploadedInvoice(
            name="invoice.pdf",
            safe_name="invoice.pdf",
            media_type="application/pdf",
            content=b"%PDF-1.4 sample valid pdf bytes",
        )
    ]
    batch = service.create_batch(uploads)
    assert len(batch["items"]) == 1
    assert parser_spy.called_count == 1  # PDF parser WAS called for valid PDF


def test_sync_service_and_worker_have_consistent_decisions(tmp_path, caplog):
    repo = SQLiteInvoiceRepository(str(tmp_path / "test.db"))
    parser_spy = MockParserSpy()
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    # 1. Process via sync service
    service = AccountingBatchService(
        repository=repo,
        storage_dir=storage_dir,
        parser=parser_spy,
        extractor_factory=lambda *_args, **_kwargs: MockExtractorSpy(),
        allowed_media_types={"image/png": {".png"}},
        max_file_bytes=10 * 1024 * 1024,
    )
    png_bytes = b"\x89PNG\r\n\x1a\n sample png"
    batch = service.create_batch([
        UploadedInvoice(name="photo.png", safe_name="photo.png", media_type="image/png", content=png_bytes)
    ])
    item_id = batch["items"][0]["file_id"]

    # 2. Process via background worker
    worker = JobWorker(
        repository=repo,
        storage_dir=storage_dir,
        parser=parser_spy,
        extractor=MockExtractorSpy(),
        worker_id="test-w1",
    )
    repo.enqueue_job(batch_id=batch["batch_id"], file_id=item_id)
    job = repo.claim_next_job("test-w1")
    assert job is not None
    success = worker.process_job(job)

    assert success is True
    assert parser_spy.called_count == 0  # Both bypassed PDF parser completely!
    assert "PDF parsing failed" not in caplog.text


def test_pdf_exceeding_page_limit_rejected():
    from accounting_app.router import validate_pdf_page_limit
    import io
    import pypdfium2 as pdfium

    # Create a 5-page PDF using pypdfium2
    pdf = pdfium.PdfDocument.new()
    for _ in range(5):
        pdf.new_page(width=100, height=100)
    buf = io.BytesIO()
    pdf.save(buf)
    pdf_5_pages = buf.getvalue()

    # Allowed if max_pages >= 5
    count = validate_pdf_page_limit(pdf_5_pages, max_pages=5)
    assert count == 5

    # Rejected if max_pages < 5
    with pytest.raises(ValueError, match="PAGE_LIMIT_EXCEEDED"):
        classify_document("long_invoice.pdf", "application/pdf", pdf_5_pages, max_pdf_pages=3)


def test_vision_first_always_passes_raw_bytes_for_pdf_and_image():
    from accounting_app.smart_extractor import SmartInvoiceExtractor
    from accounting_app.schema import INVOICE_SCHEMA_V2, SCHEMA_NAME, SCHEMA_VERSION
    from platform_core.domain import ContentBlock, FileReference, ParsedDocument
    from unittest.mock import patch

    extractor = SmartInvoiceExtractor(api_key="test-key", provider="gemini")
    
    # 1. Clean digital PDF with perfect text layer
    pdf_source = FileReference("f1", "ws1", "digital.pdf", "application/pdf", 100, "")
    pdf_doc = ParsedDocument(
        source=pdf_source,
        blocks=(
            ContentBlock(block_id="b1", kind="text", text="CÔNG TY CỔ PHẦN CÔNG NGHỆ ABC MST: 0101234567 HÓA ĐƠN GIÁ TRỊ GIA TĂNG Tổng cộng: 5000000 VND"),
        ),
        parser="pdf-parser",
    )
    mock_pdf_bytes = b"%PDF-1.4 sample digital pdf"

    with patch("accounting_app.smart_extractor._call_gemini_api") as mock_gemini:
        mock_gemini.return_value = {"supplier_name": "ABC", "total_amount": 5000000.0}
        res = extractor.extract(
            pdf_doc,
            schema_name=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            schema=INVOICE_SCHEMA_V2,
            raw_bytes=mock_pdf_bytes,
        )
        assert res.values["supplier_name"] == "ABC"
        assert res.provider.endswith("[Vision]")
        # CRITICAL: raw_bytes was passed to Gemini Multimodal Vision even though text quality is high
        assert mock_gemini.call_args[1]["raw_bytes"] == mock_pdf_bytes
        assert mock_gemini.call_args[1]["media_type"] == "application/pdf"

    # 2. Image receipt
    img_source = FileReference("f2", "ws1", "receipt.jpg", "image/jpeg", 50, "")
    img_doc = ParsedDocument(source=img_source, blocks=(), parser="image-direct")
    mock_jpg_bytes = b"\xFF\xD8\xFF\xE0 sample jpeg"

    with patch("accounting_app.smart_extractor._call_gemini_api") as mock_gemini:
        mock_gemini.return_value = {"supplier_name": "Store XYZ", "total_amount": 50000.0}
        res_img = extractor.extract(
            img_doc,
            schema_name=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            schema=INVOICE_SCHEMA_V2,
            raw_bytes=mock_jpg_bytes,
        )
        assert res_img.values["supplier_name"] == "Store XYZ"
        assert res_img.provider.endswith("[Vision]")
        assert mock_gemini.call_args[1]["raw_bytes"] == mock_jpg_bytes
        assert mock_gemini.call_args[1]["media_type"] == "image/jpeg"

