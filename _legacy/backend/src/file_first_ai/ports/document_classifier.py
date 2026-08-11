from __future__ import annotations

from typing import Protocol

from file_first_ai.domain import DocumentClassification, FileReference, ParsedDocument


class DocumentClassifier(Protocol):
    """Classify a file into a controlled business document type."""

    def classify(
        self,
        source: FileReference,
        parsed: ParsedDocument | None = None,
    ) -> DocumentClassification: ...
