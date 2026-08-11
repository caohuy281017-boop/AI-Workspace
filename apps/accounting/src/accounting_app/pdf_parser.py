"""PDF and Image Document Parser.

Extracts text blocks and structural content from PDF files or image buffers
into ParsedDocument domain model.
"""

from __future__ import annotations

import io
import logging
from typing import List

from platform_core.domain import ContentBlock, FileReference, ParsedDocument

logger = logging.getLogger(__name__)


class PDFTextParser:
    """Parses text from PDF files using pypdf or simple text extraction fallback."""

    def parse(self, source: FileReference, content: bytes) -> ParsedDocument:
        blocks: List[ContentBlock] = []
        parser_name = "pypdf-parser"

        parsed = False
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content))
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    blocks.append(
                        ContentBlock(
                            block_id=f"page-{page_num}",
                            kind="text",
                            text=text.strip(),
                        )
                    )
            if blocks:
                parsed = True
        except Exception:
            pass

        if not parsed:
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(content)
                for page_num, page in enumerate(pdf, start=1):
                    textpage = page.get_textpage()
                    text = textpage.get_text_range() or ""
                    if text.strip():
                        blocks.append(
                            ContentBlock(
                                block_id=f"page-{page_num}",
                                kind="text",
                                text=text.strip(),
                            )
                        )
                if blocks:
                    parsed = True
                    parser_name = "pypdfium2-parser"
            except Exception as exc:
                logger.warning("PDF parsing failed for %s: %s", source.name, exc)

        if not parsed:
            parser_name = "unreadable-document"

            # Only plain-text test/dev inputs may use the lightweight decode
            # fallback. Decoding PDF/image binary creates convincing garbage
            # such as "%PDF-1.4", fake dates and fake invoice numbers.
            is_binary_document = (
                source.media_type.startswith("image/")
                or source.media_type == "application/pdf"
                and content.startswith(b"%PDF-")
            )
            if not is_binary_document:
                decoded = content.decode("utf-8", errors="ignore")
                printable = "".join(
                    char
                    for char in decoded
                    if char.isprintable() or char in "\n\r\t"
                )
                if printable.strip():
                    parser_name = "fallback-text-parser"
                    blocks.append(
                        ContentBlock(
                            block_id="fallback-b1",
                            kind="text",
                            text=printable.strip()[:4000],
                        )
                    )

        if not blocks:
            blocks.append(
                ContentBlock(
                    block_id="b1",
                    kind="text",
                    text=f"[No extractable text found in file {source.name}]",
                )
            )

        return ParsedDocument(
            source=source,
            blocks=tuple(blocks),
            parser=parser_name,
        )
