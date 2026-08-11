"""Test script to parse and extract data from user's sample invoices and save to JSON."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "accounting" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "platform-core" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "platform-adapters" / "src"))

from platform_core.domain import FileReference
from accounting_app.pdf_parser import PDFTextParser
from accounting_app.smart_extractor import SmartInvoiceExtractor
from accounting_app.schema import INVOICE_SCHEMA_V1, SCHEMA_VERSION

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

    out_file = Path(__file__).with_name("extraction_results.json")
    out_file.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DONE: Extracted data from {len(pdf_files)} PDF files. Saved to {out_file.resolve()}")

if __name__ == "__main__":
    test_samples()
