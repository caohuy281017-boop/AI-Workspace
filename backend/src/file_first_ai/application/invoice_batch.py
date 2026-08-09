"""Minimal orchestration seam for the future first milestone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from file_first_ai.domain import (
    DocumentClassification,
    DocumentType,
    ExtractionResult,
    FileReference,
)
from file_first_ai.ports import DocumentClassifier, ExtractionProvider, FileParser


@dataclass(frozen=True, slots=True)
class InvoiceBatchItem:
    source: FileReference
    classification: DocumentClassification
    extraction: ExtractionResult | None
    errors: Sequence[str] = ()


class InvoiceBatchWorkflow:
    """Classify, parse, and extract each invoice independently.

    Persistence, queues, OCR fallback, review, and XLSX export will be added with
    the first functional milestone. Per-file failure isolation belongs here.
    """

    def __init__(
        self,
        *,
        classifier: DocumentClassifier,
        parser: FileParser,
        extractor: ExtractionProvider,
    ) -> None:
        self._classifier = classifier
        self._parser = parser
        self._extractor = extractor

    def process(
        self,
        files: Sequence[FileReference],
        *,
        schema: Mapping[str, Any],
        schema_version: str,
    ) -> list[InvoiceBatchItem]:
        return [
            self._process_one(file, schema=schema, schema_version=schema_version)
            for file in files
        ]

    def _process_one(
        self,
        source: FileReference,
        *,
        schema: Mapping[str, Any],
        schema_version: str,
    ) -> InvoiceBatchItem:
        classification = self._classifier.classify(source)
        if classification.document_type is not DocumentType.INVOICE:
            return InvoiceBatchItem(
                source=source,
                classification=classification,
                extraction=None,
                errors=("File was not classified as an invoice.",),
            )

        try:
            parsed = self._parser.parse(source)
            extraction = self._extractor.extract(
                parsed,
                schema_name="invoice",
                schema_version=schema_version,
                schema=schema,
            )
            return InvoiceBatchItem(source, classification, extraction)
        except Exception as exc:
            # The delivery layer will log exception details with a job ID. Avoid
            # coupling the domain result to a logging or retry framework.
            return InvoiceBatchItem(
                source=source,
                classification=classification,
                extraction=None,
                errors=(f"Processing failed: {type(exc).__name__}",),
            )
