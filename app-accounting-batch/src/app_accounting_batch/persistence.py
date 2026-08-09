"""SQLite Persistence Adapter for Accounting Batch.

Stores batches, uploaded invoice metadata, extracted fields, human review edits,
and approval status persistently in a local SQLite database.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


class SQLiteInvoiceRepository:
    """Manages persistent SQLite storage for invoice batches."""

    def __init__(self, db_path: str = "data/accounting_workspace.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._get_connection()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS batches (
                    batch_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS invoice_items (
                    file_id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    media_type TEXT,
                    size_bytes INTEGER,
                    storage_uri TEXT,
                    status TEXT NOT NULL,
                    extraction_json TEXT NOT NULL,
                    warnings_json TEXT,
                    errors_json TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE CASCADE
                );
            """)
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(invoice_items)").fetchall()
            }
            if "storage_uri" not in columns:
                conn.execute("ALTER TABLE invoice_items ADD COLUMN storage_uri TEXT")
            conn.commit()

    def save_batch(self, batch_id: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        with closing(self._get_connection()) as conn:
            conn.execute("INSERT OR REPLACE INTO batches (batch_id, created_at) VALUES (?, ?)", (batch_id, now))
            for item in items:
                conn.execute("""
                    INSERT OR REPLACE INTO invoice_items (
                        file_id, batch_id, file_name, media_type, size_bytes, storage_uri,
                        status, extraction_json, warnings_json, errors_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item["file_id"],
                    batch_id,
                    item["file_name"],
                    item.get("media_type", "application/pdf"),
                    item.get("size_bytes", 0),
                    item.get("storage_uri"),
                    item.get("status", "needs_review"),
                    json.dumps(item.get("extraction", {})),
                    json.dumps(item.get("warnings", [])),
                    json.dumps(item.get("errors", [])),
                    now
                ))
            conn.commit()
        return self.get_batch(batch_id)

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            batch_row = conn.execute("SELECT * FROM batches WHERE batch_id = ?", (batch_id,)).fetchone()
            if not batch_row:
                return None

            item_rows = conn.execute("SELECT * FROM invoice_items WHERE batch_id = ? ORDER BY file_name", (batch_id,)).fetchall()
            items = []
            for r in item_rows:
                items.append({
                    "file_id": r["file_id"],
                    "file_name": r["file_name"],
                    "media_type": r["media_type"],
                    "size_bytes": r["size_bytes"],
                    "storage_uri": r["storage_uri"],
                    "status": r["status"],
                    "extraction": json.loads(r["extraction_json"] or "{}"),
                    "warnings": json.loads(r["warnings_json"] or "[]"),
                    "errors": json.loads(r["errors_json"] or "[]"),
                })

            return {
                "batch_id": batch_row["batch_id"],
                "created_at": batch_row["created_at"],
                "items": items,
            }

    def list_all_batches(self) -> List[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            batch_rows = conn.execute("SELECT batch_id FROM batches ORDER BY created_at DESC").fetchall()
            result = []
            for row in batch_rows:
                b = self.get_batch(row["batch_id"])
                if b:
                    result.append(b)
            return result

    def get_item(self, file_id: str) -> Optional[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            row = conn.execute(
                "SELECT * FROM invoice_items WHERE file_id = ?",
                (file_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "file_id": row["file_id"],
                "batch_id": row["batch_id"],
                "file_name": row["file_name"],
                "media_type": row["media_type"],
                "size_bytes": row["size_bytes"],
                "storage_uri": row["storage_uri"],
                "status": row["status"],
                "extraction": json.loads(row["extraction_json"] or "{}"),
                "warnings": json.loads(row["warnings_json"] or "[]"),
                "errors": json.loads(row["errors_json"] or "[]"),
            }

    def update_item(self, batch_id: str, file_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            item_row = conn.execute("SELECT * FROM invoice_items WHERE file_id = ? AND batch_id = ?", (file_id, batch_id)).fetchone()
            if not item_row:
                return None

            current_extraction = json.loads(item_row["extraction_json"] or "{}")
            new_status = updates.get("status", item_row["status"])

            # Apply field updates to extraction dictionary
            for k, v in updates.items():
                if k != "status" and v is not None:
                    current_extraction[k] = v

            now = datetime.now().isoformat()
            conn.execute("""
                UPDATE invoice_items
                SET status = ?, extraction_json = ?, updated_at = ?
                WHERE file_id = ? AND batch_id = ?
            """, (new_status, json.dumps(current_extraction), now, file_id, batch_id))
            conn.commit()

            return {
                "file_id": file_id,
                "file_name": item_row["file_name"],
                "storage_uri": item_row["storage_uri"],
                "status": new_status,
                "extraction": current_extraction,
                "warnings": json.loads(item_row["warnings_json"] or "[]"),
                "errors": json.loads(item_row["errors_json"] or "[]"),
            }
