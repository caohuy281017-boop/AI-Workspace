# Architecture

## Goal

Build a simple file-processing core that owns product workflows while treating document engines and AI vendors as replaceable infrastructure. The initial implementation is a modular monolith; service boundaries can be extracted only when load or team ownership justifies it.

## High-level flow

```text
Upload/API
   |
   v
File intake -> type detection -> document classification -> workflow selection
                                                       |
                                                       v
                                      parse -> OCR if required -> extract
                                                       |
                                                       v
                                             validate -> review -> export
```

Each stage reads and produces our own domain models. Provider-specific objects must be translated at the adapter boundary.

## Layers

### Domain

Stable, provider-neutral types such as `FileReference`, `ParsedDocument`, `DocumentClassification`, `ExtractionResult`, and `ExportArtifact`. Domain models must not import SDKs, web frameworks, databases, or open-source engines.

### Ports

Interfaces that describe capabilities required by the application:

- `FileParser`: converts a supported file into a provider-neutral parsed document.
- `OCRProvider`: recognizes text and layout from files or pages that require OCR.
- `LLMProvider`: executes provider-neutral language-model requests through the LLM gateway.
- `DocumentClassifier`: determines the business document type and confidence.
- `ExtractionProvider`: extracts a requested schema from a parsed document.
- `ExportProvider`: creates a downloadable artifact from approved records.

Ports deliberately expose capability and result metadata so jobs can record which adapter/model produced an artifact.

### Application

Use cases coordinate ports, enforce workflow order, persist job state, and apply validation rules. They do not contain vendor SDK calls. The first use case will be `InvoiceBatchWorkflow`.

### Adapters

Adapters implement ports for external systems. Future examples might be a Docling parser adapter, PaddleOCR adapter, hosted/local LLM gateway adapters, and an XLSX exporter. Adapters may run in-process, as subprocesses/containers, or behind HTTP without changing application contracts.

The first implementation is `DoclingFileParser`. It is an optional dependency and is selected through dependency injection. It emits only `ParsedDocument` and `ContentBlock`; no Docling type may cross into application/domain code or persistence.

### Delivery and infrastructure

HTTP endpoints, background job execution, object storage, relational persistence, authentication, and observability live at the outside edge. These choices are intentionally deferred in the current skeleton.

## Interface behavior

### FileParser

- Accepts a `FileReference`, not a vendor object.
- Returns ordered content blocks, metadata, warnings, and provenance.
- Declares supported media types.
- Does not silently call an LLM.

### OCRProvider

- Accepts a file and optional page selection/language hints.
- Returns text regions, confidence, and page coordinates when available.
- Records engine and model identity.

### LLMProvider

- Accepts neutral messages, model capability hints, and structured-output schema.
- Returns content, usage, finish reason, provider/model identity, and raw-provider data only in diagnostic metadata where safe.
- Centralizes timeouts, retries, budgets, redaction, telemetry, and provider policy in an LLM gateway implementation.

### DocumentClassifier

- Returns a controlled document-type value, confidence, and evidence.
- Can begin as deterministic MIME/filename/content rules and later use models.
- Classification selects a workflow; it must not execute that workflow.

### ExtractionProvider

- Accepts a parsed document and a versioned target schema.
- Returns structured values, field-level evidence/confidence when possible, and warnings.
- Schema validation remains an application responsibility.

### ExportProvider

- Accepts approved records and export options.
- Returns artifact bytes or a storage reference with media type and checksum.
- Export must use reviewed values, never stale extraction output.

## Processing and data rules

- Original uploads are immutable; corrections create new artifact/review versions.
- Every job and artifact has a workspace/tenant identifier.
- Every derived artifact records source file IDs, adapter name/version, model identifier where relevant, schema version, timestamps, and warnings.
- Batch failures are isolated per file. A batch summarizes partial success.
- Long-running processing will use background jobs with idempotency keys and bounded retries.
- Persist application/domain representations, not serialized vendor SDK objects.
- Treat uploaded content and extracted text as untrusted input.

## Engine selection

Selection happens through configuration and dependency injection. The application depends only on a port; a registry can choose an adapter by capability, MIME type, tenant policy, cost, or availability. Do not build a dynamic plugin platform yet.

```python
workflow = InvoiceBatchWorkflow(
    classifier=classifier_adapter,
    parser=parser_adapter,
    extractor=extraction_adapter,
)
```

### Replacing a parser

A replacement must implement `FileParser`, pass shared contract/golden-file tests, and produce the same normalized schema version. Configuration changes the injected adapter; workflows remain untouched. Parser name/version is stored on each artifact so old outputs can be audited or selectively reprocessed. The migration does not require retaining Docling's document model.

## Third-party boundary and licensing gate

Before an adapter or dependency is accepted:

1. Pin the repository commit/tag and package version under review.
2. Inspect the repository `LICENSE` and notices.
3. Identify every downloaded/bundled model and inspect its separate license and acceptable-use terms.
4. Review important direct dependencies and any copyleft/network-copyleft implications.
5. Record distribution mode: library, subprocess, container, hosted API, or research only.
6. Record attribution/notice/source-offer obligations.
7. Add the evidence and decision to `docs/REPO_MAP.md`.
8. Obtain legal review for ambiguous, custom, open-core, or copyleft terms.

Repository code is never copied into core merely as a shortcut. Permissively licensed projects are still integrated through adapters.

## Repository layout

```text
backend/
  src/file_first_ai/
    domain/       # provider-neutral models
    ports/        # interfaces owned by us
    application/  # workflows/use cases
    adapters/     # future third-party implementations
  tests/
docs/             # product, architecture, repository/license decisions
frontend/         # later review UI
integrations/     # deployment/integration assets added after approval
research/         # evaluations; no production imports
```

## Deferred decisions

- Web framework, database, queue, and object store.
- Exact invoice schema and validation jurisdiction.
- Sync versus async API surface.
- Parser/OCR/LLM vendors.
- Adapter isolation level.

These are deferred to keep the first implementation modular without creating unused abstractions.
