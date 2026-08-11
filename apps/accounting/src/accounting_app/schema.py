"""Invoice JSON Schema v2.0 for LLM structured extraction.

This module is the single source of truth for the invoice extraction schema.

Changes from v1.0 → v2.0:
- Added: invoice_template_number, invoice_series (mẫu số / ký hiệu HĐ)
- Added: buyer_name, buyer_tax_id
- Added: discount_amount, fees
- Added: tax_breakdown (list of per-rate tax rows)
- Extended line items: unit, tax_rate, discount_rate, line_type
- Rule: ALL numeric fields use null (never 0) when not found in document
- Rule: currency uses null (never "VND") when ambiguous
"""

from __future__ import annotations

from typing import Any

SCHEMA_NAME = "invoice"
SCHEMA_VERSION = "2.0"

# ---------------------------------------------------------------------------
# Invoice JSON Schema v2.0
# ---------------------------------------------------------------------------
# Sent to the LLM as a structured-output / function-calling schema.
#
# NULL POLICY (enforced by schema, normalizer, and prompt):
#   - Every numeric field returns null when the value cannot be found or parsed.
#   - Every string field returns null when the value cannot be found.
#   - Line items that cannot be read are omitted entirely — never invented.
#   - currency returns null when ambiguous (not defaulted to "VND").
# ---------------------------------------------------------------------------

