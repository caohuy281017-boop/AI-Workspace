"""Isolated test configuration for the accounting application."""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "accounting" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "platform-core" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "platform-adapters" / "src"))

# Importing accounting_app.api creates the default ASGI app. Redirect its
# database and original-file storage so collection never touches user data.
_test_data_dir = Path(tempfile.mkdtemp(prefix="accounting-tests-"))
os.environ["ACCOUNTING_DB_PATH"] = str(_test_data_dir / "accounting.db")
os.environ["ACCOUNTING_STORAGE_DIR"] = str(_test_data_dir / "storage")
atexit.register(shutil.rmtree, _test_data_dir, ignore_errors=True)
