"""Application service for the accounting batch workflow.

This module is the single orchestration path used by the HTTP API.  It keeps
transport concerns (FastAPI/UploadFile) outside the accounting workflow and
preserves per-document failure isolation.
"""

from __future__ import annotations

import logging
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Collection, Iterable, Mapping

from platform_core.domain import FileReference

from accounting_app.persistence import SQLiteInvoiceRepository
from accounting_app.schema import INVOICE_SCHEMA_V1, SCHEMA_VERSION

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UploadedInvoice:
    """Validated bytes received by a delivery adapter."""

    name: str
    safe_name: str
    media_type: str
    content: bytes


class AccountingBatchService:
    """Coordinates storage, parsing, extraction, review persistence and export."""

    def __init__(
        self,
        repository: SQLiteInvoiceRepository,
        storage_dir: Path,
        parser: Any,
        extractor_factory: Callable[[str | None], Any],
        allowed_media_types: Mapping[str, Collection[str]],
        max_file_bytes: int,
    ) -> None:
        self.repository = repository
        self.storage_dir = storage_dir.resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.parser = parser
        self.extractor_factory = extractor_factory
        self.allowed_media_types = allowed_media_types
        self.max_file_bytes = max_file_bytes

    def create_batch(
        self,
        uploads: Iterable[UploadedInvoice],
        *,
        workspace_id: str = "default-ws",
        provider_api_key: str | None = None,
        openai_api_key: str | None = None,
        llm_provider: str | None = None,
    ) -> dict[str, Any]:
        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        try:
            extractor = self.extractor_factory(
                api_key=provider_api_key,
                openai_api_key=openai_api_key,
                provider=llm_provider,
            )
        except TypeError:
            extractor = self.extractor_factory(provider_api_key)
        schema = deepcopy(INVOICE_SCHEMA_V1)
        custom_fields = self.repository.list_custom_fields()
        if custom_fields:
            schema["properties"]["custom_fields"] = {
                "type": "object",
                "properties": {
                    field["code"]: {
                        "type": field["field_type"],
                        "description": field["llm_prompt"] or field["name"],
                    }
                    for field in custom_fields
                },
            }
        items: list[dict[str, Any]] = []

        for upload in uploads:
            file_id = f"file-{uuid.uuid4().hex[:6]}"
            storage_uri: str | None = None
            try:
                allowed_extensions = self.allowed_media_types.get(upload.media_type)
                extension = Path(upload.safe_name).suffix.lower()
                if not allowed_extensions or extension not in allowed_extensions:
                    raise ValueError(
                        "Unsupported media type or filename extension mismatch."
                    )
                if len(upload.content) > self.max_file_bytes:
                    raise ValueError(
                        f"File exceeds the {self.max_file_bytes // (1024 * 1024)} MiB limit."
                    )

                raw_path = (self.storage_dir / f"{file_id}_{upload.safe_name}").resolve()
                if not raw_path.is_relative_to(self.storage_dir):
                    raise ValueError("Unsafe storage path.")
                raw_path.write_bytes(upload.content)
                storage_uri = str(raw_path)

                source = FileReference(
                    file_id=file_id,
                    workspace_id=workspace_id,
                    name=upload.name,
                    media_type=upload.media_type,
                    size_bytes=len(upload.content),
                    storage_uri=storage_uri,
                )
                document = self.parser.parse(source, upload.content)
                extraction = extractor.extract(
                    document,
                    schema_name="invoice_schema",
                    schema_version=SCHEMA_VERSION,
                    schema=schema,
                    raw_bytes=upload.content,
                )
                item = {
                    "file_id": file_id,
                    "file_name": upload.name,
                    "media_type": upload.media_type,
                    "size_bytes": len(upload.content),
                    "storage_uri": storage_uri,
                    "status": "needs_review",
                    "extraction": extraction.values,
                    "warnings": list(extraction.warnings),
                    "errors": [],
                }
            except Exception as exc:  # one bad document must not fail the batch
                logger.error("Failed to process %s: %s", upload.name, exc, exc_info=True)
                item = {
                    "file_id": file_id,
                    "file_name": upload.name,
                    "media_type": upload.media_type,
                    "size_bytes": len(upload.content),
                    "storage_uri": storage_uri,
                    "status": "needs_review",
                    "extraction": {},
                    "warnings": [f"Document processing failed: {type(exc).__name__}"],
                    "errors": [str(exc)[:200]],
                }
            items.append(item)

        return self.repository.save_batch(batch_id, items)
