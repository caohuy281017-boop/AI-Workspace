"""Comprehensive test suite for Background Job Queue and Worker (P0 gap remediation)."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient

from accounting_app.api import create_app
from accounting_app.job_worker import JobWorker
from accounting_app.pdf_parser import PDFTextParser
from accounting_app.persistence import SQLiteInvoiceRepository
from accounting_app.smart_extractor import SmartInvoiceExtractor


class TestJobQueueAndWorker(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_jobs.db"
        self.storage_dir = Path(self.tmp_dir.name) / "storage"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.repo = SQLiteInvoiceRepository(str(self.db_path))
        self.parser = PDFTextParser()
        self.extractor = SmartInvoiceExtractor()
        self.worker = JobWorker(
            repository=self.repo,
            parser=self.parser,
            extractor=self.extractor,
            storage_dir=self.storage_dir,
            worker_id="test-worker-1",
            lease_seconds=2,
        )

        self.app = create_app(
            repo=self.repo,
            storage_dir=self.storage_dir,
            parser=self.parser,
            extractor=self.extractor,
        )
        self.client = TestClient(self.app)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_enqueue_and_claim_job(self):
        self.repo.save_batch("b-1", items=[{"file_id": "f-1", "file_name": "f1.pdf"}], workspace_id="ws-corp")
        job = self.repo.enqueue_job(
            batch_id="b-1",
            file_id="f-1",
            workspace_id="ws-corp",
            user_id="user-123",
        )
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["attempt_count"], 0)

        # Claim job
        claimed = self.repo.claim_next_job("worker-alpha", lease_seconds=10)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["job_id"], job["job_id"])
        self.assertEqual(claimed["status"], "running")
        self.assertEqual(claimed["worker_id"], "worker-alpha")
        self.assertEqual(claimed["attempt_count"], 1)

        # Attempting to claim again while lease active should return None
        claimed_again = self.repo.claim_next_job("worker-beta", lease_seconds=10)
        self.assertIsNone(claimed_again)

    def test_heartbeat_extends_lease(self):
        self.repo.save_batch("b-1", items=[{"file_id": "f-1", "file_name": "f1.pdf"}])
        job = self.repo.enqueue_job("b-1", "f-1")
        claimed = self.repo.claim_next_job("worker-alpha", lease_seconds=5)
        old_lease = claimed["lease_expires_at"]

        time.sleep(0.05)
        ok = self.repo.heartbeat_job(job["job_id"], "worker-alpha", extend_seconds=15)
        self.assertTrue(ok)

        refreshed = self.repo.get_job(job["job_id"])
        self.assertGreater(refreshed["lease_expires_at"], old_lease)

    def test_complete_job(self):
        self.repo.save_batch("b-1", items=[{"file_id": "f-1", "file_name": "f1.pdf"}])
        job = self.repo.enqueue_job("b-1", "f-1")
        self.repo.claim_next_job("worker-alpha")
        ok = self.repo.complete_job(job["job_id"], routing_decision={"mode": "text_only", "score": 0.95})
        self.assertTrue(ok)

        completed = self.repo.get_job(job["job_id"])
        self.assertEqual(completed["status"], "completed")
        self.assertIsNotNone(completed["completed_at"])
        self.assertEqual(completed["routing_decision"]["mode"], "text_only")

    def test_fail_job_retries_and_then_fails(self):
        self.repo.save_batch("b-1", items=[{"file_id": "f-1", "file_name": "f1.pdf"}])
        job = self.repo.enqueue_job("b-1", "f-1", max_attempts=2)

        # Attempt 1 -> fails -> retrying
        self.repo.claim_next_job("worker-alpha")
        s1 = self.repo.fail_job(job["job_id"], "ERR_TEMP", "Network timeout", backoff_seconds=0)
        self.assertEqual(s1, "retrying")

        # Attempt 2 -> fails -> failed
        time.sleep(0.01)
        self.repo.claim_next_job("worker-alpha")
        s2 = self.repo.fail_job(job["job_id"], "ERR_FATAL", "Permanent failure")
        self.assertEqual(s2, "failed")

        final_job = self.repo.get_job(job["job_id"])
        self.assertEqual(final_job["status"], "failed")
        self.assertEqual(final_job["last_error_code"], "ERR_FATAL")

    def test_recover_stale_jobs(self):
        self.repo.save_batch("b-1", items=[{"file_id": "f-1", "file_name": "f1.pdf"}])
        job = self.repo.enqueue_job("b-1", "f-1")
        # Claim with very short lease (0 seconds)
        self.repo.claim_next_job("worker-crashed", lease_seconds=-1)

        recovered_count = self.repo.recover_stale_jobs()
        self.assertEqual(recovered_count, 1)

        recovered_job = self.repo.get_job(job["job_id"])
        self.assertEqual(recovered_job["status"], "queued")
        self.assertIsNone(recovered_job["worker_id"])

    def test_worker_processes_job_end_to_end(self):
        # Create a mock invoice PDF file
        file_path = self.storage_dir / "inv_sample.pdf"
        file_path.write_bytes(b"%PDF-1.4 dummy invoice text content")

        # Save batch shell
        self.repo.save_batch(
            batch_id="b-async-1",
            items=[{
                "file_id": "f-sample",
                "file_name": "inv_sample.pdf",
                "media_type": "application/pdf",
                "size_bytes": len(b"%PDF-1.4 dummy invoice text content"),
                "storage_uri": str(file_path),
                "status": "queued",
                "invoice_type": "dau_vao",
                "note": "",
                "extraction": {},
                "warnings": [],
                "errors": [],
                "validation_status": "pending",
                "validation_errors": [],
            }],
            workspace_id="ws-test",
        )

        # Enqueue job
        job = self.repo.enqueue_job("b-async-1", "f-sample", workspace_id="ws-test")

        # Run worker cycle
        processed = self.worker.run_once()
        self.assertTrue(processed)

        # Check job is completed
        completed_job = self.repo.get_job(job["job_id"])
        self.assertEqual(completed_job["status"], "completed")

        # Check item was updated in repository
        item = self.repo.get_item("f-sample")
        self.assertEqual(item["status"], "needs_review")
        self.assertIn("validation_status", item)

    def test_async_batch_api_endpoints(self):
        # Upload async batch
        res = self.client.post(
            "/api/v1/accounting/batches/async",
            files=[
                ("files", ("inv1.pdf", b"%PDF-1.4 invoice 1", "application/pdf")),
                ("files", ("inv2.pdf", b"%PDF-1.4 invoice 2", "application/pdf")),
            ],
            headers={"X-Workspace-ID": "ws-custom", "X-User-ID": "u-456"},
        )
        self.assertEqual(res.status_code, 202)
        data = res.json()
        self.assertEqual(data["status"], "queued")
        self.assertEqual(data["total_files"], 2)
        batch_id = data["batch_id"]
        self.assertEqual(len(data["jobs"]), 2)
        job_id = data["jobs"][0]["job_id"]

        # Poll individual job
        j_res = self.client.get(f"/api/v1/accounting/jobs/{job_id}")
        self.assertEqual(j_res.status_code, 200)
        self.assertEqual(j_res.json()["job_id"], job_id)
        self.assertEqual(j_res.json()["status"], "queued")

        # Poll batch jobs
        b_res = self.client.get(f"/api/v1/accounting/batches/{batch_id}/jobs")
        self.assertEqual(b_res.status_code, 200)
        b_data = b_res.json()
        self.assertEqual(b_data["total_jobs"], 2)
        self.assertEqual(b_data["queued_count"], 2)

    def test_worker_start_stop_thread_lifecycle(self):
        # Create a file on disk and in repo
        file_path = self.storage_dir / "lifecycle_sample.pdf"
        file_path.write_bytes(b"%PDF-1.4 sample invoice text")

        self.repo.save_batch(
            "b-lifecycle",
            items=[{
                "file_id": "f-lifecycle",
                "file_name": "lifecycle_sample.pdf",
                "media_type": "application/pdf",
                "storage_uri": str(file_path),
                "status": "queued",
                "extraction": {},
                "warnings": [],
                "errors": [],
                "validation_status": "ok",
                "validation_errors": [],
            }],
            workspace_id="ws-life",
        )

        # Enqueue job
        job = self.repo.enqueue_job("b-lifecycle", "f-lifecycle", workspace_id="ws-life")

        # Start worker thread
        self.worker.start()
        self.assertIsNotNone(self.worker._thread)
        self.assertTrue(self.worker._thread.is_alive())

        # Wait for worker background thread to claim and finish the job
        completed = False
        for _ in range(30):
            time.sleep(0.1)
            j = self.repo.get_job(job["job_id"])
            if j and j.get("status") == "completed":
                completed = True
                break

        self.assertTrue(completed, "Worker thread should process queued job asynchronously")

        # Stop worker thread
        self.worker.stop(timeout=2.0)
        self.assertFalse(self.worker._thread.is_alive(), "Worker thread should terminate cleanly")

