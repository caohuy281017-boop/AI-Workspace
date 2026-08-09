# app-accounting-batch

**Sản phẩm 1 / Product 1** — Xử lý lô Hóa đơn & Kế toán

## Mô tả

App nhận vào một tập hợp file hóa đơn (PDF, ảnh chụp), tự động trích xuất dữ liệu bằng AI, cho người dùng kiểm duyệt và xuất ra file Excel (`.xlsx`) chuẩn kế toán.

**Luồng xử lý:**
```
[PDF/Image] → DoclingParser → InvoiceBatchWorkflow → LLMExtractionAdapter → [Human Review] → XLSXExportAdapter → [invoices.xlsx]
```

## Phụ thuộc
- `core-shared` — Domain models, ports, shared adapters (Docling, LLM, XLSX)

## Chạy tests

```bash
cd app-accounting-batch
pytest tests/ -v
```

## Cấu trúc
```
src/app_accounting_batch/
├── models.py      # InvoiceRecord, InvoiceLineItem (domain models của app này)
├── schema.py      # Invoice JSON Schema v1.0 & Prompt template
├── extractor.py   # LLMExtractionAdapter (invoice-specific logic)
└── workflow.py    # InvoiceBatchWorkflow (orchestrator)
```

## Input / Output
- **Input**: List[FileReference] — Danh sách file hóa đơn đã upload
- **Output**: ExportArtifact — File `.xlsx` 2-sheet (Invoices + Line Items)

## Trạng thái
- [x] Domain models (InvoiceRecord, InvoiceLineItem)
- [x] Invoice JSON Schema v1.0
- [x] LLM Extraction Adapter (Gemini / OpenAI / Ollama)
- [x] XLSX Export Adapter
- [x] InvoiceBatchWorkflow
- [ ] Web API (FastAPI) — Cần triển khai
- [ ] Frontend Review UI — Cần triển khai
