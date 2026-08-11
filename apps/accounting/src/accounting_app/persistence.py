"""SQLite Persistence Adapter for Accounting Batch.

Stores batches, uploaded invoice metadata, extracted fields, human review edits,
and approval status persistently in a local SQLite database.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from accounting_app.validator import validate_invoice


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
            (
                "004",
                "Add audit_logs table for tracking manual review changes and overrides",
                [
                    """
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        log_id              TEXT PRIMARY KEY,
                        workspace_id        TEXT NOT NULL DEFAULT 'default-ws',
                        entity_type         TEXT NOT NULL,
                        entity_id           TEXT NOT NULL,
                        action              TEXT NOT NULL,
                        user_id             TEXT,
                        changes_json        TEXT NOT NULL,
                        reason              TEXT,
                        created_at          TEXT NOT NULL
                    );
                    """,
                    "CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id);",
                    "CREATE INDEX IF NOT EXISTS idx_audit_workspace ON audit_logs(workspace_id);",
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

    def save_batch(self, batch_id: str, items: List[Dict[str, Any]], workspace_id: str = "default-ws") -> Dict[str, Any]:
        now = datetime.now().isoformat()
        with closing(self._get_connection()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO batches (batch_id, workspace_id, created_at) VALUES (?, ?, ?)",
                (batch_id, workspace_id, now),
            )
            for item in items:
                conn.execute("""
                    INSERT OR REPLACE INTO invoice_items (
                        file_id, batch_id, workspace_id, file_name, media_type, size_bytes,
                        storage_uri, status, extraction_json, warnings_json, errors_json,
                        validation_status, validation_errors_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item["file_id"],
                    batch_id,
                    workspace_id,
                    item["file_name"],
                    item.get("media_type", "application/pdf"),
                    item.get("size_bytes", 0),
                    item.get("storage_uri"),
                    item.get("status", "needs_review"),
                    json.dumps(item.get("extraction", {})),
                    json.dumps(item.get("warnings", [])),
                    json.dumps(item.get("errors", [])),
                    item.get("validation_status", "pending"),
                    json.dumps(item.get("validation_errors", [])),
                    now,
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
                    "validation_status": r["validation_status"] if "validation_status" in r.keys() else "pending",
                    "validation_errors": json.loads(r["validation_errors_json"] or "[]") if "validation_errors_json" in r.keys() else [],
                })

            return {
                "batch_id": batch_row["batch_id"],
                "created_at": batch_row["created_at"],
                "workspace_id": batch_row["workspace_id"] if "workspace_id" in batch_row.keys() else "default-ws",
                "items": items,
            }

    def check_duplicate(
        self,
        supplier_tax_id: Optional[str],
        invoice_series: Optional[str],
        invoice_number: Optional[str],
        invoice_date: Optional[str],
        exclude_file_id: Optional[str] = None,
    ) -> bool:
        """Return True if a matching invoice already exists in the database.

        Match criteria: same supplier_tax_id + invoice_number (minimum).
        invoice_series and invoice_date refine the match when present.
        exclude_file_id allows re-checking the same file on update.
        """
        if not supplier_tax_id or not invoice_number:
            return False
        with closing(self._get_connection()) as conn:
            rows = conn.execute(
                "SELECT file_id, extraction_json FROM invoice_items",
            ).fetchall()
        for row in rows:
            if exclude_file_id and row["file_id"] == exclude_file_id:
                continue
            try:
                ext = json.loads(row["extraction_json"] or "{}")
            except Exception:
                continue
            if ext.get("supplier_tax_id") != supplier_tax_id:
                continue
            if ext.get("invoice_number") != invoice_number:
                continue
            if invoice_series and ext.get("invoice_series") and ext.get("invoice_series") != invoice_series:
                continue
            if invoice_date and ext.get("invoice_date") and ext.get("invoice_date") != invoice_date:
                continue
            return True
        return False

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
                "workspace_id": row["workspace_id"] if "workspace_id" in row.keys() else "default-ws",
                "file_name": row["file_name"],
                "media_type": row["media_type"],
                "size_bytes": row["size_bytes"],
                "storage_uri": row["storage_uri"],
                "status": row["status"],
                "invoice_type": row["invoice_type"] if "invoice_type" in row.keys() else "dau_vao",
                "note": row["note"] if "note" in row.keys() else "",
                "extraction": json.loads(row["extraction_json"] or "{}"),
                "warnings": json.loads(row["warnings_json"] or "[]"),
                "errors": json.loads(row["errors_json"] or "[]"),
                "validation_status": row["validation_status"] if "validation_status" in row.keys() else "pending",
                "validation_errors": json.loads(row["validation_errors_json"] or "[]") if "validation_errors_json" in row.keys() else [],
            }

    def update_item_extraction_and_status(
        self,
        file_id: str,
        extraction: Dict[str, Any],
        warnings: List[str],
        errors: List[Dict[str, Any]],
        validation_status: str,
        validation_errors: List[Dict[str, Any]],
        status: str = "needs_review",
    ) -> bool:
        now_str = datetime.now().isoformat()
        with closing(self._get_connection()) as conn:
            cur = conn.execute(
                """
                UPDATE invoice_items
                SET extraction_json = ?,
                    warnings_json = ?,
                    errors_json = ?,
                    validation_status = ?,
                    validation_errors_json = ?,
                    status = ?,
                    updated_at = ?
                WHERE file_id = ?
                """,
                (
                    json.dumps(extraction),
                    json.dumps(warnings),
                    json.dumps(errors),
                    validation_status,
                    json.dumps(validation_errors),
                    status,
                    now_str,
                    file_id,
                ),
            )
            conn.commit()
            return cur.rowcount > 0

    def update_item(
        self,
        batch_id: str,
        file_id: str,
        updates: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            item_row = conn.execute(
                "SELECT * FROM invoice_items WHERE file_id = ? AND batch_id = ?",
                (file_id, batch_id),
            ).fetchone()
            if not item_row:
                return None

            current_extraction = json.loads(item_row["extraction_json"] or "{}")
            old_status = item_row["status"]
            old_invoice_type = item_row["invoice_type"] if "invoice_type" in item_row.keys() else "dau_vao"
            old_note = item_row["note"] if "note" in item_row.keys() else ""
            workspace_id = item_row["workspace_id"] if "workspace_id" in item_row.keys() else "default-ws"

            new_status = updates.get("status", old_status)
            new_invoice_type = updates.get("invoice_type", old_invoice_type)
            new_note = updates.get("note", old_note)
            override_reason = updates.get("override_reason")

            # Track changes for audit log
            changes: Dict[str, Any] = {}
            if new_status != old_status:
                changes["status"] = {"old": old_status, "new": new_status}
            if new_invoice_type != old_invoice_type:
                changes["invoice_type"] = {"old": old_invoice_type, "new": new_invoice_type}
            if new_note != old_note:
                changes["note"] = {"old": old_note, "new": new_note}

            FIRST_CLASS = {"status", "invoice_type", "note", "override_reason"}

            # Apply field updates to extraction dictionary and record changes
            for k, v in updates.items():
                if k not in FIRST_CLASS and v is not None:
                    old_v = current_extraction.get(k)
                    if old_v != v:
                        changes[f"extraction.{k}"] = {"old": old_v, "new": v}
                        current_extraction[k] = v

            # Re-run validation on updated extraction data
            def _dup_checker(mst, series, number, inv_date):
                return self.check_duplicate(
                    supplier_tax_id=mst,
                    invoice_series=series,
                    invoice_number=number,
                    invoice_date=inv_date,
                    exclude_file_id=file_id,
                )

            val_issues = validate_invoice(current_extraction, duplicate_checker=_dup_checker)
            val_errors = [i.to_dict() for i in val_issues if i.severity == "error"]
            val_warnings = [i.to_dict() for i in val_issues if i.severity in ("warning", "info")]
            validation_status = "error" if val_errors else ("warning" if val_warnings else "ok")
            all_val_issues = val_errors + val_warnings

            # ── Backend Enforcement (P0) ──────────────────────────────────
            # Reject approval if validation errors exist and override_reason is missing
            if new_status == "approved" and val_errors:
                if not override_reason or not str(override_reason).strip():
                    error_msgs = "; ".join(e.get("message", "") for e in val_errors)
                    raise ValueError(
                        f"Không thể phê duyệt hóa đơn có {len(val_errors)} lỗi kiểm tra số liệu: [{error_msgs}]. "
                        f"Bắt buộc phải cung cấp lý do giải trình (override_reason) hợp lệ."
                    )

            now = datetime.now().isoformat()

            # Execute update and audit log in the same transaction
            conn.execute("""
                UPDATE invoice_items
                SET status = ?, extraction_json = ?, invoice_type = ?, note = ?,
                    validation_status = ?, validation_errors_json = ?, updated_at = ?
                WHERE file_id = ? AND batch_id = ?
            """, (
                new_status,
                json.dumps(current_extraction),
                new_invoice_type,
                new_note,
                validation_status,
                json.dumps(all_val_issues),
                now,
                file_id,
                batch_id,
            ))

            if changes or override_reason:
                log_id = f"audit-{uuid.uuid4().hex[:12]}"
                action = "override" if (override_reason or (old_status != "approved" and new_status == "approved" and val_errors)) else "update"
                conn.execute("""
                    INSERT INTO audit_logs (
                        log_id, workspace_id, entity_type, entity_id, action,
                        user_id, changes_json, reason, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_id,
                    workspace_id,
                    "invoice_item",
                    file_id,
                    action,
                    user_id,
                    json.dumps(changes),
                    override_reason,
                    now,
                ))

            conn.commit()

            return {
                "file_id": file_id,
                "batch_id": batch_id,
                "workspace_id": workspace_id,
                "file_name": item_row["file_name"],
                "storage_uri": item_row["storage_uri"],
                "status": new_status,
                "invoice_type": new_invoice_type,
                "note": new_note,
                "extraction": current_extraction,
                "warnings": json.loads(item_row["warnings_json"] or "[]"),
                "errors": json.loads(item_row["errors_json"] or "[]"),
                "validation_status": validation_status,
                "validation_errors": all_val_issues,
            }

    def list_audit_logs(
        self,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        workspace_id: str = "default-ws",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            query = "SELECT * FROM audit_logs WHERE workspace_id = ?"
            params: list[Any] = [workspace_id]
            if entity_id:
                query += " AND entity_id = ?"
                params.append(entity_id)
            if entity_type:
                query += " AND entity_type = ?"
                params.append(entity_type)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, tuple(params)).fetchall()
            return [
                {
                    "log_id": r["log_id"],
                    "workspace_id": r["workspace_id"],
                    "entity_type": r["entity_type"],
                    "entity_id": r["entity_id"],
                    "action": r["action"],
                    "user_id": r["user_id"],
                    "changes": json.loads(r["changes_json"] or "{}"),
                    "reason": r["reason"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    # ── Background Job Management (P0) ───────────────────────────

    def enqueue_job(
        self,
        batch_id: str,
        file_id: str,
        workspace_id: str = "default-ws",
        user_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        max_attempts: int = 3,
    ) -> Dict[str, Any]:
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        with closing(self._get_connection()) as conn:
            # Check idempotency
            if idempotency_key:
                existing = conn.execute(
                    "SELECT * FROM jobs WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if existing:
                    return self._row_to_job_dict(existing)

            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, batch_id, file_id, workspace_id, created_by_user_id,
                    status, attempt_count, max_attempts, next_attempt_at,
                    idempotency_key, created_at
                ) VALUES (?, ?, ?, ?, ?, 'queued', 0, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    batch_id,
                    file_id,
                    workspace_id,
                    user_id,
                    max_attempts,
                    now,
                    idempotency_key,
                    now,
                ),
            )
            conn.commit()
            return {
                "job_id": job_id,
                "batch_id": batch_id,
                "file_id": file_id,
                "workspace_id": workspace_id,
                "status": "queued",
                "attempt_count": 0,
                "max_attempts": max_attempts,
                "created_at": now,
            }

    def claim_next_job(
        self,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> Optional[Dict[str, Any]]:
        """Atomically claim the next eligible job using SQLite immediate transaction."""
        now = datetime.now()
        now_str = now.isoformat()
        lease_expires = (now + timedelta(seconds=lease_seconds)).isoformat()

        with closing(self._get_connection()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            candidate = conn.execute(
                """
                SELECT job_id, attempt_count, max_attempts FROM jobs
                WHERE status = 'queued'
                   OR (status = 'running' AND lease_expires_at < ?)
                   OR (status = 'retrying' AND next_attempt_at <= ?)
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (now_str, now_str),
            ).fetchone()

            if not candidate:
                conn.commit()
                return None

            job_id = candidate["job_id"]
            new_attempt = candidate["attempt_count"] + 1

            conn.execute(
                """
                UPDATE jobs
                SET status = 'running',
                    attempt_count = ?,
                    worker_id = ?,
                    lease_expires_at = ?,
                    heartbeat_at = ?,
                    started_at = COALESCE(started_at, ?)
                WHERE job_id = ?
                """,
                (new_attempt, worker_id, lease_expires, now_str, now_str, job_id),
            )
            conn.commit()

            updated = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return self._row_to_job_dict(updated) if updated else None

    def heartbeat_job(self, job_id: str, worker_id: str, extend_seconds: int = 60) -> bool:
        now = datetime.now()
        now_str = now.isoformat()
        lease_expires = (now + timedelta(seconds=extend_seconds)).isoformat()
        with closing(self._get_connection()) as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET heartbeat_at = ?, lease_expires_at = ?
                WHERE job_id = ? AND worker_id = ? AND status = 'running'
                """,
                (now_str, lease_expires, job_id, worker_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def complete_job(self, job_id: str, routing_decision: Optional[Dict[str, Any]] = None) -> bool:
        now_str = datetime.now().isoformat()
        routing_json = json.dumps(routing_decision) if routing_decision else None
        with closing(self._get_connection()) as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status = 'completed',
                    completed_at = ?,
                    routing_decision_json = COALESCE(?, routing_decision_json),
                    last_error_code = NULL,
                    last_error_message = NULL
                WHERE job_id = ?
                """,
                (now_str, routing_json, job_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def fail_job(
        self,
        job_id: str,
        error_code: str,
        error_message: str,
        backoff_seconds: int = 5,
    ) -> str:
        """Fail or schedule a retry for the job. Returns new status ('retrying' or 'failed')."""
        now = datetime.now()
        now_str = now.isoformat()
        with closing(self._get_connection()) as conn:
            job = conn.execute(
                "SELECT attempt_count, max_attempts FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if not job:
                return "failed"

            attempt = job["attempt_count"]
            max_att = job["max_attempts"]

            if attempt < max_att:
                next_at = (now + timedelta(seconds=backoff_seconds * attempt)).isoformat()
                new_status = "retrying"
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'retrying',
                        next_attempt_at = ?,
                        last_error_code = ?,
                        last_error_message = ?
                    WHERE job_id = ?
                    """,
                    (next_at, error_code, error_message, job_id),
                )
            else:
                new_status = "failed"
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'failed',
                        completed_at = ?,
                        last_error_code = ?,
                        last_error_message = ?
                    WHERE job_id = ?
                    """,
                    (now_str, error_code, error_message, job_id),
                )
            conn.commit()
            return new_status

    def recover_stale_jobs(self) -> int:
        now_str = datetime.now().isoformat()
        with closing(self._get_connection()) as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status = 'queued', worker_id = NULL, lease_expires_at = NULL
                WHERE status = 'running' AND lease_expires_at < ?
                """,
                (now_str,),
            )
            conn.commit()
            return cur.rowcount

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return self._row_to_job_dict(row) if row else None

    def list_jobs(
        self,
        batch_id: Optional[str] = None,
        workspace_id: str = "default-ws",
    ) -> List[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            if batch_id:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE batch_id = ? ORDER BY created_at ASC",
                    (batch_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 100",
                    (workspace_id,),
                ).fetchall()
            return [self._row_to_job_dict(r) for r in rows]

    def _row_to_job_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "job_id": row["job_id"],
            "batch_id": row["batch_id"],
            "file_id": row["file_id"],
            "workspace_id": row["workspace_id"],
            "created_by_user_id": row["created_by_user_id"],
            "status": row["status"],
            "attempt_count": row["attempt_count"],
            "max_attempts": row["max_attempts"],
            "next_attempt_at": row["next_attempt_at"],
            "worker_id": row["worker_id"],
            "lease_expires_at": row["lease_expires_at"],
            "heartbeat_at": row["heartbeat_at"],
            "idempotency_key": row["idempotency_key"],
            "last_error_code": row["last_error_code"],
            "last_error_message": row["last_error_message"],
            "routing_decision": json.loads(row["routing_decision_json"] or "null") if row["routing_decision_json"] else None,
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
        }

