"""Invoice JSON Schema v1.0 for LLM structured extraction.

This module is the single source of truth for the invoice extraction schema.
It lives in adapters/ because it is consumed by the LLM adapter.
The schema itself is plain Python dicts — no vendor types cross this boundary.

Design inspired by TaxHacker (MIT) schema builder pattern.
"""

from __future__ import annotations

from typing import Any

SCHEMA_NAME = "invoice"
SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Invoice JSON Schema v1.0
# ---------------------------------------------------------------------------
# Sent to the LLM as a structured-output / function-calling schema.
# All fields except "total_amount" and "items" are optional so that
# partial invoices (e.g. receipts without supplier tax ID) still produce
# usable results.
# ---------------------------------------------------------------------------

INVOICE_SCHEMA_V1: dict[str, Any] = {
    "type": "object",
    "properties": {
        "supplier_name": {
            "type": ["string", "null"],
            "description": (
                "Full legal name or trading name of the supplier / seller / vendor. "
                "Use null if not found."
            ),
        },
        "supplier_tax_id": {
            "type": ["string", "null"],
            "description": (
                "Tax identification number, VAT number, or business registration number "
                "of the supplier. Use null if not found."
            ),
        },
        "invoice_number": {
            "type": ["string", "null"],
            "description": (
                "Invoice number, receipt number, or document reference. "
                "Use null if not found."
            ),
        },
        "invoice_date": {
            "type": ["string", "null"],
            "description": (
                "Date the invoice was issued, in ISO 8601 format (YYYY-MM-DD). "
                "Convert any local date format to ISO 8601. Use null if not found."
            ),
        },
        "currency": {
            "type": ["string", "null"],
            "description": (
                "ISO 4217 currency code (e.g. 'VND', 'USD', 'EUR'). "
                "Infer from currency symbols if the code is not explicit. "
                "Use null if ambiguous."
            ),
        },
        "subtotal": {
            "type": ["number", "null"],
            "description": (
                "Total amount before tax. Use null if not stated separately."
            ),
        },
        "tax_amount": {
            "type": ["number", "null"],
            "description": (
                "VAT or other tax amount. Use null if not stated separately."
            ),
        },
        "total_amount": {
            "type": ["number", "null"],
            "description": (
                "Final payable total including all taxes. "
                "This is the most important field — extract it even when other fields "
                "are missing."
            ),
        },
        "items": {
            "type": "array",
            "description": (
                "All individual line items, products, or services listed on the invoice. "
                "Extract EVERY item found. Use an empty array [] only if there are "
                "genuinely no line items (e.g. a simple ATM receipt)."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Name or description of the product or service.",
                    },
                    "quantity": {
                        "type": ["number", "null"],
                        "description": "Quantity or units. Use null if not stated.",
                    },
                    "unit_price": {
                        "type": ["number", "null"],
                        "description": "Price per unit. Use null if not stated.",
                    },
                    "amount": {
                        "type": ["number", "null"],
                        "description": "Total amount for this line item.",
                    },
                },
                "required": ["description"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["total_amount", "items"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT_TEMPLATE = """\
You are an expert accounting assistant specializing in invoice data extraction.

Extract all invoice information from the following document text.
Return data strictly according to the JSON schema provided.

Rules:
- Use null for any field that cannot be found or is ambiguous.
- Convert all dates to ISO 8601 format (YYYY-MM-DD).
- Extract EVERY line item found on the document.
- Do not invent or hallucinate values not present in the text.
- Numbers must be plain numeric values (no currency symbols, no commas as thousands separators).

Document text:
---
{document_text}
---
"""


def build_extraction_prompt(document_text: str) -> str:
    """Return a filled extraction prompt for the given document text."""
    return EXTRACTION_PROMPT_TEMPLATE.format(document_text=document_text)
