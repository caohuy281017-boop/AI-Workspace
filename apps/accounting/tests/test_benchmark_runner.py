"""Automated test for Benchmark Runner (Lát 6).

Verifies that:
- Ground truth dataset exists and contains >= 20 valid invoice definitions.
- Benchmark runner executes end-to-end without errors.
- Overall accuracy meets the minimum baseline (> 80%).
- Markdown report artifact is created and well-formed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmark.run_benchmark import run_benchmark


def test_ground_truth_file_structure():
    gt_path = (ROOT_DIR / "benchmark" / "ground_truth.json").resolve()
    assert gt_path.is_file(), f"{gt_path} must exist"

    with open(gt_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    invoices = data.get("invoices", [])
    assert len(invoices) >= 20, f"Ground truth must have at least 20 invoices, found {len(invoices)}"

    for inv in invoices:
        assert "id" in inv
        assert "filename" in inv
        assert "input_text" in inv
        assert "expected" in inv
        assert len(inv["input_text"].strip()) > 30


def test_run_benchmark_produces_valid_metrics_and_report():
    gt_path = (ROOT_DIR / "benchmark" / "ground_truth.json").resolve()
    result = run_benchmark(gt_path)

    assert result["total_documents"] >= 20
    assert result["overall_accuracy_pct"] >= 80.0
    assert result["avg_ms_per_doc"] < 100.0  # Must be fast

    assert "field_accuracies" in result
    assert result["field_accuracies"]["invoice_date"] >= 90.0
    assert result["field_accuracies"]["currency"] >= 90.0

    report_path = (ROOT_DIR / "benchmark" / "results_report.md").resolve()
    assert report_path.is_file(), "results_report.md must be generated"
    report_content = report_path.read_text(encoding="utf-8")
    assert "# 📊 Báo Cáo Đánh Giá" in report_content
    assert "Độ chính xác tổng thể" in report_content
