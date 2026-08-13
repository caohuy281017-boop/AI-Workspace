# Repository and License Map

This file is an engineering inventory, not legal advice. A permissive repository code license does **not** automatically clear bundled models, weights, datasets, optional components, or dependencies for commercial use.

## Status vocabulary

- **Candidate:** relevant but no complete license review has been recorded.
- **Research only:** may be studied; no source code, package, model, or container may enter production.
- **Approved:** code, models, important dependencies, distribution approach, and obligations were reviewed for a pinned version.
- **Rejected:** incompatible with the intended commercial use or risk tolerance.

## Inventory

| repo | purpose | URL | code license | model license | commercial status | integration strategy | status | notes |
|---|---|---|---|---|---|---|---|---|
| Docling | Universal parsing and document structure extraction | https://github.com/docling-project/docling | MIT; reviewed for package pin 2.115.0 | PDF bundle: CDLA-Permissive-2.0 / Apache-2.0 metadata; Heron: Apache-2.0; exact artifact revision review pending | Conditional engineering approval; legal/SBOM review pending | Optional in-process `FileParser` adapter now; isolated worker remains available | Adapter implemented | Narrow scope disables OCR/enrichments/remote services. See `docs/DOCLING_EVALUATION.md`. Not yet cleared for commercial release. |
| PaddleOCR | OCR, layout analysis, and document parsing | https://github.com/PaddlePaddle/PaddleOCR | Apache-2.0 (upstream states; pin/version review pending) | Unverified per selected PP-OCR/PP-Structure/PaddleOCR-VL model | Not approved | Future `OCRProvider` adapter, potentially isolated worker/container | Candidate | Apache code status does not by itself clear model weights or Paddle dependencies. |
| TaxHacker | Invoice/accounting workflow reference | https://github.com/vas3k/TaxHacker | MIT (upstream states; pin/version review pending) | Depends on configured providers; unverified | Research/reference only | Study UX and workflow concepts; implement our own domain workflow and schemas | Research only | Do not copy implementation before full dependency and asset review. |
| bankstatementparser | Bank statement parsing workflow/reference | https://github.com/sebastienrousseau/bankstatementparser | Apache-2.0 (upstream states; pin/version review pending) | Provider/model dependent; unverified | Not approved | Future adapter or workflow reference after review; not part of invoice milestone | Candidate | Review optional PDF/LLM paths, packages, and transitive dependencies. |
| Meetily | Meeting transcription, diarization, and summarization reference | https://github.com/Zackriya-Solutions/meetily | MIT for community repository (upstream states; pin/version review pending) | Whisper/Parakeet and other selected models unverified | Research/reference only | Study workflow; build our own meeting use case behind speech/LLM adapters later | Research only | Upstream also advertises a separately licensed Pro product; distinguish assets/code carefully. |
| PDFMathTranslate | Layout-preserving PDF translation research | https://github.com/PDFMathTranslate/PDFMathTranslate | Unverified | Unverified; provider/model dependent | Not approved | Research only until complete code/model/dependency review | Research only | Translation output and font/tool dependencies may add separate obligations. Do not integrate yet. |
| Stirling PDF | Broad PDF manipulation platform | https://github.com/Stirling-Tools/Stirling-PDF | Open-core/custom terms; exact current LICENSE review required | Not applicable or feature-dependent; unverified | Not approved | No integration; evaluate API/process boundary only after legal review | Research only | Current upstream describes the project as open-core. Treat as high-review-risk, not as a permissive dependency. |
| Firecrawl anydoc | Local conversion of Word, Office and native-text PDF files to Markdown | https://github.com/firecrawl/anydoc | MIT; package pin 0.1.8 reviewed | N/A (pure parser, no bundled ML model) | Conditional engineering approval | In-process adapter behind a size-limited upload endpoint; the application does not persist source documents and framework-managed temporary uploads are released after the request | Adapter implemented | PyPI wheel includes a native Rust library. Preserve MIT notice, pin 0.1.8, review transitive/native SBOM before commercial release. Image-only/scanned PDF is not OCRed. |
| openpyxl | Excel (.xlsx) file generation | https://pypi.org/project/openpyxl/ | MIT | N/A (no model) | Preliminary acceptable | Used only in `adapters/xlsx_exporter.py` via `ExportProvider` port | Adapter implemented | Pure Python OOXML writer. MIT licence confirmed. No native binaries. Pin version in pyproject.toml before release. |
| google-generativeai | Google Gemini LLM API client | https://pypi.org/project/google-generativeai/ | Apache-2.0 | N/A (hosted API, model not bundled) | Conditional engineering approval | Used only in `adapters/llm_adapter.py` via `LLMProvider` port | Adapter implemented | API key required; data is sent to Google servers — confirm tenant data and retention policy before production. |
| openai | OpenAI & OpenAI-compatible HTTP client | https://pypi.org/project/openai/ | MIT | N/A (hosted API or local, model not bundled) | Conditional engineering approval | Used only in `adapters/llm_adapter.py` via `LLMProvider` port | Adapter implemented | Supports both OpenAI cloud and local Ollama/LM Studio endpoints. Confirm API key and data-residency policy for cloud use. |

## Review record required before approval

For each pinned candidate, add or link a dated review containing:

- Repository URL, commit/tag, package/container version, and review date.
- Exact code license and copyright/NOTICE obligations.
- Model/weight names, versions, download sources, licenses, and use restrictions.
- Important direct dependencies and their licenses; flag GPL/AGPL/LGPL/SSPL/custom terms.
- Fonts, datasets, sample assets, codecs, native binaries, and optional components shipped or invoked.
- Intended integration/distribution mode and whether files/data leave our infrastructure.
- Required attributions, notices, source offers, or user-facing terms.
- Final decision, approver, constraints, and re-review trigger.

## Current decision

Docling is the first optional adapter and is pinned separately from the dependency-free core. It has conditional engineering approval only; production/commercial release remains blocked on a resolved dependency SBOM, exact model artifact pin/checksums, notices, and legal sign-off. No other listed repository is integrated.
