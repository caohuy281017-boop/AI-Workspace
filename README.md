# File-First AI Workspace

Commercial SaaS platform that routes uploaded business files into specialized, reviewable AI workflows. Each application is **fully independent** — debug, extend, or replace any app without touching the others.

## Apps (Ứng dụng)

| Folder | Sản phẩm | Trạng thái |
| :--- | :--- | :---: |
| [`app-accounting-batch/`](app-accounting-batch/README.md) | 🧾 Xử lý lô Hóa đơn & Kế toán | ✅ Core done |
| [`app-doc-translator/`](app-doc-translator/) | 📄 Dịch tài liệu | 🚧 Skeleton |
| [`app-meeting-notes/`](app-meeting-notes/) | 🎙️ Biên bản & Tóm tắt Cuộc họp | 🚧 Skeleton |

## Shared Core (Dùng chung)

| Folder | Nội dung |
| :--- | :--- |
| [`core-shared/`](core-shared/) | Domain models, port interfaces, shared adapters (Docling parser, LLM gateway, XLSX exporter) |

## Tài liệu

| File | Mô tả |
| :--- | :--- |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Ports & Adapters design |
| [`docs/PRODUCT.md`](docs/PRODUCT.md) | Product scope & milestones |
| [`docs/SUPERPOWERS_GITNEXUS_WORKFLOW.md`](docs/SUPERPOWERS_GITNEXUS_WORKFLOW.md) | TDD & Agent development discipline |
| [`docs/REPO_MAP.md`](docs/REPO_MAP.md) | Third-party dependency & license inventory |

## Quy tắc Đặt tên (Naming Convention)

| Loại | Quy tắc | Ví dụ |
| :--- | :--- | :--- |
| App folder | `app-{tên-app}` | `app-accounting-batch`, `app-doc-translator` |
| Shared package | `core-{tên}` | `core-shared` |
| Python module | `snake_case` | `invoice_schema.py`, `llm_extractor.py` |
| Python class | `PascalCase` | `InvoiceBatchWorkflow`, `XLSXExportAdapter` |
| Reference repos | `ref-{tên}` (trong `references/`) | `ref-taxhacker` |

## Luồng xử lý Milestone 1 (Hóa đơn)

```text
[PDF/Image] → core-shared DoclingParser
           → app-accounting-batch InvoiceBatchWorkflow
           → core-shared LLMAdapter (Gemini / OpenAI / Ollama)
           → [Human Review UI]
           → core-shared XLSXExporter → [invoices.xlsx]
```

## Chạy tests

```bash
# Test app-accounting-batch
cd app-accounting-batch
pytest tests/ -v
# → 34 passed ✅
```
