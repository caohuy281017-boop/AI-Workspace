"""HTTP delivery adapter for the accounting batch application."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Header, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from platform_adapters.exporters.xlsx_exporter import XLSXExportAdapter

from accounting_app.pdf_parser import PDFTextParser
from accounting_app.persistence import SQLiteInvoiceRepository
from accounting_app.service import AccountingBatchService, UploadedInvoice
from accounting_app.smart_extractor import SmartInvoiceExtractor

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA_DIR = WORKSPACE_ROOT / "apps" / "accounting" / "data"
DEFAULT_STORAGE_DIR = DEFAULT_DATA_DIR / "storage"
MAX_BATCH_FILES = 20
MAX_FILE_BYTES = 20 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {
    "application/pdf": {".pdf"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/tiff": {".tif", ".tiff"},
}
VALID_STATUSES = {"needs_review", "approved", "rejected"}


def sanitize_upload_name(name: str) -> str:
    """Return a basename that cannot escape server-controlled storage."""
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


VALID_INVOICE_TYPES = {"dau_vao", "dau_ra", "khac"}


class InvoiceItemUpdateSchema(BaseModel):
    supplier_name: str | None = None
    supplier_tax_id: str | None = None
    buyer_name: str | None = None
    buyer_tax_id: str | None = None
    invoice_template_number: str | None = None
    invoice_series: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    currency: str | None = None
    subtotal: float | None = None
    discount_amount: float | None = None
    fees: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    tax_breakdown: list[dict[str, Any]] | None = None
    items: list[dict[str, Any]] | None = None
    custom_fields: dict[str, Any] | None = None
    status: str | None = None
    invoice_type: str | None = None
    note: str | None = None
    override_reason: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in VALID_STATUSES:
            raise ValueError(f"Invalid status. Choose one of: {', '.join(sorted(VALID_STATUSES))}")
        return value

    @field_validator("invoice_type")
    @classmethod
    def validate_invoice_type(cls, value: str | None) -> str | None:
        if value is not None and value not in VALID_INVOICE_TYPES:
            raise ValueError(f"Invalid invoice_type. Choose one of: {', '.join(sorted(VALID_INVOICE_TYPES))}")
        return value


class CustomFieldCreateSchema(BaseModel):
    code: str
    name: str
    field_type: str = "string"
    llm_prompt: str = ""
    visible_in_list: bool = False
    visible_in_analysis: bool = True
    is_required: bool = False

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", value):
            raise ValueError("Code must use 2-40 lowercase letters, numbers or underscores.")
        return value

    @field_validator("field_type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value not in {"string", "number", "boolean"}:
            raise ValueError("field_type must be string, number or boolean.")
        return value


class CustomFieldUpdateSchema(BaseModel):
    name: str | None = None
    field_type: str | None = None
    llm_prompt: str | None = None
    visible_in_list: bool | None = None
    visible_in_analysis: bool | None = None
    is_required: bool | None = None


class CustomFieldReorderSchema(BaseModel):
    codes: list[str]


def _parse_column_labels(raw: str | None) -> dict[str, str]:
    """Parse column_labels query param (JSON string) safely."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except Exception:
        pass
    return {}


