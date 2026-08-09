# Docling sample files

Fixtures are generated locally from original strings; no upstream Docling test assets are copied.

```powershell
python tests/samples/create_samples.py
python -m unittest tests.integration.test_docling_sample_files -v
```

Generated binary files are intentionally not committed. PDF parsing may download Docling model artifacts on first use; production/CI must use reviewed, pinned, pre-fetched artifacts.
