"""Docling implementation of the application-owned ``FileParser`` port.

Only this module knows about Docling. It converts Docling's document graph into
our small normalized schema and never returns a Docling object to callers.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import unquote, urlparse

from core_shared.domain import BoundingBox, ContentBlock, FileReference, ParsedDocument


class UnsupportedFileTypeError(ValueError):
    pass


class NonLocalFileError(ValueError):
    pass


class DoclingFileParser:
    """Parse PDF and modern Office files with an injected or local Docling converter.

    The default converter disables PDF OCR and optional enrichments. OCR remains a
    separate application capability and can be added through ``OCRProvider`` after
    its engine/model license is approved.
    """

    MEDIA_TYPES = (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    EXTENSIONS = (".pdf", ".docx", ".pptx", ".xlsx")

    def __init__(self, converter: Any | None = None) -> None:
        self._converter = converter if converter is not None else self._build_converter()

    def supported_media_types(self) -> Sequence[str]:
        return self.MEDIA_TYPES

    def parse(self, source: FileReference) -> ParsedDocument:
        path = self._local_path(source.storage_uri)
        self._validate_source(source, path)
        result = self._converter.convert(path)
        document = result.document

        blocks = tuple(self._normalize_items(document))
        warnings: list[str] = []
        if path.suffix.lower() == ".pdf":
            warnings.append(
                "Docling OCR is disabled in this adapter; scanned pages may require OCRProvider."
            )

        return ParsedDocument(
            source=source,
            blocks=blocks,
            parser="docling",
            parser_version=self._docling_version(),
            metadata={
                "normalized_schema": "file-first-document",
                "normalized_schema_version": "1.0",
                "source_format": path.suffix.lower().lstrip("."),
                "page_count": len(getattr(document, "pages", {}) or {}),
            },
            warnings=tuple(warnings),
        )

    @classmethod
    def _build_converter(cls) -> Any:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as exc:
            raise RuntimeError(
                "Docling is optional. Install the pinned adapter dependency with "
                "`pip install -e .[docling]`."
            ) from exc

        pdf_options = PdfPipelineOptions()
        pdf_options.do_ocr = False
        pdf_options.do_code_enrichment = False
        pdf_options.do_formula_enrichment = False
        pdf_options.do_picture_classification = False
        pdf_options.do_picture_description = False

        return DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.DOCX,
                InputFormat.PPTX,
                InputFormat.XLSX,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
            },
        )

    @classmethod
    def _validate_source(cls, source: FileReference, path: Path) -> None:
        extension = path.suffix.lower()
        if source.media_type not in cls.MEDIA_TYPES or extension not in cls.EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"Docling adapter does not support {source.media_type!r} / {extension!r}."
            )
        if not path.is_file():
            raise FileNotFoundError(path)

    @staticmethod
    def _local_path(storage_uri: str) -> Path:
        direct = Path(storage_uri)
        if direct.is_absolute():
            return direct

        parsed = urlparse(storage_uri)
        if parsed.scheme != "file":
            raise NonLocalFileError(
                "DoclingFileParser accepts local/file:// storage references only; "
                "materialize object storage to a worker-local file first."
            )

        path_text = unquote(parsed.path)
        if parsed.netloc:
            path_text = f"//{parsed.netloc}{path_text}"
        if len(path_text) >= 3 and path_text[0] == "/" and path_text[2] == ":":
            path_text = path_text[1:]
        return Path(path_text)

    def _normalize_items(self, document: Any) -> Iterable[ContentBlock]:
        for index, entry in enumerate(document.iterate_items()):
            item = entry[0] if isinstance(entry, tuple) else entry
            level = entry[1] if isinstance(entry, tuple) and len(entry) > 1 else None
            kind = self._label(item)
            text = self._item_text(item, document)
            bounds, provenance = self._provenance(item, document)
            block_id = str(getattr(item, "self_ref", None) or f"block-{index + 1}")

            metadata: dict[str, Any] = {"order": index}
            if level is not None:
                metadata["level"] = level
            parent = getattr(item, "parent", None)
            parent_ref = getattr(parent, "cref", None)
            if parent_ref:
                metadata["parent_id"] = str(parent_ref)
            if provenance:
                metadata["provenance"] = provenance
            table = self._table_data(item)
            if table is not None:
                metadata["table"] = table

            yield ContentBlock(
                block_id=block_id,
                kind=kind,
                text=text,
                bounds=bounds,
                metadata=metadata,
            )

    @staticmethod
    def _label(item: Any) -> str:
        label = getattr(item, "label", None)
        return str(getattr(label, "value", label) or "unknown")

    @staticmethod
    def _item_text(item: Any, document: Any) -> str | None:
        text = getattr(item, "text", None)
        if text is not None:
            return str(text)
        export = getattr(item, "export_to_markdown", None)
        if callable(export):
            try:
                return str(export(doc=document))
            except TypeError:
                return str(export(document))
        return None

    @staticmethod
    def _table_data(item: Any) -> dict[str, Any] | None:
        data = getattr(item, "data", None)
        cells = getattr(data, "table_cells", None)
        if cells is None:
            return None
        normalized_cells = []
        for cell in cells:
            normalized_cells.append(
                {
                    "text": str(getattr(cell, "text", "")),
                    "row_start": getattr(cell, "start_row_offset_idx", None),
                    "row_end": getattr(cell, "end_row_offset_idx", None),
                    "column_start": getattr(cell, "start_col_offset_idx", None),
                    "column_end": getattr(cell, "end_col_offset_idx", None),
                    "is_column_header": bool(getattr(cell, "column_header", False)),
                    "is_row_header": bool(getattr(cell, "row_header", False)),
                }
            )
        return {
            "rows": getattr(data, "num_rows", None),
            "columns": getattr(data, "num_cols", None),
            "cells": normalized_cells,
        }

    @classmethod
    def _provenance(
        cls, item: Any, document: Any
    ) -> tuple[BoundingBox | None, list[dict[str, Any]]]:
        normalized: list[dict[str, Any]] = []
        first_bounds: BoundingBox | None = None
        for prov in getattr(item, "prov", ()) or ():
            page = int(getattr(prov, "page_no", 1))
            bbox = getattr(prov, "bbox", None)
            bounds = cls._bounds(bbox, page, document) if bbox is not None else None
            charspan = getattr(prov, "charspan", None)
            record: dict[str, Any] = {"page": page}
            if bounds is not None:
                record["bounds"] = {
                    "left": bounds.left,
                    "top": bounds.top,
                    "right": bounds.right,
                    "bottom": bounds.bottom,
                }
                first_bounds = first_bounds or bounds
            if charspan is not None:
                record["character_span"] = list(charspan)
            normalized.append(record)
        return first_bounds, normalized

    @staticmethod
    def _bounds(bbox: Any, page: int, document: Any) -> BoundingBox:
        left = float(bbox.l)
        top = float(bbox.t)
        right = float(bbox.r)
        bottom = float(bbox.b)
        origin = str(getattr(getattr(bbox, "coord_origin", None), "value", "TOPLEFT"))
        if origin.upper().replace("_", "") == "BOTTOMLEFT":
            page_data = (getattr(document, "pages", {}) or {}).get(page)
            height = float(getattr(getattr(page_data, "size", None), "height"))
            top, bottom = height - top, height - bottom
        return BoundingBox(left, top, right, bottom, page)

    @staticmethod
    def _docling_version() -> str | None:
        try:
            return version("docling")
        except PackageNotFoundError:
            return None
