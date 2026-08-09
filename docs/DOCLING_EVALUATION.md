# Docling FileParser Evaluation

Review date: 2026-08-08  
Adapter target: `docling==2.115.0`  
Upstream repository: https://github.com/docling-project/docling

This is an engineering review, not legal advice. Approval applies only to the narrow configuration below and must be repeated when the pin, models, OCR engine, enrichments, or distribution approach changes.

## Decision

Use Docling as the first optional `FileParser` adapter for PDF, DOCX, PPTX, and XLSX. Keep it outside the core domain and normalize all output into our `ParsedDocument`/`ContentBlock` schema.

Current approval scope:

- Docling Python package pinned to `2.115.0`.
- Local file conversion only.
- PDF standard pipeline with OCR and optional enrichments disabled.
- DOCX, PPTX, and XLSX built-in backends.
- No remote services.
- No copied Docling application/UI code or sample assets.

This is a conditional engineering approval, pending formal legal/dependency review before commercial release.

## Code license

Docling's current repository `LICENSE` is the MIT License, copyright IBM. Its current package metadata also declares MIT. Obligations are to retain the copyright and permission notice in copies/substantial portions; preserve the upstream license in the product's third-party notices when distributed.

Review evidence:

- https://github.com/docling-project/docling/blob/main/LICENSE
- https://github.com/docling-project/docling/blob/main/pyproject.toml

## Model considerations

Docling's code license does not automatically license model weights.

### Default PDF models

PDF processing requires separately downloaded model weights. The current Docling model bundle page identifies licenses including CDLA-Permissive-2.0 and Apache-2.0. The current default Heron layout model card declares Apache-2.0. The bundle also includes table-structure models, so the exact artifact files and revisions used in deployment must be captured rather than relying only on a repository-level badge.

- Bundle: https://huggingface.co/docling-project/docling-models
- Default layout model: https://huggingface.co/docling-project/docling-layout-heron

Deployment must prefetch a reviewed snapshot, record its Hugging Face revision/checksums, retain required notices, and disable implicit downloads. Re-review if Docling changes its default model set.

### Office formats

Docling's FAQ states DOCX/PPTX and other non-PDF document types do not require the PDF model weights. Their parser dependencies still require a dependency-license inventory.

### OCR and enrichments

OCR engines have their own code, native binary, language-data, and model licenses. Optional picture classification, formula/code recognition, picture description, and VLM pipelines also select separate models. Examples include:

- `CodeFormulaV2`: CDLA-Permissive-2.0 according to its model card.
- `DocumentFigureClassifier-v2.5`: MIT according to its model card.
- VLM and OCR choices: multiple independent licenses; not approved by this review.

The adapter therefore disables OCR, code/formula enrichment, picture classification, and picture description. Scanned PDFs may produce insufficient text and should later be routed to a separately approved `OCRProvider`.

## Important dependency considerations

Before production release, generate an SBOM/license report for the resolved `docling==2.115.0` environment. At minimum review direct/native processing dependencies, including `docling-core`, `docling-parse`, `docling-ibm-models`, PDF backends, Office parsers, PyTorch/torchvision, model download clients, OCR plugins if enabled, codecs, and any system packages used in the deployment image.

Versions resolved during the 2026-08-08 smoke test included:

| component | resolved version | preliminary package metadata | review state |
|---|---:|---|---|
| docling | 2.115.0 | Upstream repository/package declares MIT | Reviewed at top level |
| docling-slim | 2.115.0 | Upstream package declares MIT | NOTICE/license-file capture still required |
| docling-core | 2.91.0 | Docling-project component; metadata license field was blank in `pip show` | Inspect installed/upstream LICENSE before release |
| docling-parse | 7.11.0 | Docling-project native PDF component; metadata license field was blank | Inspect binary redistribution and LICENSE before release |
| docling-ibm-models | 3.13.3 | Inference package; metadata license field was blank | Inspect code license plus every model artifact |
| pypdfium2 | 5.12.1 | BSD-3-Clause / Apache-2.0 / dependency licenses | Review bundled PDFium notices |
| python-docx | 1.2.0 | MIT | Preliminary acceptable |
| python-pptx | 1.0.2 | MIT | Preliminary acceptable |
| openpyxl | 3.1.5 | MIT | Preliminary acceptable |
| torch / torchvision | 2.13.0 / 0.28.0 | Not concluded in this review | Review binaries and bundled third-party notices |
| rapidocr | 3.9.2 | Installed by the standard extra but disabled by adapter policy | Review or remove from production image |

The standard `docling` installation brings a significantly wider dependency set than the four-format adapter directly exercises. Before release, evaluate whether a narrower `docling-slim` extra can reduce the dependency and license surface without losing required formats.

Do not treat a successful `pip install` as license approval. Pin the complete lockfile and container digest.

## Data and network behavior

- The adapter accepts only worker-local paths or `file://` URIs.
- Object-storage files must be materialized by application-controlled infrastructure first.
- Remote Docling services are not enabled.
- PDF model downloads can occur during default initialization/use; production must point Docling at reviewed prefetched artifacts and block runtime egress.

## Normalized output

The adapter emits only application-owned models:

- ordered blocks with stable source references;
- normalized block kinds such as `title`, `text`, `table`, and `picture`;
- text/Markdown for blocks where available;
- table cells in row/column coordinates where available;
- one-based page provenance;
- top-left-origin bounding boxes;
- parser name/version, source format, schema version, page count, and warnings.

No Docling/Pydantic object crosses the adapter boundary or is persisted by the core.

## Known limitations

- OCR is intentionally disabled, so scanned/image-only PDFs need a separate OCR stage.
- Bounding boxes are best-effort and absent for items/formats without page geometry.
- Docling's labels may grow; unknown labels remain strings rather than breaking conversion.
- Layout fidelity is a parse concern only; this adapter does not reconstruct editable Office/PDF files.
- Current application processing is synchronous and intended only as a skeleton.

## Replacement plan

Docling can be replaced without changing application workflows:

1. Implement `FileParser` in a new adapter.
2. Map the engine output to the same normalized schema version.
3. Run the shared contract tests and golden sample corpus.
4. Compare block order, text, tables, provenance, accuracy, latency, and cost.
5. Select the adapter through dependency injection/configuration.
6. Reprocess only artifacts whose parser/version policy requires it.
7. Remove the Docling optional dependency and model image after data-retention and rollback windows close.

Core application code imports `FileParser`, never `DoclingFileParser`; stored artifacts record parser and version so migrations remain explicit.
