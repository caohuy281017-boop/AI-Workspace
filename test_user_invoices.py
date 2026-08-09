"""Test script to parse and extract data from user's sample invoices and save to JSON."""

import json
import sys
from pathlib import Path

sys.path.insert(0, "app-accounting-batch/src")
sys.path.insert(0, "core-shared/src")

from core_shared.domain import FileReference
from app_accounting_batch.pdf_parser import PDFTextParser
from app_accounting_batch.smart_extractor import SmartInvoiceExtractor
from app_accounting_batch.schema import INVOICE_SCHEMA_V1, SCHEMA_VERSION

def test_samples():
    sample_dir = Path(r"C:\Users\Mr.Chuong\Downloads\Hóa đơn mẫu")
    parser = PDFTextParser()
    extractor = SmartInvoiceExtractor()

    pdf_files = list(sample_dir.glob("*.pdf"))
    all_results = []

    for f in pdf_files:
        content = f.read_bytes()
        ref = FileReference(
            file_id=f"test-{f.stem}",
            workspace_id="default",
            name=f.name,
            media_type="application/pdf",
            size_bytes=len(content),
            storage_uri=str(f)
        )

        doc = parser.parse(ref, content)
        text_content = doc.blocks[0].text if doc.blocks else ""

        result = extractor.extract(
            doc,
            schema_name="invoice_schema",
            schema_version=SCHEMA_VERSION,
            schema=INVOICE_SCHEMA_V1
        )

        all_results.append({
            "filename": f.name,
            "text_length": len(text_content),
            "text_sample": text_content[:300],
            "extracted": result.values,
            "warnings": result.warnings
        })

    out_file = Path("extraction_results.json")
    out_file.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DONE: Extracted data from {len(pdf_files)} PDF files. Saved to {out_file.resolve()}")

if __name__ == "__main__":
    test_samples()
