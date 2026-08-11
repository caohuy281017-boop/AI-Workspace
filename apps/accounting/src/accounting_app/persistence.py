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
        self._run_migrations()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        # WAL mode for better concurrent read/write performance
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


    # ──────────────────────────────────────────────────────────────────────────
    # Migration Framework
    # ──────────────────────────────────────────────────────────────────────────

    def _run_migrations(self) -> None:
        """Apply all pending migrations in order. Idempotent — safe to run on every startup."""
        with closing(self._get_connection()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS db_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL,
                    description TEXT NOT NULL
                );
            """)
            conn.commit()
            applied = {
                row["version"]
                for row in conn.execute("SELECT version FROM db_migrations").fetchall()
            }

        for version, description, sql_statements in self._get_migrations():
            if version in applied:
                continue
            with closing(self._get_connection()) as conn:
                for stmt in sql_statements:
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO db_migrations (version, applied_at, description) VALUES (?, ?, ?)",
                    (version, datetime.utcnow().isoformat(), description),
                )
                conn.commit()

    @staticmethod
    def _get_migrations() -> list[tuple[str, str, list[str]]]:
        """Return ordered list of (version, description, [sql_statements]).

        Rules:
        - Versions must be zero-padded sortable strings ('001', '002', ...).
        - Each migration is idempotent: uses CREATE TABLE IF NOT EXISTS, etc.
        - Never DROP existing data without an explicit plan.
        """
        return [
            (
                "001",
                "Initial schema: batches, invoice_items, custom_fields",
                [
                    """
                    CREATE TABLE IF NOT EXISTS batches (
                        batch_id     TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL DEFAULT 'default-ws',
                        created_at   TEXT NOT NULL
                    );
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS invoice_items (
                        file_id                TEXT PRIMARY KEY,
                        batch_id               TEXT NOT NULL,
                        workspace_id           TEXT NOT NULL DEFAULT 'default-ws',
                        created_by_user_id     TEXT,
                        file_name              TEXT NOT NULL,
                        media_type             TEXT,
                        size_bytes             INTEGER,
                        storage_uri            TEXT,
                        invoice_type           TEXT DEFAULT 'dau_vao',
                        note                   TEXT DEFAULT '',
                        status                 TEXT NOT NULL,
                        extraction_json        TEXT NOT NULL,
                        warnings_json          TEXT,
                        errors_json            TEXT,
                        validation_status      TEXT DEFAULT 'pending',
                        validation_errors_json TEXT,
                        updated_at             TEXT NOT NULL,
                        FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE CASCADE
                    );
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS custom_fields (
                        code                TEXT PRIMARY KEY,
                        name                TEXT NOT NULL,
                        field_type          TEXT NOT NULL,
                        llm_prompt          TEXT NOT NULL DEFAULT '',
                        visible_in_list     INTEGER NOT NULL DEFAULT 0,
                        visible_in_analysis INTEGER NOT NULL DEFAULT 1,
                        is_required         INTEGER NOT NULL DEFAULT 0,
                        display_order       INTEGER NOT NULL,
                        created_at          TEXT NOT NULL,
                        updated_at          TEXT NOT NULL
                    );
                    """,
                ],
            ),
            (
                "002",
                "Add jobs table for async background processing with lease/idempotency",
                [
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id                TEXT PRIMARY KEY,
                        batch_id              TEXT NOT NULL,
                        file_id               TEXT NOT NULL,
                        workspace_id          TEXT NOT NULL DEFAULT 'default-ws',
                        created_by_user_id    TEXT,
                        status                TEXT NOT NULL DEFAULT 'queued',
                        attempt_count         INTEGER NOT NULL DEFAULT 0,
                        max_attempts          INTEGER NOT NULL DEFAULT 3,
                        next_attempt_at       TEXT,
                        worker_id             TEXT,
                        lease_expires_at      TEXT,
                        heartbeat_at          TEXT,
                        idempotency_key       TEXT UNIQUE,
                        last_error_code       TEXT,
                        last_error_message    TEXT,
                        routing_decision_json TEXT,
                        created_at            TEXT NOT NULL,
                        started_at            TEXT,
                        completed_at          TEXT,
                        FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE CASCADE
                    );
                    """,
                    "CREATE INDEX IF NOT EXISTS idx_jobs_status_next ON jobs(status, next_attempt_at);",
                    "CREATE INDEX IF NOT EXISTS idx_jobs_workspace ON jobs(workspace_id);",
                    "CREATE INDEX IF NOT EXISTS idx_jobs_file ON jobs(file_id);",
                ],
            ),
            (
                "003",
                "Backfill workspace/user indexes on invoice_items and batches",
                [
                    "CREATE INDEX IF NOT EXISTS idx_invoice_items_workspace ON invoice_items(workspace_id);",
                    "CREATE INDEX IF NOT EXISTS idx_batches_workspace ON batches(workspace_id);",
                ],
            ),
        ]

    def _ensure_legacy_columns(self, conn: sqlite3.Connection) -> None:
        """Backfill columns missing on databases created before migration 001.

        Safe to call multiple times — uses PRAGMA table_info to check existence.
        Only needed for pre-migration databases; new installs use the full schema.
        """
        legacy_additions: dict[str, dict[str, str]] = {
            "invoice_items": {
                "workspace_id": "TEXT NOT NULL DEFAULT 'default-ws'",
                "created_by_user_id": "TEXT",
                "storage_uri": "TEXT",
                "invoice_type": "TEXT DEFAULT 'dau_vao'",
                "note": "TEXT DEFAULT ''",
                "validation_status": "TEXT DEFAULT 'pending'",
                "validation_errors_json": "TEXT",
            },
            "batches": {
                "workspace_id": "TEXT NOT NULL DEFAULT 'default-ws'",
            },
        }
        for table, columns in legacy_additions.items():
            existing = {
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for col_name, col_def in columns.items():
                if col_name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")

    def list_custom_fields(self) -> List[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            rows = conn.execute(
                "SELECT * FROM custom_fields ORDER BY display_order, created_at"
            ).fetchall()
        return [self._custom_field_dict(row) for row in rows]

    def create_custom_field(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        with closing(self._get_connection()) as conn:
            next_order = conn.execute(
                "SELECT COALESCE(MAX(display_order), -1) + 1 FROM custom_fields"
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO custom_fields (
                    code, name, field_type, llm_prompt, visible_in_list,
                    visible_in_analysis, is_required, display_order,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data["code"], data["name"], data["field_type"],
                    data.get("llm_prompt", ""), int(data.get("visible_in_list", False)),
                    int(data.get("visible_in_analysis", True)),
                    int(data.get("is_required", False)), next_order, now, now,
                ),
            )
            conn.commit()
        return next(field for field in self.list_custom_fields() if field["code"] == data["code"])

    def update_custom_field(self, code: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = {
            "name", "field_type", "llm_prompt", "visible_in_list",
            "visible_in_analysis", "is_required",
        }
        updates = {key: value for key, value in data.items() if key in allowed}
        if not updates:
            return next((f for f in self.list_custom_fields() if f["code"] == code), None)
        bool_keys = {"visible_in_list", "visible_in_analysis", "is_required"}
        updates = {key: int(value) if key in bool_keys else value for key, value in updates.items()}
        updates["updated_at"] = datetime.now().isoformat()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        with closing(self._get_connection()) as conn:
            cursor = conn.execute(
                f"UPDATE custom_fields SET {assignments} WHERE code = ?",
                (*updates.values(), code),
            )
            conn.commit()
        if not cursor.rowcount:
            return None
        return next(field for field in self.list_custom_fields() if field["code"] == code)

    def delete_custom_field(self, code: str) -> bool:
        with closing(self._get_connection()) as conn:
            cursor = conn.execute("DELETE FROM custom_fields WHERE code = ?", (code,))
            conn.commit()
        return bool(cursor.rowcount)

    def reorder_custom_fields(self, codes: List[str]) -> List[Dict[str, Any]]:
        existing = {field["code"] for field in self.list_custom_fields()}
        if set(codes) != existing or len(codes) != len(existing):
            raise ValueError("Reorder list must contain every custom field exactly once.")
        with closing(self._get_connection()) as conn:
            for order, code in enumerate(codes):
                conn.execute(
                    "UPDATE custom_fields SET display_order = ?, updated_at = ? WHERE code = ?",
                    (order, datetime.now().isoformat(), code),
                )
            conn.commit()
        return self.list_custom_fields()

    @staticmethod
    def _custom_field_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "code": row["code"], "name": row["name"],
            "field_type": row["field_type"], "llm_prompt": row["llm_prompt"],
            "visible_in_list": bool(row["visible_in_list"]),
            "visible_in_analysis": bool(row["visible_in_analysis"]),
            "is_required": bool(row["is_required"]),
            "display_order": row["display_order"],
        }

    def list_custom_fields(self) -> List[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            rows = conn.execute(
                "SELECT * FROM custom_fields ORDER BY display_order, created_at"
            ).fetchall()
        return [self._custom_field_dict(row) for row in rows]

    def create_custom_field(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        with closing(self._get_connection()) as conn:
            next_order = conn.execute(
                "SELECT COALESCE(MAX(display_order), -1) + 1 FROM custom_fields"
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO custom_fields (
                    code, name, field_type, llm_prompt, visible_in_list,
                    visible_in_analysis, is_required, display_order,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data["code"], data["name"], data["field_type"],
                    data.get("llm_prompt", ""), int(data.get("visible_in_list", False)),
                    int(data.get("visible_in_analysis", True)),
                    int(data.get("is_required", False)), next_order, now, now,
                ),
            )
            conn.commit()
        return next(field for field in self.list_custom_fields() if field["code"] == data["code"])

    def update_custom_field(self, code: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = {
            "name", "field_type", "llm_prompt", "visible_in_list",
            "visible_in_analysis", "is_required",
        }
        updates = {key: value for key, value in data.items() if key in allowed}
        if not updates:
            return next((f for f in self.list_custom_fields() if f["code"] == code), None)
        bool_keys = {"visible_in_list", "visible_in_analysis", "is_required"}
        updates = {key: int(value) if key in bool_keys else value for key, value in updates.items()}
        updates["updated_at"] = datetime.now().isoformat()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        with closing(self._get_connection()) as conn:
            cursor = conn.execute(
                f"UPDATE custom_fields SET {assignments} WHERE code = ?",
                (*updates.values(), code),
            )
            conn.commit()
        if not cursor.rowcount:
            return None
        return next(field for field in self.list_custom_fields() if field["code"] == code)

    def delete_custom_field(self, code: str) -> bool:
        with closing(self._get_connection()) as conn:
            cursor = conn.execute("DELETE FROM custom_fields WHERE code = ?", (code,))
            conn.commit()
        return bool(cursor.rowcount)

    def reorder_custom_fields(self, codes: List[str]) -> List[Dict[str, Any]]:
        existing = {field["code"] for field in self.list_custom_fields()}
        if set(codes) != existing or len(codes) != len(existing):
            raise ValueError("Reorder list must contain every custom field exactly once.")
        with closing(self._get_connection()) as conn:
            for order, code in enumerate(codes):
                conn.execute(
                    "UPDATE custom_fields SET display_order = ?, updated_at = ? WHERE code = ?",
                    (order, datetime.now().isoformat(), code),
                )
            conn.commit()
        return self.list_custom_fields()

    @staticmethod
    def _custom_field_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "code": row["code"], "name": row["name"],
            "field_type": row["field_type"], "llm_prompt": row["llm_prompt"],
            "visible_in_list": bool(row["visible_in_list"]),
            "visible_in_analysis": bool(row["visible_in_analysis"]),
            "is_required": bool(row["is_required"]),
            "display_order": row["display_order"],
        }

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

    def get_batch(self, batch_id: str, search: str | None = None, invoice_type: str | None = None) -> Optional[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            batch_row = conn.execute("SELECT * FROM batches WHERE batch_id = ?", (batch_id,)).fetchone()
            if not batch_row:
                return None

            item_rows = conn.execute("SELECT * FROM invoice_items WHERE batch_id = ? ORDER BY file_name", (batch_id,)).fetchall()
            items = []
            for r in item_rows:
                extraction = json.loads(r["extraction_json"] or "{}")
                # --- Filter by invoice_type ---
                row_type = r["invoice_type"] if "invoice_type" in r.keys() else "dau_vao"
                if invoice_type and row_type != invoice_type:
                    continue
                # --- Filter by search query ---
                if search:
                    q = search.lower()
                    supplier = (extraction.get("supplier_name") or "").lower()
                    inv_num  = (extraction.get("invoice_number") or "").lower()
                    fname    = (r["file_name"] or "").lower()
                    tax_id   = (extraction.get("supplier_tax_id") or "").lower()
                    note     = (r["note"] if "note" in r.keys() else "") or ""
                    if not any(q in s for s in [supplier, inv_num, fname, tax_id, note.lower()]):
                        continue
                items.append({
                    "file_id": r["file_id"],
                    "file_name": r["file_name"],
                    "media_type": r["media_type"],
                    "size_bytes": r["size_bytes"],
                    "storage_uri": r["storage_uri"],
                    "status": r["status"],
                    "invoice_type": r["invoice_type"] if "invoice_type" in r.keys() else "dau_vao",
                    "note": r["note"] if "note" in r.keys() else "",
                    "extraction": extraction,
                    "warnings": json.loads(r["warnings_json"] or "[]"),
                    "errors": json.loads(r["errors_json"] or "[]"),
                })

            return {
                "batch_id": batch_row["batch_id"],
                "created_at": batch_row["created_at"],
                "items": items,
            }

    def list_all_batches(
        self,
        search: str | None = None,
        invoice_type: str | None = None,
    ) -> List[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            batch_rows = conn.execute("SELECT batch_id FROM batches ORDER BY created_at DESC").fetchall()
            result = []
            for row in batch_rows:
                b = self.get_batch(row["batch_id"], search=search, invoice_type=invoice_type)
                if b:
                    result.append(b)
            return result

    def get_all_approved_items(
        self,
        invoice_type: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Return all approved invoice items across every batch, optionally filtered by type."""
        with closing(self._get_connection()) as conn:
            rows = conn.execute(
                """SELECT ii.*, b.created_at as batch_created_at
                   FROM invoice_items ii
                   JOIN batches b ON b.batch_id = ii.batch_id
                   WHERE ii.status = 'approved'
                   ORDER BY b.created_at DESC, ii.file_name""",
            ).fetchall()
            items = []
            for r in rows:
                row_type = r["invoice_type"] if "invoice_type" in r.keys() else "dau_vao"
                if invoice_type and row_type != invoice_type:
                    continue
                extraction = json.loads(r["extraction_json"] or "{}")
                errors = json.loads(r["errors_json"] or "[]")
                if errors:
                    continue  # Skip errored items
                items.append({
                    "file_id": r["file_id"],
                    "batch_id": r["batch_id"],
                    "file_name": r["file_name"],
                    "status": r["status"],
                    "invoice_type": row_type,
                    "note": r["note"] if "note" in r.keys() else "",
                    "extraction": extraction,
                })
            return items

    def delete_item(self, batch_id: str, file_id: str, storage_dir: "Path | None" = None) -> bool:
        """Delete a single invoice item and its stored file."""
        from pathlib import Path as _Path
        item = self.get_item(file_id)
        if not item or item.get("batch_id") != batch_id:
            return False

        # Remove physical file from storage
        if storage_dir and item.get("storage_uri"):
            file_path = _Path(item["storage_uri"]).resolve()
            try:
                if file_path.is_relative_to(_Path(storage_dir).resolve()) and file_path.is_file():
                    file_path.unlink()
            except Exception:
                pass  # Don't block deletion if file removal fails

        with closing(self._get_connection()) as conn:
            cursor = conn.execute(
                "DELETE FROM invoice_items WHERE file_id = ? AND batch_id = ?",
                (file_id, batch_id),
            )
            conn.commit()
        return bool(cursor.rowcount)

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

            # invoice_type and note are first-class columns; don't embed in extraction JSON
            FIRST_CLASS = {"status", "invoice_type", "note"}
            new_invoice_type = updates.get("invoice_type", item_row["invoice_type"] if "invoice_type" in item_row.keys() else "dau_vao")
            new_note = updates.get("note", item_row["note"] if "note" in item_row.keys() else "")

            # Apply field updates to extraction dictionary (skip first-class fields)
            for k, v in updates.items():
                if k not in FIRST_CLASS and v is not None:
                    current_extraction[k] = v

            now = datetime.now().isoformat()
            conn.execute("""
                UPDATE invoice_items
                SET status = ?, extraction_json = ?, invoice_type = ?, note = ?, updated_at = ?
                WHERE file_id = ? AND batch_id = ?
            """, (new_status, json.dumps(current_extraction), new_invoice_type, new_note, now, file_id, batch_id))
            conn.commit()

            return {
                "file_id": file_id,
                "file_name": item_row["file_name"],
                "storage_uri": item_row["storage_uri"],
                "status": new_status,
                "invoice_type": new_invoice_type,
                "note": new_note,
                "extraction": current_extraction,
                "warnings": json.loads(item_row["warnings_json"] or "[]"),
                "errors": json.loads(item_row["errors_json"] or "[]"),
            }

