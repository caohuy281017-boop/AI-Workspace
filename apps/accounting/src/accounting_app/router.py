"""Document Router: Intelligent text-quality scoring and model routing.

Routes documents to the most cost-effective and accurate processing path:
- High-quality digital PDF text (quality >= 0.70) -> Text-only LLM (faster, 5-10x cheaper)
- Scanned PDF, image, or garbled text (quality < 0.70) -> Multimodal Vision AI
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional


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
