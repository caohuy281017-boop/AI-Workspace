"""LLM Extraction Adapter — implements ExtractionProvider port.

Uses an injected LLMProvider to send invoice extraction prompts and parses
the structured JSON response into an ExtractionResult.

Design notes:
- All errors (LLM failures, JSON parse errors, missing required fields) are
  captured in ExtractionResult.warnings rather than raised, so the batch
  workflow can continue processing other files.
- No Docling / OpenAI / Google types cross this module's boundary.
- The prompt and schema are defined in ``adapters/invoice_schema.py``.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping

from platform_core.domain import (
    ExtractionResult,
    LLMMessage,
    LLMRequest,
    ParsedDocument,
)
from accounting_app.schema import (
    INVOICE_SCHEMA_V1,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    build_extraction_prompt,
)
from platform_core.ports import LLMProvider

logger = logging.getLogger(__name__)

_PROVIDER_NAME = "LLMExtractionAdapter"
_REQUIRED_FIELDS = ("total_amount", "items")


def _blocks_to_text(document: ParsedDocument) -> str:
    """Concatenate all text blocks from a parsed document into a single string."""
    parts: list[str] = []
    for block in document.blocks:
        if block.text:
            parts.append(block.text.strip())
    return "\n\n".join(parts)


def _parse_llm_response(raw_content: str) -> tuple[dict[str, Any], list[str]]:
    """Parse raw LLM response text into a dict and a list of warnings.

    Handles:
    - Plain JSON
    - JSON wrapped in Markdown code fences (```json ... ```)
    """
    warnings: list[str] = []
    text = raw_content.strip()

    # Strip Markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        inner = [ln for ln in lines if not ln.startswith("```")]
        text = "\n".join(inner).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        warnings.append(f"LLM returned non-JSON response: {exc}. Raw: {raw_content[:200]!r}")
        return {}, warnings

    if not isinstance(data, dict):
        warnings.append(f"Expected a JSON object, got {type(data).__name__}.")
        return {}, warnings

    return data, warnings


def _validate_and_warn(data: dict[str, Any]) -> list[str]:
    """Check required fields and return any validation warnings."""
    warnings: list[str] = []
    for field in _REQUIRED_FIELDS:
        if field not in data or data[field] is None:
            warnings.append(f"Required field '{field}' is missing or null in LLM extraction output.")
    return warnings


class LLMExtractionAdapter:
    """Implements ``ExtractionProvider`` using a configurable ``LLMProvider``.

    Usage::

        llm = MultiProviderLLMAdapter()   # configured via env vars
        extractor = LLMExtractionAdapter(llm=llm)
        result = extractor.extract(parsed_doc, schema_name="invoice", schema_version="1.0", schema={})
    """

    def __init__(self, *, llm: LLMProvider) -> None:
        self._llm = llm

    def extract(
        self,
        document: ParsedDocument,
        *,
        schema_name: str,
        schema_version: str,
        schema: Mapping[str, Any],
    ) -> ExtractionResult:
        """Extract invoice fields from a parsed document using the LLM.

        Errors are captured in ``warnings``; this method never raises.
        """
        warnings: list[str] = []
        values: dict[str, Any] = {}
        provider_label = _PROVIDER_NAME

        try:
            document_text = _blocks_to_text(document)
            if not document_text.strip():
                warnings.append("Document text is empty — extraction may produce poor results.")

            prompt = build_extraction_prompt(document_text)

            request = LLMRequest(
                messages=(LLMMessage(role="user", content=prompt),),
                capability="structured_extraction",
                response_schema=INVOICE_SCHEMA_V1,
                temperature=0.0,
            )

            response = self._llm.complete(request)
            provider_label = f"{_PROVIDER_NAME}/{response.provider}/{response.model}"

            parsed_data, parse_warnings = _parse_llm_response(response.content)
            warnings.extend(parse_warnings)

            if parsed_data:
                validation_warnings = _validate_and_warn(parsed_data)
                warnings.extend(validation_warnings)
                values = parsed_data

        except Exception as exc:  # noqa: BLE001
            msg = f"LLM extraction failed: {type(exc).__name__}: {exc}"
            logger.error(msg, exc_info=True)
            warnings.append(msg)

        return ExtractionResult(
            source_file_id=document.source.file_id,
            schema_name=schema_name,
            schema_version=schema_version,
            values=values,
            provider=provider_label,
            warnings=tuple(warnings),
        )
