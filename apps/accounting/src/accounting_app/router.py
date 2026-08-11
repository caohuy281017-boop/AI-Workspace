"""Document Router: Intelligent text-quality scoring and model routing.

Routes documents to the most cost-effective and accurate processing path:
- High-quality digital PDF text (quality >= 0.70) -> Text-only LLM (faster, 5-10x cheaper)
- Scanned PDF, image, or garbled text (quality < 0.70) -> Multimodal Vision AI
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

DocumentFormat = Literal["pdf", "jpeg", "png", "webp", "tiff"]

SUPPORTED_EXTENSIONS = {
    "pdf": {".pdf"},
    "jpeg": {".jpg", ".jpeg"},
    "png": {".png"},
    "webp": {".webp"},
    "tiff": {".tif", ".tiff"},
}

CANONICAL_MIME_TYPES = {
    "pdf": "application/pdf",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "tiff": "image/tiff",
}

EXTENSION_TO_FORMAT = {
    ".pdf": "pdf",
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".webp": "webp",
    ".tif": "tiff",
    ".tiff": "tiff",
}

MIME_TO_FORMAT = {
    "application/pdf": "pdf",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/png": "png",
    "image/webp": "webp",
    "image/tiff": "tiff",
    "image/tif": "tiff",
}


@dataclass(frozen=True, slots=True)
class DocumentType:
    format: DocumentFormat
    media_type: str
    is_image: bool


def detect_magic_format(content: bytes) -> DocumentFormat | None:
    """Detect format from magic bytes/signature."""
    if content.startswith(b"%PDF-"):
        return "pdf"
    if content.startswith(b"\xFF\xD8\xFF"):
        return "jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    if content.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    return None


import io
import os

MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", "10"))


def validate_pdf_page_limit(content: bytes, max_pages: int = MAX_PDF_PAGES) -> int:
    """Validate that a PDF does not exceed the page limit.

    Raises ValueError with PAGE_LIMIT_EXCEEDED if page count > max_pages.
    """
    page_count = 1
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        page_count = len(reader.pages)
    except Exception:
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(content)
            page_count = len(pdf)
        except Exception:
            page_count = 1

    if page_count > max_pages:
        raise ValueError(
            f"PAGE_LIMIT_EXCEEDED: PDF contains {page_count} pages, exceeding the limit of {max_pages} pages."
        )
    return page_count


def classify_document(
    filename: str,
    declared_media_type: str,
    content: bytes,
    *,
    max_pdf_pages: int = MAX_PDF_PAGES,
) -> DocumentType:
    """Classify document by verifying MIME type, filename extension, and magic bytes.

    Raises ValueError with FILE_TYPE_MISMATCH if any source is inconsistent.
    Raises ValueError with PAGE_LIMIT_EXCEEDED if PDF exceeds max page limit.
    """
    ext = Path(filename).suffix.lower()
    ext_format = EXTENSION_TO_FORMAT.get(ext)
    clean_mime = (declared_media_type or "").lower().split(";")[0].strip()
    mime_format = MIME_TO_FORMAT.get(clean_mime)
    magic_format = detect_magic_format(content)

    if not ext_format:
        raise ValueError(f"FILE_TYPE_MISMATCH: Unsupported file extension '{ext}' for file '{filename}'")

    if not mime_format:
        raise ValueError(f"FILE_TYPE_MISMATCH: Unsupported declared MIME type '{declared_media_type}' for file '{filename}'")

    if not magic_format:
        raise ValueError(f"FILE_TYPE_MISMATCH: File '{filename}' content does not match any recognized signature (PDF, JPEG, PNG, WEBP, TIFF)")

    if not (ext_format == mime_format == magic_format):
        raise ValueError(
            f"FILE_TYPE_MISMATCH: Inconsistent file attributes for '{filename}'. "
            f"Extension suggests '{ext_format}', declared MIME suggests '{mime_format}', "
            f"but magic bytes indicate '{magic_format}'."
        )

    if magic_format == "pdf":
        validate_pdf_page_limit(content, max_pages=max_pdf_pages)

    canonical_mime = CANONICAL_MIME_TYPES[magic_format]
    is_image = magic_format in {"jpeg", "png", "webp", "tiff"}

    return DocumentType(
        format=magic_format,
        media_type=canonical_mime,
        is_image=is_image,
    )


# Invoice-specific landmark keywords in Vietnamese and English
_INVOICE_KEYWORDS = [
    # Vietnamese
    r"hóa\s*đơn",
    r"mã\s*số\s*thuế",
    r"mst",
    r"ngày\s*tháng",
    r"tiền\s*hàng",
    r"tiền\s*thuế",
    r"thuế\s*gtgt",
    r"vat",
    r"tổng\s*tiền",
    r"tổng\s*cộng",
    r"thanh\s*toán",
    r"công\s*ty",
    r"tnhh",
    r"cổ\s*phần",
    r"đơn\s*vị",
    r"người\s*bán",
    r"người\s*mua",
    r"số\s*tài\s*khoản",
    # English
    r"invoice",
    r"tax\s*id",
    r"tax\s*code",
    r"subtotal",
    r"total\s*amount",
    r"due\s*date",
    r"company",
    r"supplier",
]


@dataclass(frozen=True, slots=True)
class DocumentRoutingDecision:
    """Routing decision for processing a document."""
    mode: str                      # "text_only" | "multimodal_vision"
    text_quality_score: float      # 0.0 to 1.0
    char_count: int
    printable_ratio: float
    keyword_density: float
    has_scanned_indicator: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "text_quality_score": round(self.text_quality_score, 3),
            "char_count": self.char_count,
            "printable_ratio": round(self.printable_ratio, 3),
            "keyword_density": round(self.keyword_density, 3),
            "has_scanned_indicator": self.has_scanned_indicator,
            "reason": self.reason,
        }


def assess_text_quality(
    text: str | None,
    media_type: str = "application/pdf",
    filename: str = "",
) -> DocumentRoutingDecision:
    """Assess extracted text quality and decide whether to route to text LLM or Vision AI.

    Scoring formula:
      text_quality_score = 0.35 * length_score + 0.35 * printable_ratio + 0.30 * keyword_score

    Decision criteria:
      - Images (PNG, JPG, TIFF, WEBP) -> always "multimodal_vision"
      - No text or "[No extractable text found...]" -> "multimodal_vision"
      - text_quality_score >= 0.70 and char_count >= 100 and matched_keywords >= 2 -> "text_only"
      - Otherwise -> "multimodal_vision"
    """
    if not text:
        return DocumentRoutingDecision(
            mode="multimodal_vision",
            text_quality_score=0.0,
            char_count=0,
            printable_ratio=0.0,
            keyword_density=0.0,
            has_scanned_indicator=True,
            reason="Văn bản rỗng hoặc không trích xuất được chữ -> Chuyển sang Vision AI.",
        )

    # 1. Check if media type is inherently image
    is_image = media_type.startswith("image/") or any(
        filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".tiff")
    )
    if is_image:
        return DocumentRoutingDecision(
            mode="multimodal_vision",
            text_quality_score=0.0,
            char_count=len(text),
            printable_ratio=0.0,
            keyword_density=0.0,
            has_scanned_indicator=True,
            reason="Tệp dạng hình ảnh -> Bắt buộc dùng Multimodal Vision AI.",
        )

    # 2. Check for explicit scan / no text marker
    if "[No extractable text found" in text or len(text.strip()) < 30:
        return DocumentRoutingDecision(
            mode="multimodal_vision",
            text_quality_score=0.05,
            char_count=len(text.strip()),
            printable_ratio=0.0,
            keyword_density=0.0,
            has_scanned_indicator=True,
            reason="PDF dạng scan (chứa ảnh scan, không có text layer) -> Chuyển sang Vision AI.",
        )

    clean_text = text.strip()
    char_count = len(clean_text)

    # 3. Printable characters ratio
    printable_count = sum(
        1 for c in clean_text
        if c.isprintable() and (c.isalnum() or c.isspace() or c in ".,:;/-_()%$#@+=*&'\"₫đĐ")
    )
    printable_ratio = printable_count / max(1, char_count)

    # 4. Length score
    if char_count < 50:
        length_score = 0.2
    elif char_count < 100:
        length_score = 0.5
    elif char_count < 250:
        length_score = 0.8
    else:
        length_score = 1.0

    # 5. Keyword density
    text_lower = clean_text.lower()
    matched_keywords = sum(
        1 for kw in _INVOICE_KEYWORDS
        if re.search(kw, text_lower)
    )
    keyword_score = min(1.0, matched_keywords / 5.0)

    # 6. Overall Text Quality Score
    text_quality_score = (
        0.35 * length_score +
        0.35 * printable_ratio +
        0.30 * keyword_score
    )

    # Check for excessive OCR garbage / control chars
    control_chars = sum(1 for c in clean_text if unicodedata.category(c).startswith("C") and c not in "\r\n\t")
    if control_chars > 10 or printable_ratio < 0.65:
        text_quality_score *= 0.5

    # 7. Routing decision
    if text_quality_score >= 0.70 and char_count >= 100 and matched_keywords >= 2:
        return DocumentRoutingDecision(
            mode="text_only",
            text_quality_score=text_quality_score,
            char_count=char_count,
            printable_ratio=printable_ratio,
            keyword_density=keyword_score,
            has_scanned_indicator=False,
            reason=(
                f"PDF điện tử chất lượng cao (Điểm: {text_quality_score:.2f}, "
                f"{char_count} ký tự, {matched_keywords} từ khóa) -> Xử lý nhanh bằng Text LLM."
            ),
        )
    else:
        return DocumentRoutingDecision(
            mode="multimodal_vision",
            text_quality_score=text_quality_score,
            char_count=char_count,
            printable_ratio=printable_ratio,
            keyword_density=keyword_score,
            has_scanned_indicator=True,
            reason=(
                f"Chất lượng text không đủ cao (Điểm: {text_quality_score:.2f} < 0.70) "
                f"-> Sử dụng Multimodal Vision AI để đảm bảo độ chính xác."
            ),
        )
