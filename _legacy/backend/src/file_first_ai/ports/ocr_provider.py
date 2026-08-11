from __future__ import annotations

from typing import Protocol, Sequence

from file_first_ai.domain import FileReference, OCRResult


class OCRProvider(Protocol):
    """Recognize text from selected pages of an image or document."""

    def recognize(
        self,
        source: FileReference,
        *,
        pages: Sequence[int] | None = None,
        language_hints: Sequence[str] = (),
    ) -> OCRResult: ...
