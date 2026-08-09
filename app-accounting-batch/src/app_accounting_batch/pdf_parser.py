"""PDF and Image Document Parser.

Extracts text blocks and structural content from PDF files or image buffers
into ParsedDocument domain model.
"""

from __future__ import annotations

import io
import logging
from typing import List

from core_shared.domain import ContentBlock, FileReference, ParsedDocument

logger = logging.getLogger(__name__)


class PDFTextParser:
    """Parses text from PDF files using pypdf or simple text extraction fallback."""

    def parse(self, source: FileReference, content: bytes) -> ParsedDocument:
        blocks: List[ContentBlock] = []
        parser_name = "pypdf-parser"

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
        except Exception as exc:
            logger.warning("pypdf parsing failed for %s: %s. Falling back to string decode.", source.name, exc)
            parser_name = "fallback-text-parser"
            try:
                decoded = content.decode("utf-8", errors="ignore")
                printable = "".join(c for c in decoded if c.isprintable() or c in "\n\r\t")
                if printable.strip():
                    blocks.append(ContentBlock(block_id="fallback-b1", kind="text", text=printable.strip()[:4000]))
            except Exception:
                pass

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
