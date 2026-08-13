"""Safe, in-memory text extraction backed by Firecrawl anydoc."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class DocumentTextExtractionError(ValueError):
    """Raised when a supported document cannot produce meaningful text."""


class UnsupportedDocumentTypeError(DocumentTextExtractionError):
    """Raised when a file extension is outside the public tool contract."""


@dataclass(frozen=True)
class ExtractedDocumentText:
    content: str
    source_format: str
    engine: str = "anydoc"


class AnydocTextExtractor:
    """Convert supported documents to clean Markdown without persisting files."""

    EXTENSIONS = frozenset(
        {
            ".doc", ".docx", ".docm",
            ".ppt", ".pps", ".pot", ".pptx", ".pptm", ".ppsx", ".ppsm",
            ".xls", ".xlsx", ".xlsm", ".xlsb",
            ".odt", ".ods", ".odp", ".rtf", ".epub", ".pdf", ".csv",
        }
    )

    def extract(self, content: bytes, filename: str) -> ExtractedDocumentText:
        extension = Path(filename).suffix.lower()
        if extension not in self.EXTENSIONS:
            raise UnsupportedDocumentTypeError(
                f"Định dạng tài liệu chưa được hỗ trợ: {extension or 'không có phần mở rộng'}."
            )
        if not content:
            raise DocumentTextExtractionError("Tài liệu được tải lên đang trống.")

        try:
            import anydoc
        except ImportError as exc:  # pragma: no cover - deployment guard
            raise RuntimeError(
                "Bộ trích xuất tài liệu chưa sẵn sàng trên máy chủ."
            ) from exc

        try:
            markdown = anydoc.to_markdown_bytes(content, extension.lstrip("."))
        except Exception as exc:
            raise DocumentTextExtractionError(
                "Không đọc được tài liệu. File có thể bị mã hóa, hỏng, chỉ chứa ảnh quét hoặc không có văn bản."
            ) from exc

        normalized = str(markdown or "").strip()
        if not normalized:
            raise DocumentTextExtractionError("Không tìm thấy văn bản có thể đọc trong tài liệu.")
        return ExtractedDocumentText(
            content=normalized,
            source_format=extension.lstrip("."),
        )
