"""Invoice-specific domain models for app-accounting-batch.

These models extend the neutral platform_core domain with invoice-specific
fields. They live in this app package because they are not shared with
other applications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True, slots=True)
class InvoiceLineItem:
    """A single line item extracted from an invoice."""

    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None
    currency: str | None = None


@dataclass(frozen=True, slots=True)
class InvoiceRecord:
    """Structured invoice data produced by the extraction pipeline.

    ``schema_version`` identifies the extraction schema used so stored
    records can be selectively reprocessed when the schema evolves.
    """

    source_file_id: str
    schema_version: str = "1.0"
    supplier_name: str | None = None
    supplier_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None       # ISO 8601 date string
    currency: str | None = None           # ISO 4217, e.g. "VND", "USD"
    subtotal: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    items: Sequence[InvoiceLineItem] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)
