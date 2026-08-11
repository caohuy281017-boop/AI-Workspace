# Backend skeleton

The provider-neutral core remains dependency-free. Docling is available as the first optional parser adapter; this is not yet an API server.

## Layout

```text
src/file_first_ai/
  domain/models.py
  ports/
    document_classifier.py
    export_provider.py
    extraction_provider.py
    file_parser.py
    llm_provider.py
    ocr_provider.py
  application/invoice_batch.py
  adapters/
    docling_parser.py
```

The six ports use `typing.Protocol`, so adapters do not need to inherit a framework base class. Future adapters belong in `adapters/` and must translate provider objects into the domain models.

## Docling adapter

```powershell
python -m pip install -e ".[docling]"
```

`DoclingFileParser` supports PDF, DOCX, PPTX, and XLSX from worker-local files. PDF OCR/enrichments and remote services are disabled by default. See `docs/DOCLING_EVALUATION.md` for the licensing scope and model controls.

## Run tests

From `backend/`:

```powershell
python -m unittest discover -s tests -v
```

Unit tests use in-memory fakes and need no third-party package. The opt-in sample integration test is documented in `tests/samples/README.md`.
