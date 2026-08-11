"""Tests for app-accounting-batch FastAPI Web API.

Verifies:
  - Batch upload endpoint (POST /api/v1/accounting/batches)
  - Batch detail endpoint (GET /api/v1/accounting/batches/{batch_id})
  - Inline edit / PATCH invoice item (PATCH /api/v1/accounting/batches/{batch_id}/items/{file_id})
  - Export XLSX endpoint (POST /api/v1/accounting/batches/{batch_id}/export)

Run with:
    pytest tests/test_api.py -v
"""

import io
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from accounting_app.api import create_app
from accounting_app.persistence import SQLiteInvoiceRepository


class TestAccountingBatchAPI(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.repo = SQLiteInvoiceRepository(str(root / "test.db"))
        self.app = create_app(self.repo, storage_dir=root / "storage")
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def test_batch_upload_creates_batch(self):
        file1 = ("invoice1.pdf", b"fake pdf content 1", "application/pdf")
        file2 = ("invoice2.pdf", b"fake pdf content 2", "application/pdf")
        
        response = self.client.post(
            "/api/v1/accounting/batches",
            files=[("files", file1), ("files", file2)]
        )
        
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("batch_id", data)
        self.assertEqual(len(data["items"]), 2)

    def test_get_batch_returns_details_and_stats(self):
        # First upload a file to create a batch
        file1 = ("inv.pdf", b"pdf content", "application/pdf")
        res = self.client.post("/api/v1/accounting/batches", files=[("files", file1)])
        batch_id = res.json()["batch_id"]

        # Fetch details
        get_res = self.client.get(f"/api/v1/accounting/batches/{batch_id}")
        self.assertEqual(get_res.status_code, 200)
        data = get_res.json()
        self.assertIn("stats", data)
        self.assertEqual(data["stats"]["total_files"], 1)

    def test_patch_item_updates_extracted_fields(self):
        file1 = ("inv.pdf", b"pdf content", "application/pdf")
        res = self.client.post("/api/v1/accounting/batches", files=[("files", file1)])
        batch_id = res.json()["batch_id"]
        file_id = res.json()["items"][0]["file_id"]

        # Update supplier_name and total_amount via PATCH
        patch_payload = {
            "supplier_name": "Công ty Cổ phần Mới Sửa",
            "total_amount": 999000.0,
            "status": "approved"
        }
        patch_res = self.client.patch(
            f"/api/v1/accounting/batches/{batch_id}/items/{file_id}",
            json=patch_payload
        )
        self.assertEqual(patch_res.status_code, 200)
        updated = patch_res.json()
        self.assertEqual(updated["extraction"]["supplier_name"], "Công ty Cổ phần Mới Sửa")
        self.assertEqual(updated["extraction"]["total_amount"], 999000.0)
        self.assertEqual(updated["status"], "approved")

    def test_export_batch_returns_xlsx_file(self):
        file1 = ("inv.pdf", b"pdf content", "application/pdf")
        res = self.client.post("/api/v1/accounting/batches", files=[("files", file1)])
        batch_id = res.json()["batch_id"]
        file_id = res.json()["items"][0]["file_id"]

        approve_res = self.client.patch(
            f"/api/v1/accounting/batches/{batch_id}/items/{file_id}",
            json={"status": "approved"},
        )
        self.assertEqual(approve_res.status_code, 200)

        export_res = self.client.post(f"/api/v1/accounting/batches/{batch_id}/export")
        self.assertEqual(export_res.status_code, 200)
        self.assertEqual(
            export_res.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.assertGreater(len(export_res.content), 0)

    def test_export_all_batches_multi_batch(self):
        # Create Batch 1
        res1 = self.client.post("/api/v1/accounting/batches", files=[("files", ("inv1.pdf", b"pdf 1", "application/pdf"))])
        b1_id = res1.json()["batch_id"]
        f1_id = res1.json()["items"][0]["file_id"]
        self.client.patch(f"/api/v1/accounting/batches/{b1_id}/items/{f1_id}", json={"status": "approved", "supplier_name": "Supplier 1"})

        # Create Batch 2
        res2 = self.client.post("/api/v1/accounting/batches", files=[("files", ("inv2.pdf", b"pdf 2", "application/pdf"))])
        b2_id = res2.json()["batch_id"]
        f2_id = res2.json()["items"][0]["file_id"]
        self.client.patch(f"/api/v1/accounting/batches/{b2_id}/items/{f2_id}", json={"status": "approved", "supplier_name": "Supplier 2"})

        # Export ALL
        res_all = self.client.get("/api/v1/accounting/export-all.xlsx")
        self.assertEqual(res_all.status_code, 200)

        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(res_all.content))
        ws = wb["Invoices"]
        rows = list(ws.iter_rows(values_only=True))
        # 1 header + 2 approved records from 2 distinct batches
        self.assertEqual(len(rows), 3)

    def test_delete_invoice_item(self):
        res = self.client.post("/api/v1/accounting/batches", files=[("files", ("to_delete.pdf", b"pdf", "application/pdf"))])
        batch_id = res.json()["batch_id"]
        file_id = res.json()["items"][0]["file_id"]

        del_res = self.client.delete(f"/api/v1/accounting/batches/{batch_id}/items/{file_id}")
        self.assertEqual(del_res.status_code, 204)

        # Batch should now have 0 items
        get_res = self.client.get(f"/api/v1/accounting/batches/{batch_id}")
        self.assertEqual(len(get_res.json()["items"]), 0)

    def test_patch_item_revalidates_and_updates_validation_status(self):
        # Create an item
        res = self.client.post("/api/v1/accounting/batches", files=[("files", ("test.pdf", b"pdf", "application/pdf"))])
        batch_id = res.json()["batch_id"]
        file_id = res.json()["items"][0]["file_id"]

        # 1. PATCH with arithmetic mismatch: subtotal 100 + tax 10 != total 200
        patch_res = self.client.patch(
            f"/api/v1/accounting/batches/{batch_id}/items/{file_id}",
            json={
                "subtotal": 100.0,
                "tax_amount": 10.0,
                "total_amount": 200.0,
                "currency": "VND",
                "supplier_name": "Cong ty ABC",
                "supplier_tax_id": "0123456789",
            },
        )
        self.assertEqual(patch_res.status_code, 200)
        data = patch_res.json()
        self.assertEqual(data["validation_status"], "error")
        error_codes = [e["code"] for e in data["validation_errors"]]
        self.assertIn("TOTAL_MISMATCH", error_codes)

        # 2. Fix the numbers: subtotal 100 + tax 10 == total 110
        fix_res = self.client.patch(
            f"/api/v1/accounting/batches/{batch_id}/items/{file_id}",
            json={"total_amount": 110.0},
        )
        self.assertEqual(fix_res.status_code, 200)
        fixed_data = fix_res.json()
        self.assertEqual(fixed_data["validation_status"], "ok")

    def test_patch_item_creates_audit_log_and_can_be_retrieved(self):
        res = self.client.post("/api/v1/accounting/batches", files=[("files", ("test.pdf", b"pdf", "application/pdf"))])
        batch_id = res.json()["batch_id"]
        file_id = res.json()["items"][0]["file_id"]

        # Update with override reason
        self.client.patch(
            f"/api/v1/accounting/batches/{batch_id}/items/{file_id}",
            json={
                "supplier_name": "Supplier Changed",
                "status": "approved",
                "override_reason": "Khach hang xac nhan dung so hoa don",
            },
        )

        # Retrieve audit logs
        log_res = self.client.get(f"/api/v1/accounting/batches/{batch_id}/items/{file_id}/audit-logs")
        self.assertEqual(log_res.status_code, 200)
        logs = log_res.json()["audit_logs"]
        self.assertGreaterEqual(len(logs), 1)
        latest_log = logs[0]
        self.assertEqual(latest_log["entity_id"], file_id)
        self.assertEqual(latest_log["reason"], "Khach hang xac nhan dung so hoa don")
        self.assertIn("extraction.supplier_name", latest_log["changes"])


if __name__ == "__main__":
    unittest.main()

