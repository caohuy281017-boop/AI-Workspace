"""pytest conftest.py — adds both package src directories to sys.path.

This allows tests in app-accounting-batch to import from both:
  - app_accounting_batch  (this app's src/)
  - core_shared           (the shared core package src/)

Without needing pip install for either package during development.
"""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

# app-accounting-batch/src
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# core-shared/src (two levels up from app-accounting-batch, then into core-shared)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core-shared" / "src"))

# Importing app_accounting_batch.api creates the default ASGI app. Redirect its
# database and original-file storage so test collection never touches user data.
_test_data_dir = Path(tempfile.mkdtemp(prefix="accounting-tests-"))
os.environ["ACCOUNTING_DB_PATH"] = str(_test_data_dir / "accounting.db")
os.environ["ACCOUNTING_STORAGE_DIR"] = str(_test_data_dir / "storage")
atexit.register(shutil.rmtree, _test_data_dir, ignore_errors=True)
