"""Run script for AI Workspace Backend & Frontend FastAPI Server.

Serves:
1. REST API endpoints at /api/v1/accounting/...
2. SPA Frontend files at /
"""

import sys
import uvicorn
from pathlib import Path

# Add python packages to sys.path
sys.path.insert(0, str(Path("app-accounting-batch/src").resolve()))
sys.path.insert(0, str(Path("core-shared/src").resolve()))
sys.path.insert(0, str(Path("backend/src").resolve()))

if __name__ == "__main__":
    print("[SERVER] Starting AI Workspace FastAPI Server on http://localhost:8000 ...")
    uvicorn.run("app_accounting_batch.api:app", host="0.0.0.0", port=8000, reload=False)
