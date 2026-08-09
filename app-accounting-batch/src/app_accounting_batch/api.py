"""FastAPI Web API for app-accounting-batch.

Provides production-hardened REST endpoints for:
  - Batch upload & processing of invoice files with per-file error isolation
  - Gemini AI / Smart extraction (no data fabrication)
  - Raw file persistence in data/storage/ and SQLite metadata store
  - Strict Excel export filter: ONLY approved (status == 'approved') records are exported
  - Raw document download via GET /api/v1/accounting/files/{file_id}
"""

from __future__ import annotations

import io
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Header, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from core_shared.domain import FileReference
from core_shared.adapters.exporters.xlsx_exporter import XLSXExportAdapter
from app_accounting_batch.schema import INVOICE_SCHEMA_V1, SCHEMA_VERSION
from app_accounting_batch.pdf_parser import PDFTextParser
from app_accounting_batch.smart_extractor import SmartInvoiceExtractor
from app_accounting_batch.persistence import SQLiteInvoiceRepository

logger = logging.getLogger(__name__)

DEFAULT_STORAGE_DIR = Path("data/storage")
MAX_BATCH_FILES = 20
MAX_FILE_BYTES = 20 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {
    "application/pdf": {".pdf"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/tiff": {".tif", ".tiff"},
}


def sanitize_upload_name(name: str) -> str:
    """Return a safe basename suitable for server-controlled storage."""
    basename = name.replace("\\", "/").rsplit("/", 1)[-1]
    sanitized = "".join(
        char if (char.isalnum() or char in {".", "_", "-"}) else "_"
        for char in basename
        if ord(char) >= 32
    )
    sanitized = sanitized.lstrip(".")
    while ".." in sanitized:
        sanitized = sanitized.replace("..", ".")
    return sanitized or "invoice"

# ---------------------------------------------------------------------------
# Pydantic Schemas with Strict Enum Validation
# ---------------------------------------------------------------------------

VALID_STATUSES = {"needs_review", "approved", "rejected"}


class InvoiceItemUpdateSchema(BaseModel):
    supplier_name: Optional[str] = None
    supplier_tax_id: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    currency: Optional[str] = None
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    items: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"Trạng thái không hợp lệ. Chọn một trong: {', '.join(VALID_STATUSES)}")
        return v


# ---------------------------------------------------------------------------
# FastAPI App Factory
# ---------------------------------------------------------------------------

