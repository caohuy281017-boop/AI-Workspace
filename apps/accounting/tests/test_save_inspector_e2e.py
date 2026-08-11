"""End-to-end regression tests for Inspector save and validation workflow."""

import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from accounting_app.api import create_app
from accounting_app.persistence import SQLiteInvoiceRepository


class TestSaveInspectorE2E(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.repo = SQLiteInvoiceRepository(str(root / "test.db"))
        self.app = create_app(self.repo, storage_dir=root / "storage")
        self.client = TestClient(self.app)

        # Upload an initial invoice
        file_payload = ("test_inv.pdf", b"%PDF-1.4 test invoice content", "application/pdf")
        res = self.client.post("/api/v1/accounting/batches", files=[("files", file_payload)])
        self.assertEqual(res.status_code, 201)
        batch_data = res.json()
        self.batch_id = batch_data["batch_id"]
        self.file_id = batch_data["items"][0]["file_id"]

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def test_save_inspector_updates_backend_fields_and_persists(self):
        """Verify editing supplier_name and total_amount via top-level payload persists in database."""
        update_payload = {
            "supplier_name": "CONG TY TNHH AI VIET NAM",
            "supplier_tax_id": "0102030405",
            "buyer_name": "CONG TY CO PHAN CONG NGHE",
            "buyer_tax_id": "0987654321",
            "invoice_number": "HD-99999",
            "invoice_date": "2026-08-11",
            "currency": "VND",
            "subtotal": 1000000.0,
            "tax_amount": 100000.0,
            "total_amount": 1100000.0,
            "items": [
                {
                    "description": "Dich vu AI Extraction",
                    "quantity": 1.0,
                    "unit_price": 1000000.0,
                    "amount": 1000000.0,
                }
            ],
            "status": "approved",
            "invoice_type": "dau_vao",
            "note": "Xac nhan tu form inspector",
        }

        patch_res = self.client.patch(
            f"/api/v1/accounting/batches/{self.batch_id}/items/{self.file_id}",
            json=update_payload,
        )
        self.assertEqual(patch_res.status_code, 200)

        # Verify persisted item from GET batch
        get_res = self.client.get(f"/api/v1/accounting/batches/{self.batch_id}")
        self.assertEqual(get_res.status_code, 200)
        item = get_res.json()["items"][0]

        self.assertEqual(item["status"], "approved")
        self.assertEqual(item["note"], "Xac nhan tu form inspector")
        self.assertEqual(item["extraction"]["supplier_name"], "CONG TY TNHH AI VIET NAM")
        self.assertEqual(item["extraction"]["supplier_tax_id"], "0102030405")
        self.assertEqual(item["extraction"]["buyer_name"], "CONG TY CO PHAN CONG NGHE")
        self.assertEqual(item["extraction"]["invoice_number"], "HD-99999")
        self.assertEqual(item["extraction"]["total_amount"], 1100000.0)
        self.assertEqual(len(item["extraction"]["items"]), 1)
        self.assertEqual(item["extraction"]["items"][0]["description"], "Dich vu AI Extraction")

    def test_save_inspector_ext_fallback_payload(self):
        """Verify fallback when client passes nested 'ext' dictionary."""
        nested_payload = {
            "ext": {
                "supplier": "NHA CUNG CAP MOI",
                "num": "INV-77777",
                "total": 550000.0,
                "sub": 500000.0,
                "vat": 50000.0,
            },
            "status": "approved",
            "invoice_type": "dau_ra",
            "note": "Legacy ext format",
        }

        patch_res = self.client.patch(
            f"/api/v1/accounting/batches/{self.batch_id}/items/{self.file_id}",
            json=nested_payload,
        )
        self.assertEqual(patch_res.status_code, 200)

        get_res = self.client.get(f"/api/v1/accounting/batches/{self.batch_id}")
        self.assertEqual(get_res.status_code, 200)
        item = get_res.json()["items"][0]

        self.assertEqual(item["status"], "approved")
        self.assertEqual(item["extraction"]["supplier_name"], "NHA CUNG CAP MOI")
        self.assertEqual(item["extraction"]["invoice_number"], "INV-77777")
        self.assertEqual(item["extraction"]["total_amount"], 550000.0)

    def test_null_policy_preservation(self):
        """Verify NULL policy: empty/missing values remain None and do not default to empty string or 0."""
        null_payload = {
            "supplier_name": "CONG TY TNHH ABC",
            "buyer_name": None,
            "invoice_template_number": None,
            "discount_amount": None,
            "fees": None,
            "total_amount": 500000.0,
            "status": "needs_review",
        }

        patch_res = self.client.patch(
            f"/api/v1/accounting/batches/{self.batch_id}/items/{self.file_id}",
            json=null_payload,
        )
        self.assertEqual(patch_res.status_code, 200)

        get_res = self.client.get(f"/api/v1/accounting/batches/{self.batch_id}")
        self.assertEqual(get_res.status_code, 200)
        item = get_res.json()["items"][0]

        self.assertEqual(item["extraction"]["supplier_name"], "CONG TY TNHH ABC")
        self.assertIsNone(item["extraction"].get("buyer_name"))
        self.assertIsNone(item["extraction"].get("invoice_template_number"))
        self.assertIsNone(item["extraction"].get("discount_amount"))
