"""Small, serializable models shared by application ports.

These models intentionally contain no objects from vendor SDKs or frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence


JsonObject = Mapping[str, Any]


class DocumentType(StrEnum):
    INVOICE = "invoice"
    BANK_STATEMENT = "bank_statement"
    CONTRACT = "contract"
    PRESENTATION = "presentation"
    GENERAL_DOCUMENT = "general_document"
    AUDIO_RECORDING = "audio_recording"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class FileReference:
    """Reference to an immutable uploaded file in application-controlled storage."""

    file_id: str
    workspace_id: str
    name: str
    media_type: str
    size_bytes: int
    storage_uri: str
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Top-left-origin coordinates on a one-based page number."""

    left: float
    top: float
    right: float
    bottom: float
    page: int


@dataclass(frozen=True, slots=True)
class ContentBlock:
    block_id: str
    kind: str
    text: str | None = None
    bounds: BoundingBox | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    source: FileReference
    blocks: Sequence[ContentBlock]
    parser: str
    parser_version: str | None = None
    metadata: JsonObject = field(default_factory=dict)
    warnings: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class OCRRegion:
    text: str
    confidence: float | None = None
    bounds: BoundingBox | None = None


@dataclass(frozen=True, slots=True)
class OCRResult:
    source: FileReference
    regions: Sequence[OCRRegion]
    provider: str
    model: str | None = None
    warnings: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DocumentClassification:
    document_type: DocumentType
    confidence: float
    classifier: str
    evidence: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    source_file_id: str
    schema_name: str
    schema_version: str
    values: JsonObject
    provider: str
    field_confidence: Mapping[str, float] = field(default_factory=dict)
    evidence: Mapping[str, Sequence[str]] = field(default_factory=dict)
    warnings: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    name: str
    media_type: str
    content: bytes
    exporter: str
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class LLMRequest:
    messages: Sequence[LLMMessage]
    capability: str
    response_schema: JsonObject | None = None
    temperature: float = 0.0
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str
    provider: str
    model: str
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InvoiceLineItem:
    """A single line item extracted from an invoice.

    All numeric fields are None when the engine could not parse the value.
    """

    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None
    currency: str | None = None


@dataclass(frozen=True, slots=True)
class InvoiceRecord:
    """Structured invoice data produced by the extraction pipeline.

    This is a domain model: it must not reference any vendor SDK or adapter.
    ``schema_version`` identifies the extraction schema used so stored records
    can be selectively reprocessed when the schema evolves.
    """

    source_file_id: str
    schema_version: str = "1.0"
    supplier_name: str | None = None
    supplier_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None          # ISO 8601 date string
    currency: str | None = None              # ISO 4217 code, e.g. "VND", "USD"
    subtotal: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    items: Sequence[InvoiceLineItem] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)
