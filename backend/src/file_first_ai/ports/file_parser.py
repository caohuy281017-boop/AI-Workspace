from __future__ import annotations

from typing import Protocol, Sequence

from file_first_ai.domain import FileReference, ParsedDocument


class FileParser(Protocol):
    """Parse files without leaking an engine-specific document model."""

    def supported_media_types(self) -> Sequence[str]: ...

    def parse(self, source: FileReference) -> ParsedDocument: ...
