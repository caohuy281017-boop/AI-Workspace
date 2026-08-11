"""Regression tests for bounded uploads and safe original-file storage."""

from pathlib import Path

from fastapi.testclient import TestClient

from accounting_app.api import (
    MAX_BATCH_FILES,
    MAX_FILE_BYTES,
    create_app,
    sanitize_upload_name,
)
from accounting_app.persistence import SQLiteInvoiceRepository
from platform_core.domain import ContentBlock, ExtractionResult, ParsedDocument


class SelectiveParser:
    def parse(self, source, content):
        if source.name == "bad.pdf":
            raise ValueError("broken document")
        return ParsedDocument(
            source=source,
            blocks=(ContentBlock("b1", "text", text="Tổng thanh toán: 100.000"),),
            parser="test-parser",
        )


class FixedExtractor:
    def extract(self, document, **kwargs):
        return ExtractionResult(
            source_file_id=document.source.file_id,
            schema_name="invoice_schema",
            schema_version="1.0",
            values={"supplier_name": "Test", "total_amount": 100_000.0, "items": []},
            provider="test-extractor",
            warnings=(),
        )


def make_client(tmp_path, *, parser=None, extractor=None):
    repo = SQLiteInvoiceRepository(str(tmp_path / "test.db"))
    app = create_app(
        repo,
        storage_dir=tmp_path / "storage",
        parser=parser,
        extractor=extractor,
    )
    return TestClient(app), repo


def test_rejects_more_than_maximum_batch_files(tmp_path):
    client, _ = make_client(tmp_path)
    files = [
        ("files", (f"invoice-{index}.pdf", b"pdf", "application/pdf"))
        for index in range(MAX_BATCH_FILES + 1)
    ]

    response = client.post("/api/v1/accounting/batches", files=files)

    assert response.status_code == 400


def test_unsupported_media_type_is_an_error_item_and_is_not_stored(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.post(
        "/api/v1/accounting/batches",
        files=[("files", ("malware.exe", b"MZ", "application/x-msdownload"))],
    )

    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["errors"]
    assert list((tmp_path / "storage").iterdir()) == []


def test_missing_media_type_is_not_assumed_to_be_pdf(tmp_path):
    client, _ = make_client(tmp_path)
    boundary = "----missing-content-type"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="unknown.pdf"\r\n'
        "\r\n"
        "pdf\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    response = client.post(
        "/api/v1/accounting/batches",
        content=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    assert response.status_code == 201
    assert response.json()["items"][0]["errors"]


def test_oversized_file_is_an_error_item(tmp_path):
    client, _ = make_client(tmp_path)
    content = b"x" * (MAX_FILE_BYTES + 1)

    response = client.post(
        "/api/v1/accounting/batches",
        files=[("files", ("large.pdf", content, "application/pdf"))],
    )

    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["errors"]
    assert item["size_bytes"] == len(content)
    assert list((tmp_path / "storage").iterdir()) == []


def test_sanitize_upload_name_removes_directory_components():
    safe_name = sanitize_upload_name(r"..\..\secret folder\invoice?.pdf")

    assert "/" not in safe_name
    assert "\\" not in safe_name
    assert ".." not in safe_name
    assert safe_name.endswith(".pdf")


def test_bad_file_does_not_prevent_good_file_processing(tmp_path):
    client, _ = make_client(tmp_path, parser=SelectiveParser(), extractor=FixedExtractor())

    response = client.post(
        "/api/v1/accounting/batches",
        files=[
            ("files", ("bad.pdf", b"bad", "application/pdf")),
            ("files", ("good.pdf", b"good", "application/pdf")),
        ],
    )

    assert response.status_code == 201
    items = {item["file_name"]: item for item in response.json()["items"]}
    assert items["bad.pdf"]["errors"]
    assert items["good.pdf"]["errors"] == []
    assert items["good.pdf"]["extraction"]["total_amount"] == 100_000.0


def test_original_file_is_downloaded_from_configured_storage(tmp_path):
    client, repo = make_client(tmp_path, parser=SelectiveParser(), extractor=FixedExtractor())
    content = b"original invoice bytes"

    upload = client.post(
        "/api/v1/accounting/batches",
        files=[("files", (r"..\invoice.pdf", content, "application/pdf"))],
    )
    item = upload.json()["items"][0]
    stored = repo.get_item(item["file_id"])

    assert stored is not None
    storage_path = Path(stored["storage_uri"]).resolve()
    assert storage_path.is_relative_to((tmp_path / "storage").resolve())

    download = client.get(f"/api/v1/accounting/files/{item['file_id']}")
    assert download.status_code == 200
    assert download.content == content
    assert download.headers["content-disposition"].startswith("inline;")

    attachment = client.get(
        f"/api/v1/accounting/files/{item['file_id']}?download=true"
    )
    assert attachment.headers["content-disposition"].startswith("attachment;")


def test_invalid_status_is_rejected_by_api(tmp_path):
    client, repo = make_client(tmp_path)
    repo.save_batch("batch-status", [{
        "file_id": "file-status",
        "file_name": "status.pdf",
        "status": "needs_review",
        "extraction": {},
        "warnings": [],
        "errors": [],
    }])

    response = client.patch(
        "/api/v1/accounting/batches/batch-status/items/file-status",
        json={"status": "anything"},
    )

    assert response.status_code == 422


def test_default_app_paths_can_be_redirected_for_test_isolation(tmp_path, monkeypatch):
    db_path = tmp_path / "isolated.db"
    storage_path = tmp_path / "isolated-storage"
    monkeypatch.setenv("ACCOUNTING_DB_PATH", str(db_path))
    monkeypatch.setenv("ACCOUNTING_STORAGE_DIR", str(storage_path))

    create_app()

    assert db_path.exists()
    assert storage_path.is_dir()
