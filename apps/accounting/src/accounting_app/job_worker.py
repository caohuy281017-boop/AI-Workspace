"""Background Job Worker for asynchronous invoice processing.

Runs an atomic job claiming loop over the SQLite `jobs` table:
- Enqueues jobs upon asynchronous file upload.
- Atomically claims pending jobs with lease locking.
- Executes parsing, text quality routing, extraction, validation, and persistence.
- Handles retries with exponential backoff on transient errors.
- Recovers stale jobs if a worker crashes or drops heartbeat.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from platform_core.domain import ContentBlock, FileReference, ParsedDocument
from accounting_app.persistence import SQLiteInvoiceRepository
from accounting_app.pdf_parser import PDFTextParser
from accounting_app.smart_extractor import SmartInvoiceExtractor
from accounting_app.router import assess_text_quality, classify_document
from accounting_app.validator import validate_invoice
from accounting_app.schema import SCHEMA_NAME, SCHEMA_VERSION, INVOICE_SCHEMA_V2

logger = logging.getLogger(__name__)


class JobWorker:
    """Worker instance claiming and executing asynchronous extraction jobs."""

    def __init__(
        self,
        repository: SQLiteInvoiceRepository,
        storage_dir: Path,
        parser: PDFTextParser,
        extractor: SmartInvoiceExtractor,
        worker_id: Optional[str] = None,
        lease_seconds: int = 60,
    ) -> None:
        self.repository = repository
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.parser = parser
        self.extractor = extractor
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:6]}"
        self.lease_seconds = lease_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def process_job(self, job: Dict[str, Any]) -> bool:
        """Process a single claimed job. Returns True if completed, False if failed."""
        job_id = job["job_id"]
        file_id = job["file_id"]
        batch_id = job["batch_id"]

        logger.info("[%s] Processing job %s for file %s in batch %s", self.worker_id, job_id, file_id, batch_id)

        try:
            # 1. Fetch item from repository to get storage uri and filename
            item = self.repository.get_item(file_id)
            if not item:
                self.repository.fail_job(job_id, "ITEM_NOT_FOUND", f"Item {file_id} not found in DB")
                return False

            storage_uri = item.get("storage_uri")
            file_name = item.get("file_name", "unknown")
            declared_media_type = item.get("media_type", "application/pdf")
            file_path = Path(storage_uri) if storage_uri else self.storage_dir / file_id

            if not file_path.is_file():
                self.repository.fail_job(job_id, "FILE_NOT_FOUND", f"File {file_path} not found on disk")
                return False

            raw_bytes = file_path.read_bytes()

            # 2. Classify document
            try:
                doc_type = classify_document(
                    filename=file_name,
                    declared_media_type=declared_media_type,
                    content=raw_bytes,
                )
            except ValueError as exc:
                logger.warning("[%s] Document classification error for %s: %s", self.worker_id, file_name, exc)
                self.repository.fail_job(job_id, "FILE_TYPE_MISMATCH", str(exc))
                self.repository.update_item_extraction_and_status(
                    file_id=file_id,
                    extraction={},
                    warnings=[],
                    errors=[{"message": str(exc), "code": "FILE_TYPE_MISMATCH"}],
                    validation_status="error",
                    validation_errors=[],
                    status="failed",
                )
                return False

            source_ref = FileReference(
                file_id=file_id,
                workspace_id=job.get("workspace_id", "default-ws"),
                name=file_name,
                media_type=doc_type.media_type,
                size_bytes=len(raw_bytes),
                storage_uri=str(file_path),
            )

            # 3. Parse document
            if doc_type.is_image:
                parsed_doc = ParsedDocument(
                    source=source_ref,
                    blocks=(),
                    parser="image-direct",
                )
            else:
                try:
                    parsed_doc = self.parser.parse(source_ref, raw_bytes)
                except Exception as exc:
                    logger.warning("PDF parsing error for %s: %s", file_name, exc)
                    parsed_doc = ParsedDocument(
                        source=source_ref,
                        blocks=(ContentBlock(block_id="b0", kind="text", text=f"[Parsing fallback for {file_name}]"),),
                        parser="fallback",
                    )

            # 4. Document routing decision
            doc_text = "\n".join(b.text for b in parsed_doc.blocks if b.text)
            routing = assess_text_quality(doc_text, media_type=doc_type.media_type, filename=file_name)

            # Heartbeat lease
            self.repository.heartbeat_job(job_id, self.worker_id, extend_seconds=self.lease_seconds)

            # 4. Extract structured fields
            extraction_res = self.extractor.extract(
                parsed_doc,
                schema_name=SCHEMA_NAME,
                schema_version=SCHEMA_VERSION,
                schema=INVOICE_SCHEMA_V2,
                raw_bytes=raw_bytes,
            )

            # 5. Validation engine
            def _dup_checker(mst, series, number, inv_date):
                return self.repository.check_duplicate(
                    supplier_tax_id=mst,
                    invoice_series=series,
                    invoice_number=number,
                    invoice_date=inv_date,
                    exclude_file_id=file_id,
                )

            val_issues = validate_invoice(extraction_res.values, duplicate_checker=_dup_checker)
            val_errors = [i.to_dict() for i in val_issues if i.severity == "error"]
            val_warnings = [i.to_dict() for i in val_issues if i.severity in ("warning", "info")]
            validation_status = "error" if val_errors else ("warning" if val_warnings else "ok")
            all_val_issues = val_errors + val_warnings

            # 6. Update item in repository
            self.repository.update_item_extraction_and_status(
                file_id=file_id,
                extraction=extraction_res.values,
                warnings=list(extraction_res.warnings),
                errors=val_errors,
                validation_status=validation_status,
                validation_errors=all_val_issues,
                status="needs_review",
            )

            # 7. Complete job
            self.repository.complete_job(job_id, routing_decision=routing.to_dict())
            logger.info("[%s] Job %s completed successfully", self.worker_id, job_id)
            return True

        except Exception as exc:
            logger.exception("[%s] Unexpected error processing job %s: %s", self.worker_id, job_id, exc)
            self.repository.fail_job(job_id, "EXECUTION_ERROR", str(exc))
            return False

    def run_once(self) -> bool:
        """Attempt to claim and process one job. Returns True if a job was processed."""
        # Clean stale leases periodically
        self.repository.recover_stale_jobs()

        job = self.repository.claim_next_job(self.worker_id, lease_seconds=self.lease_seconds)
        if not job:
            return False

        return self.process_job(job)

    def _worker_loop(self) -> None:
        logger.info("[%s] Worker loop started", self.worker_id)
        while not self._stop_event.is_set():
            processed = self.run_once()
            if not processed:
                self._stop_event.wait(timeout=self.poll_interval)
        logger.info("[%s] Worker loop stopped", self.worker_id)

    def start(self) -> None:
        """Start worker in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name=f"WorkerThread-{self.worker_id}")
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the worker to stop and wait for completion."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
