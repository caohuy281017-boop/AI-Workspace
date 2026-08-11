from __future__ import annotations

from typing import Mapping, Protocol, Any

from platform_core.domain import ExtractionResult, ParsedDocument


class ExtractionProvider(Protocol):
    """Extract a versioned business schema from a parsed document."""

    def extract(
        self,
        document: ParsedDocument,
        *,
        schema_name: str,
        schema_version: str,
        schema: Mapping[str, Any],
    ) -> ExtractionResult: ...
