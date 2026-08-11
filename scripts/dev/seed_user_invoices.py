"""Seed persistent SQLite database with user sample invoices."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "accounting" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "platform-core" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "platform-adapters" / "src"))

from platform_core.domain import FileReference
from accounting_app.pdf_parser import PDFTextParser
from accounting_app.smart_extractor import SmartInvoiceExtractor
from accounting_app.persistence import SQLiteInvoiceRepository
from accounting_app.schema import INVOICE_SCHEMA_V1, SCHEMA_VERSION

def seed():
    sample_dir = Path(r"C:\Users\Mr.Chuong\Downloads\Hóa đơn mẫu")
    parser = PDFTextParser()
    extractor = SmartInvoiceExtractor()
    repo = SQLiteInvoiceRepository()

    pdf_files = list(sample_dir.glob("*.pdf"))
    items_data = []

    for idx, f in enumerate(pdf_files, start=1):
        content = f.read_bytes()
        file_id = f"inv-{idx:03d}"
        ref = FileReference(
            file_id=file_id,
            workspace_id="default-ws",
            name=f.name,
            media_type="application/pdf",
            size_bytes=len(content),
            storage_uri=str(f)
        )

        doc = parser.parse(ref, content)
        ext_result = extractor.extract(
            doc,
            schema_name="invoice_schema",
            schema_version=SCHEMA_VERSION,
            schema=INVOICE_SCHEMA_V1
        )

        items_data.append({
            "file_id": file_id,
            "file_name": f.name,
            "media_type": "application/pdf",
            "size_bytes": len(content),
            "status": "needs_review",
            "extraction": ext_result.values,
            "warnings": list(ext_result.warnings),
            "errors": []
        })

    batch_id = "batch-sample-001"
    repo.save_batch(batch_id, items_data)
    print(f"Successfully seeded SQLite database with batch '{batch_id}' ({len(items_data)} real invoices)!")

if __name__ == "__main__":
    seed()
