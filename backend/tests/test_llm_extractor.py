"""TDD tests for LLM Extraction Adapter.

These tests run entirely with mock/stub objects — no real LLM is called.
They verify contract behaviour: correct output types, field mapping,
partial data handling, and error isolation.

Run with:
    pytest tests/test_llm_extractor.py -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from file_first_ai.domain import (
    ContentBlock,
    ExtractionResult,
    FileReference,
    InvoiceLineItem,
    InvoiceRecord,
    LLMRequest,
    LLMResponse,
    ParsedDocument,
)
from file_first_ai.adapters.invoice_schema import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    build_extraction_prompt,
)


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

def make_file_ref(file_id: str = "f-001") -> FileReference:
    return FileReference(
        file_id=file_id,
        workspace_id="ws-001",
        name="invoice.pdf",
        media_type="application/pdf",
        size_bytes=12345,
        storage_uri=f"object://ws-001/{file_id}",
    )


def make_parsed_doc(text: str, file_id: str = "f-001") -> ParsedDocument:
    return ParsedDocument(
        source=make_file_ref(file_id),
        blocks=(ContentBlock("b1", "text", text=text),),
        parser="fake-parser",
    )


class StubLLMProvider:
    """Returns a fixed JSON payload as LLM response."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.last_request: LLMRequest | None = None

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.last_request = request
        return LLMResponse(
            content=json.dumps(self._payload),
            provider="stub",
            model="stub-model",
            finish_reason="stop",
        )