def create_app(
    repo: SQLiteInvoiceRepository | None = None,
    *,
    storage_dir: Path | str | None = None,
    parser: Any | None = None,
    extractor: Any | None = None,
) -> FastAPI:
    """Build the API and inject all external adapters at the composition root."""
    app = FastAPI(
        title="Accounting Batch Service API",
        version="1.1.0",
        description="Batch invoice extraction, human review and XLSX export",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    repository = repo or SQLiteInvoiceRepository(
        os.environ.get(
            "ACCOUNTING_DB_PATH",
            str(DEFAULT_DATA_DIR / "accounting_workspace.db"),
        )
    )
    configured_storage = os.environ.get("ACCOUNTING_STORAGE_DIR")
    active_storage_dir = Path(
        storage_dir or configured_storage or DEFAULT_STORAGE_DIR
    ).resolve()
    active_parser = parser or PDFTextParser()
    extractor_factory = (
        (lambda *_args, **_kwargs: extractor)
        if extractor is not None
        else (lambda api_key=None, openai_api_key=None, provider=None: SmartInvoiceExtractor(
            api_key=api_key,
            openai_api_key=openai_api_key,
            provider=provider,
        ))
    )
    service = AccountingBatchService(
        repository=repository,
        storage_dir=active_storage_dir,
        parser=active_parser,
        extractor_factory=extractor_factory,
        allowed_media_types=ALLOWED_MEDIA_TYPES,
        max_file_bytes=MAX_FILE_BYTES,
    )

    @app.get("/api/v1/accounting/batches")
    async def list_batches(search: str | None = None, invoice_type: str | None = None):
        batches = repository.list_all_batches(search=search, invoice_type=invoice_type)
        return {"batches": batches}

    @app.get("/api/v1/accounting/settings/custom-fields")
    async def list_custom_fields():
        return {"fields": repository.list_custom_fields()}

    @app.post("/api/v1/accounting/settings/custom-fields", status_code=201)
    async def create_custom_field(field: CustomFieldCreateSchema):
        try:
            return repository.create_custom_field(field.model_dump())
        except Exception as exc:
            if "UNIQUE constraint" in str(exc):
                raise HTTPException(status_code=409, detail="Field code already exists.") from exc
            raise

    @app.patch("/api/v1/accounting/settings/custom-fields/{code}")
    async def update_custom_field(code: str, field: CustomFieldUpdateSchema):
        updated = repository.update_custom_field(code, field.model_dump(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=404, detail="Custom field not found.")
        return updated

    @app.delete("/api/v1/accounting/settings/custom-fields/{code}", status_code=204)
    async def delete_custom_field(code: str):
        if not repository.delete_custom_field(code):
            raise HTTPException(status_code=404, detail="Custom field not found.")

    @app.put("/api/v1/accounting/settings/custom-fields/reorder")
    async def reorder_custom_fields(order: CustomFieldReorderSchema):
        try:
            return {"fields": repository.reorder_custom_fields(order.codes)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/accounting/batches", status_code=status.HTTP_201_CREATED)
    async def create_batch(
        files: list[UploadFile] = File(...),
        x_gemini_api_key: str | None = Header(None, alias="X-Gemini-API-Key"),
        x_openai_api_key: str | None = Header(None, alias="X-OpenAI-API-Key"),
        x_llm_provider: str | None = Header(None, alias="X-LLM-Provider"),
    ):
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded.")
        if len(files) > MAX_BATCH_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"A batch can contain at most {MAX_BATCH_FILES} files.",
            )

        uploads = []
        for upload in files:
            name = upload.filename or "invoice.pdf"
            uploads.append(
                UploadedInvoice(
                    name=name,
                    safe_name=sanitize_upload_name(name),
                    media_type=upload.content_type or "",
                    content=await upload.read(MAX_FILE_BYTES + 1),
                )
            )
        return service.create_batch(
            uploads,
            provider_api_key=x_gemini_api_key,
            openai_api_key=x_openai_api_key,
            llm_provider=x_llm_provider,
        )

    @app.get("/api/v1/accounting/batches/{batch_id}")
    async def get_batch(batch_id: str):
        batch = repository.get_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found.")
        items = batch["items"]
        total = sum(
            item.get("extraction", {}).get("total_amount", 0) or 0
            for item in items
        )
        return {
            **batch,
            "stats": {
                "total_files": len(items),
                "approved_count": sum(item["status"] == "approved" for item in items),
                "needs_review_count": sum(
                    item["status"] == "needs_review" for item in items
                ),
                "total_amount_sum": total,
            },
        }

    @app.patch("/api/v1/accounting/batches/{batch_id}/items/{file_id}")
    async def update_item(
        batch_id: str,
        file_id: str,
        update: InvoiceItemUpdateSchema,
    ):
        updated = repository.update_item(
            batch_id,
            file_id,
            update.model_dump(exclude_unset=True),
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Invoice item or batch not found.")
        return updated

    @app.get("/api/v1/accounting/batches/{batch_id}/items/{file_id}/audit-logs")
    async def get_item_audit_logs(batch_id: str, file_id: str):
        item = repository.get_item(file_id)
        if not item or item.get("batch_id") != batch_id:
            raise HTTPException(status_code=404, detail="Invoice item or batch not found.")
        logs = repository.list_audit_logs(entity_id=file_id, entity_type="invoice_item")
        return {"audit_logs": logs}

    @app.delete("/api/v1/accounting/batches/{batch_id}/items/{file_id}", status_code=204)
    async def delete_item(batch_id: str, file_id: str):
        """Remove a single invoice from the batch. Also deletes the stored file."""
        deleted = repository.delete_item(batch_id, file_id, storage_dir=active_storage_dir)
        if not deleted:
            raise HTTPException(status_code=404, detail="Invoice item or batch not found.")

    @app.get("/api/v1/accounting/files/{file_id}")
    async def get_raw_file(file_id: str, download: bool = False):
        item = repository.get_item(file_id)
        if not item or not item.get("storage_uri"):
            raise HTTPException(status_code=404, detail="Stored file not found.")
        raw_path = Path(item["storage_uri"]).resolve()
        if not raw_path.is_relative_to(active_storage_dir) or not raw_path.is_file():
            raise HTTPException(status_code=404, detail="Stored file not found.")
        return FileResponse(
            path=str(raw_path),
            media_type=item.get("media_type") or "application/octet-stream",
            filename=item.get("file_name") or raw_path.name,
            content_disposition_type="attachment" if download else "inline",
        )

    @app.get("/api/v1/accounting/batches/{batch_id}/export.xlsx")
    @app.post("/api/v1/accounting/batches/{batch_id}/export")
    async def export_batch(batch_id: str, column_labels: str | None = None):
        batch = repository.get_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found.")
        approved = [
            {"file_name": item["file_name"], "invoice_type": item.get("invoice_type", "dau_vao"),
             "note": item.get("note", ""), "extraction": item["extraction"]}
            for item in batch["items"]
            if item.get("status") == "approved"
            and not item.get("errors")
            and item.get("extraction")
        ]
        if not approved:
            raise HTTPException(
                status_code=400,
                detail="Không có hóa đơn nào đã được duyệt để xuất Excel.",
            )
        filename = f"Bao_Cao_Hoa_Don_{batch_id}.xlsx"
        col_labels = _parse_column_labels(column_labels)
        artifact = XLSXExportAdapter().export(approved, options={"filename": filename, "column_labels": col_labels})
        return Response(
            content=artifact.content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    @app.get("/api/v1/accounting/export-all.xlsx")
    async def export_all(invoice_type: str | None = None, column_labels: str | None = None):
        """Export ALL approved invoices across every batch into one XLSX file."""
        items = repository.get_all_approved_items(invoice_type=invoice_type)
        if not items:
            raise HTTPException(
                status_code=400,
                detail="Không có hóa đơn nào đã được duyệt để xuất Excel.",
            )
        from datetime import datetime
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Bao_Cao_Hoa_Don_TatCa_{stamp}.xlsx"
        col_labels = _parse_column_labels(column_labels)
        artifact = XLSXExportAdapter().export(items, options={"filename": filename, "column_labels": col_labels})
        return Response(
            content=artifact.content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    frontend_dir = WORKSPACE_ROOT / "frontend"
    if frontend_dir.exists():
        if (frontend_dir / "styles").exists():
            app.mount("/styles", StaticFiles(directory=frontend_dir / "styles"), name="styles")
        if (frontend_dir / "src").exists():
            app.mount("/src", StaticFiles(directory=frontend_dir / "src"), name="src")

        @app.get("/", response_class=FileResponse)
        async def serve_index():
            return FileResponse(frontend_dir / "index.html")

    return app


app = create_app()