def create_app(
    repo: Optional[SQLiteInvoiceRepository] = None,
    *,
    storage_dir: Path | str | None = None,
    parser: Any | None = None,
    extractor: Any | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Accounting Batch Service API",
        version="1.0.0",
        description="Production API for batch invoice AI extraction, review, and XLSX export",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    repository = repo or SQLiteInvoiceRepository(
        os.environ.get("ACCOUNTING_DB_PATH", "data/accounting_workspace.db")
    )
    configured_storage = os.environ.get("ACCOUNTING_STORAGE_DIR")
    active_storage_dir = (
        Path(storage_dir)
        if storage_dir
        else Path(configured_storage) if configured_storage else DEFAULT_STORAGE_DIR
    )
    active_storage_dir.mkdir(parents=True, exist_ok=True)
    active_parser = parser or PDFTextParser()
    active_extractor = extractor or SmartInvoiceExtractor()

    @app.get("/api/v1/accounting/batches")
    async def list_batches():
        """Retrieve all historical invoice batches from SQLite persistence."""
        batches = repository.list_all_batches()
        return {"batches": batches}

    @app.post("/api/v1/accounting/batches", status_code=status.HTTP_201_CREATED)
    async def create_batch(
        files: List[UploadFile] = File(...),
        x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key")
    ):
        """Upload a batch of invoice files. Individual file failures do NOT crash the batch."""
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded.")

        if x_gemini_api_key:
            os.environ["GEMINI_API_KEY"] = x_gemini_api_key
        if len(files) > MAX_BATCH_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"Mỗi batch chỉ được tối đa {MAX_BATCH_FILES} file.",
            )

        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        items_data = []

        for upload in files:
            file_id = f"file-{uuid.uuid4().hex[:6]}"
            filename = upload.filename or "invoice.pdf"
            safe_filename = sanitize_upload_name(filename)
            content_type = upload.content_type or ""
            content_size = 0
            storage_uri = None

            try:
                allowed_extensions = ALLOWED_MEDIA_TYPES.get(content_type)
                extension = Path(safe_filename).suffix.lower()
                if not allowed_extensions or extension not in allowed_extensions:
                    raise ValueError("Định dạng file không được hỗ trợ hoặc không khớp phần mở rộng.")

                content = await upload.read(MAX_FILE_BYTES + 1)
                content_size = len(content)
                if content_size > MAX_FILE_BYTES:
                    raise ValueError(f"File vượt quá giới hạn {MAX_FILE_BYTES // (1024 * 1024)} MiB.")

                # Save raw original file to disk storage
                raw_file_path = (active_storage_dir / f"{file_id}_{safe_filename}").resolve()
                if not raw_file_path.is_relative_to(active_storage_dir.resolve()):
                    raise ValueError("Tên file không tạo được đường dẫn lưu trữ an toàn.")
                raw_file_path.write_bytes(content)
                storage_uri = str(raw_file_path)

                ref = FileReference(
                    file_id=file_id,
                    workspace_id="default-ws",
                    name=filename,
                    media_type=content_type,
                    size_bytes=content_size,
                    storage_uri=storage_uri,
                )

                # 1. Parse PDF / Image text
                parsed_doc = active_parser.parse(ref, content)

                # 2. Extract structured fields via Gemini AI / Smart Rules
                ext_result = active_extractor.extract(
                    parsed_doc,
                    schema_name="invoice_schema",
                    schema_version=SCHEMA_VERSION,
                    schema=INVOICE_SCHEMA_V1,
                    raw_bytes=content,
                )

                items_data.append({
                    "file_id": file_id,
                    "file_name": filename,
                    "media_type": content_type,
                    "size_bytes": content_size,
                    "storage_uri": storage_uri,
                    "status": "needs_review",
                    "extraction": ext_result.values,
                    "warnings": list(ext_result.warnings),
                    "errors": [],
                })
            except Exception as exc:  # Per-file error isolation
                logger.error("Failed to process uploaded file %s: %s", filename, exc, exc_info=True)
                items_data.append({
                    "file_id": file_id,
                    "file_name": filename,
                    "media_type": content_type,
                    "size_bytes": content_size,
                    "storage_uri": storage_uri,
                    "status": "needs_review",
                    "extraction": {},
                    "warnings": [f"Lỗi đọc file: {type(exc).__name__}"],
                    "errors": [str(exc)[:200]],
                })

        saved_batch = repository.save_batch(batch_id, items_data)
        return saved_batch

    @app.get("/api/v1/accounting/batches/{batch_id}")
    async def get_batch(batch_id: str):
        batch = repository.get_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found.")

        items = batch["items"]
        total_amount = sum(i["extraction"].get("total_amount", 0) or 0 for i in items if i.get("extraction"))
        needs_review_count = sum(1 for i in items if i["status"] == "needs_review")
        approved_count = sum(1 for i in items if i["status"] == "approved")

        return {
            **batch,
            "stats": {
                "total_files": len(items),
                "approved_count": approved_count,
                "needs_review_count": needs_review_count,
                "total_amount_sum": total_amount,
            }
        }

    @app.patch("/api/v1/accounting/batches/{batch_id}/items/{file_id}")
    async def update_item(batch_id: str, file_id: str, update: InvoiceItemUpdateSchema):
        """Update an invoice's extracted fields or approval status."""
        update_data = update.model_dump(exclude_unset=True) if hasattr(update, "model_dump") else update.dict(exclude_unset=True)
        updated_item = repository.update_item(batch_id, file_id, update_data)
        if not updated_item:
            raise HTTPException(status_code=404, detail="Invoice item or batch not found.")
        return updated_item

    @app.get("/api/v1/accounting/files/{file_id}")
    async def get_raw_file(file_id: str):
        """Serve original uploaded raw invoice PDF or image file."""
        item = repository.get_item(file_id)
        if not item or not item.get("storage_uri"):
            raise HTTPException(status_code=404, detail="File không tồn tại trên lưu trữ disk.")
        raw_path = Path(item["storage_uri"]).resolve()
        if not raw_path.is_relative_to(active_storage_dir.resolve()) or not raw_path.is_file():
            raise HTTPException(status_code=404, detail="File không tồn tại trên lưu trữ disk.")
        return FileResponse(
            path=str(raw_path),
            media_type=item.get("media_type") or "application/octet-stream",
            filename=item.get("file_name") or raw_path.name,
        )

    @app.get("/api/v1/accounting/batches/{batch_id}/export.xlsx")
    @app.post("/api/v1/accounting/batches/{batch_id}/export")
    async def export_batch(batch_id: str):
        """Generate a workbook containing approved invoices only."""
        batch = repository.get_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found.")

        approved_records = []
        for item in batch["items"]:
            if (
                item.get("status") != "approved"
                or item.get("errors")
                or not item.get("extraction")
            ):
                continue
            approved_records.append({
                "source_file_id": item["file_id"],
                **item["extraction"],
            })

        if not approved_records:
            raise HTTPException(
                status_code=400,
                detail="Không có hóa đơn nào đã được duyệt để xuất Excel.",
            )

        exporter = XLSXExportAdapter()
        excel_filename = f"Bao_Cao_Hoa_Don_{batch_id}.xlsx"
        artifact = exporter.export(approved_records, options={"filename": excel_filename})

        return Response(
            content=artifact.content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{excel_filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )

    # Serve frontend SPA
    frontend_dir = Path("frontend")
    if frontend_dir.exists():
        if (frontend_dir / "styles").exists():
            app.mount("/styles", StaticFiles(directory="frontend/styles"), name="styles")
        if (frontend_dir / "src").exists():
            app.mount("/src", StaticFiles(directory="frontend/src"), name="src")

        @app.get("/", response_class=FileResponse)
        async def serve_index():
            return FileResponse("frontend/index.html")

    return app


app = create_app()