class ErrorLLMProvider:
    """Simulates a broken LLM provider."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise RuntimeError("LLM connection timeout")


# ---------------------------------------------------------------------------
# Import the adapter under test (after mocks are defined)
# ---------------------------------------------------------------------------

from file_first_ai.adapters.llm_extractor import LLMExtractionAdapter  # noqa: E402


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestLLMExtractionAdapterHappyPath(unittest.TestCase):

    def _make_adapter(self, payload: dict[str, Any]) -> LLMExtractionAdapter:
        return LLMExtractionAdapter(llm=StubLLMProvider(payload))

    def test_returns_extraction_result_type(self):
        adapter = self._make_adapter({"total_amount": 500.0, "items": []})
        doc = make_parsed_doc("Total: 500")
        result = adapter.extract(doc, schema_name=SCHEMA_NAME, schema_version=SCHEMA_VERSION, schema={})
        self.assertIsInstance(result, ExtractionResult)

    def test_extraction_result_has_correct_schema_metadata(self):
        adapter = self._make_adapter({"total_amount": 100.0, "items": []})
        doc = make_parsed_doc("Total: 100")
        result = adapter.extract(doc, schema_name=SCHEMA_NAME, schema_version=SCHEMA_VERSION, schema={})
        self.assertEqual(result.schema_name, SCHEMA_NAME)
        self.assertEqual(result.schema_version, SCHEMA_VERSION)
        self.assertEqual(result.source_file_id, doc.source.file_id)

    def test_maps_scalar_fields_into_values(self):
        payload = {
            "supplier_name": "ACME Corp",
            "supplier_tax_id": "0123456789",
            "invoice_number": "INV-001",
            "invoice_date": "2026-08-01",
            "currency": "USD",
            "subtotal": 900.0,
            "tax_amount": 90.0,
            "total_amount": 990.0,
            "items": [],
        }
        adapter = self._make_adapter(payload)
        doc = make_parsed_doc("Invoice from ACME Corp, Total: 990")
        result = adapter.extract(doc, schema_name=SCHEMA_NAME, schema_version=SCHEMA_VERSION, schema={})
        self.assertEqual(result.values["supplier_name"], "ACME Corp")
        self.assertEqual(result.values["total_amount"], 990.0)
        self.assertEqual(result.values["currency"], "USD")

    def test_maps_line_items_array(self):
        payload = {
            "total_amount": 300.0,
            "items": [
                {"description": "Widget A", "quantity": 2.0, "unit_price": 100.0, "amount": 200.0},
                {"description": "Widget B", "quantity": 1.0, "unit_price": 100.0, "amount": 100.0},
            ],
        }
        adapter = self._make_adapter(payload)
        doc = make_parsed_doc("Widget A x2 + Widget B x1 = 300")
        result = adapter.extract(doc, schema_name=SCHEMA_NAME, schema_version=SCHEMA_VERSION, schema={})
        items = result.values["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["description"], "Widget A")
        self.assertEqual(items[1]["amount"], 100.0)

    def test_sends_document_text_in_llm_request(self):
        stub = StubLLMProvider({"total_amount": 42.0, "items": []})
        adapter = LLMExtractionAdapter(llm=stub)
        doc = make_parsed_doc("unique-marker-text-xyz")
        adapter.extract(doc, schema_name=SCHEMA_NAME, schema_version=SCHEMA_VERSION, schema={})
        prompt_content = stub.last_request.messages[0].content
        self.assertIn("unique-marker-text-xyz", prompt_content)

    def test_provider_name_recorded_in_result(self):
        adapter = self._make_adapter({"total_amount": 1.0, "items": []})
        doc = make_parsed_doc("Total: 1")
        result = adapter.extract(doc, schema_name=SCHEMA_NAME, schema_version=SCHEMA_VERSION, schema={})
        self.assertTrue(len(result.provider) > 0)


class TestLLMExtractionAdapterPartialData(unittest.TestCase):

    def test_null_fields_produce_none_in_values(self):
        payload = {"supplier_name": None, "total_amount": 50.0, "items": []}
        adapter = LLMExtractionAdapter(llm=StubLLMProvider(payload))
        doc = make_parsed_doc("Total: 50")
        result = adapter.extract(doc, schema_name=SCHEMA_NAME, schema_version=SCHEMA_VERSION, schema={})
        self.assertIsNone(result.values["supplier_name"])

    def test_missing_total_produces_warning(self):
        # LLM returns a response with no total_amount
        payload = {"items": [{"description": "Something"}]}
        adapter = LLMExtractionAdapter(llm=StubLLMProvider(payload))
        doc = make_parsed_doc("Something 100")
        result = adapter.extract(doc, schema_name=SCHEMA_NAME, schema_version=SCHEMA_VERSION, schema={})
        self.assertTrue(len(result.warnings) > 0)

    def test_empty_items_list_is_valid(self):
        payload = {"total_amount": 200.0, "items": []}
        adapter = LLMExtractionAdapter(llm=StubLLMProvider(payload))
        doc = make_parsed_doc("Total 200")
        result = adapter.extract(doc, schema_name=SCHEMA_NAME, schema_version=SCHEMA_VERSION, schema={})
        self.assertEqual(result.values["items"], [])
        self.assertEqual(result.errors if hasattr(result, "errors") else (), ())


class TestLLMExtractionAdapterErrorHandling(unittest.TestCase):

    def test_llm_exception_produces_result_with_warning(self):
        adapter = LLMExtractionAdapter(llm=ErrorLLMProvider())
        doc = make_parsed_doc("Total: 999")
        # Should NOT raise — errors are captured in warnings
        result = adapter.extract(doc, schema_name=SCHEMA_NAME, schema_version=SCHEMA_VERSION, schema={})
        self.assertIsInstance(result, ExtractionResult)
        self.assertTrue(len(result.warnings) > 0)

    def test_malformed_json_response_produces_warning(self):
        class BadJsonLLM:
            def complete(self, request):
                return LLMResponse(
                    content="this is not JSON {{{",
                    provider="bad",
                    model="bad-model",
                )

        adapter = LLMExtractionAdapter(llm=BadJsonLLM())
        doc = make_parsed_doc("Total: 100")
        result = adapter.extract(doc, schema_name=SCHEMA_NAME, schema_version=SCHEMA_VERSION, schema={})
        self.assertIsInstance(result, ExtractionResult)
        self.assertTrue(len(result.warnings) > 0)


class TestBuildExtractionPrompt(unittest.TestCase):

    def test_prompt_contains_document_text(self):
        prompt = build_extraction_prompt("Invoice No. 123 Total: 500")
        self.assertIn("Invoice No. 123 Total: 500", prompt)

    def test_prompt_is_non_empty_string(self):
        prompt = build_extraction_prompt("text")
        self.assertIsInstance(prompt, str)
        self.assertTrue(len(prompt) > 50)


if __name__ == "__main__":
    unittest.main()