INVOICE_SCHEMA_V2: dict[str, Any] = {
    "type": "object",
    "properties": {
        # ── Supplier / Seller ──────────────────────────────────────────────
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
                "Vietnamese MST (10 digits for company, 13 digits 'xxxxxxxxx-xxx' for branch) "
                "or foreign VAT/business registration number of the supplier. "
                "Use null if not found."
            ),
        },
        # ── Buyer / Customer ───────────────────────────────────────────────
        "buyer_name": {
            "type": ["string", "null"],
            "description": "Full legal name of the buyer / purchaser. Use null if not found.",
        },
        "buyer_tax_id": {
            "type": ["string", "null"],
            "description": "Tax ID / MST of the buyer. Use null if not found.",
        },
        # ── Invoice Identity ───────────────────────────────────────────────
        "invoice_template_number": {
            "type": ["string", "null"],
            "description": (
                "Vietnamese Mẫu số (template number) of the invoice, e.g. '1/001', '2/001'. "
                "Use null if not present."
            ),
        },
        "invoice_series": {
            "type": ["string", "null"],
            "description": (
                "Vietnamese Ký hiệu (series/symbol) of the invoice, e.g. 'AA/25E', 'C25TAA'. "
                "Use null if not present."
            ),
        },
        "invoice_number": {
            "type": ["string", "null"],
            "description": (
                "Invoice number, receipt number, or document reference (Số hóa đơn). "
                "Use null if not found."
            ),
        },
        "invoice_date": {
            "type": ["string", "null"],
            "description": (
                "Date the invoice was issued, in ISO 8601 format (YYYY-MM-DD). "
                "Convert any local date format (dd/mm/yyyy, 'ngày dd tháng mm năm yyyy') "
                "to ISO 8601. Use null if not found."
            ),
        },
        "currency": {
            "type": ["string", "null"],
            "description": (
                "ISO 4217 currency code (e.g. 'VND', 'USD', 'EUR'). "
                "Infer from currency symbols only when unambiguous. "
                "Use null if ambiguous or not stated."
            ),
        },
        # ── Financial Amounts ──────────────────────────────────────────────
        "subtotal": {
            "type": ["number", "null"],
            "description": (
                "Total amount before tax (Cộng tiền hàng / Tiền trước thuế). "
                "Use null if not stated separately."
            ),
        },
        "discount_amount": {
            "type": ["number", "null"],
            "description": (
                "Total discount amount applied (Chiết khấu / Giảm giá). "
                "Use null if not applicable or not stated."
            ),
        },
        "fees": {
            "type": ["number", "null"],
            "description": (
                "Additional fees, surcharges, or adjustments. "
                "Use null if not applicable."
            ),
        },
        "tax_amount": {
            "type": ["number", "null"],
            "description": (
                "Total VAT / tax amount (Tiền thuế GTGT). "
                "Use null if not stated separately."
            ),
        },
        "total_amount": {
            "type": ["number", "null"],
            "description": (
                "Final payable total including all taxes (Tổng cộng tiền thanh toán). "
                "This is the most important field — extract it even when other fields "
                "are missing. Use null if not found."
            ),
        },
        # ── Tax Breakdown ──────────────────────────────────────────────────
        "tax_breakdown": {
            "type": "array",
            "description": (
                "Per-rate tax breakdown rows when the invoice shows multiple tax rates. "
                "Use empty array [] if the invoice has a single uniform tax rate."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "tax_rate": {
                        "type": ["number", "null"],
                        "description": "Tax rate as decimal (e.g. 0.1 for 10%, 0.0 for 0%). Use null if not stated.",
                    },
                    "taxable_amount": {
                        "type": ["number", "null"],
                        "description": "Amount subject to this tax rate. Use null if not stated.",
                    },
                    "tax_amount": {
                        "type": ["number", "null"],
                        "description": "Tax amount at this rate. Use null if not stated.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        # ── Line Items ─────────────────────────────────────────────────────
        "items": {
            "type": "array",
            "description": (
                "All individual line items, products, or services listed on the invoice. "
                "Extract EVERY item found. Use an empty array [] ONLY if there are "
                "genuinely no line items (e.g. a simple ATM receipt). "
                "NEVER invent or fabricate items."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": ["string", "null"],
                        "description": "Name or description of the product or service. Use null if not readable.",
                    },
                    "unit": {
                        "type": ["string", "null"],
                        "description": "Unit of measure (Đơn vị tính), e.g. 'cái', 'kg', 'lần'. Use null if not stated.",
                    },
                    "quantity": {
                        "type": ["number", "null"],
                        "description": "Quantity or units (Số lượng). Use null if not stated.",
                    },
                    "unit_price": {
                        "type": ["number", "null"],
                        "description": "Price per unit (Đơn giá). Use null if not stated.",
                    },
                    "discount_rate": {
                        "type": ["number", "null"],
                        "description": "Line-item discount rate as decimal (e.g. 0.05 for 5%). Use null if not applicable.",
                    },
                    "tax_rate": {
                        "type": ["number", "null"],
                        "description": "VAT rate for this line as decimal (e.g. 0.1 for 10%, 0.0 for exempt). Use null if not stated.",
                    },
                    "amount": {
                        "type": ["number", "null"],
                        "description": "Total amount for this line item before tax. Use null if not stated.",
                    },
                    "line_type": {
                        "type": ["string", "null"],
                        "description": (
                            "Type of line: 'normal' for standard goods/services, "
                            "'discount' for discount lines, 'adjustment' for debit/credit adjustments. "
                            "Use null if unclear."
                        ),
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        # ── Custom Fields (injected at runtime by service) ─────────────────
        "custom_fields": {
            "type": "object",
            "description": "Additional fields configured by the workspace. Use null for each if not found.",
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}

# Keep v1 alias for backward compatibility during migration period
INVOICE_SCHEMA_V1 = INVOICE_SCHEMA_V2


# ---------------------------------------------------------------------------
# Extraction Prompt Template v2
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT_TEMPLATE = """\
You are an expert accounting assistant specializing in Vietnamese and international invoice data extraction.

Extract all invoice information from the document and return it as a strict JSON object matching the schema.

CRITICAL RULES — follow exactly:
1. Use null for ANY field that cannot be found, is ambiguous, or is unreadable. NEVER invent values.
2. NEVER default currency to "VND" — use null if not explicitly stated or clearly inferable.
3. NEVER create line items with fabricated descriptions, quantities, prices, or amounts.
   If a line item field is not readable, use null for that field.
4. Convert all dates to ISO 8601 format (YYYY-MM-DD).
5. Numbers must be plain numeric values (no currency symbols, no thousands-separator commas).
6. For Vietnamese invoices: extract Mẫu số (invoice_template_number) and Ký hiệu (invoice_series) when present.
7. If the invoice has multiple VAT rates, populate tax_breakdown.
8. Return ONLY valid JSON matching the schema. No markdown, no explanation.

Document:
---
{document_text}
---
"""


def build_extraction_prompt(document_text: str) -> str:
    """Return a filled extraction prompt for the given document text."""
    return EXTRACTION_PROMPT_TEMPLATE.format(document_text=document_text)
