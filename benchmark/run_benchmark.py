"""Benchmark Evaluation Runner.

Runs the invoice extraction engine across the ground truth benchmark dataset (20 realistic invoices)
and generates a field-level accuracy and precision report in Markdown format.
"""

from __future__ import annotations

import json
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure packages and apps are on pythonpath
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "apps" / "accounting" / "src"))
sys.path.insert(0, str(ROOT_DIR / "packages" / "platform-core" / "src"))

from accounting_app.smart_extractor import extract_with_heuristics
from accounting_app.router import assess_text_quality


def _normalize_date_str(d: str | None) -> str | None:
    if not d:
        return None
    d = d.strip().replace("-", "/")
    parts = d.split("/")
    if len(parts) == 3:
        if len(parts[0]) == 4:  # YYYY/MM/DD -> DD/MM/YYYY
            return f"{int(parts[2]):02d}/{int(parts[1]):02d}/{parts[0]}"
        return f"{int(parts[0]):02d}/{int(parts[1]):02d}/{parts[2]}"
    return d


def _compare_names(extracted: str | None, expected: str | None) -> bool:
    if not expected:
        return True
    if not extracted:
        return False
    e_low = expected.lower().strip()
    x_low = extracted.lower().strip()
    return e_low in x_low or x_low in e_low or len(set(e_low.split()) & set(x_low.split())) >= 2


def _compare_amounts(extracted: float | None, expected: float | None, currency: str = "VND") -> bool:
    if expected is None:
        return extracted is None
    if extracted is None:
        return False
    diff = abs(Decimal(str(extracted)) - Decimal(str(expected)))
    tol = Decimal("1.0") if (currency or "VND").upper() == "VND" else Decimal("0.02")
    return diff <= tol


def _compare_exact(extracted: Any, expected: Any) -> bool:
    if expected is None:
        return True
    if extracted is None:
        return False
    return str(extracted).strip().lower() == str(expected).strip().lower()


def run_benchmark(ground_truth_path: Path | None = None) -> Dict[str, Any]:
    if ground_truth_path is None:
        ground_truth_path = Path(__file__).resolve().parent / "ground_truth.json"

    with open(ground_truth_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    invoices = data.get("invoices", [])
    total_invoices = len(invoices)

    fields_to_eval = [
        "supplier_name",
        "supplier_tax_id",
        "invoice_number",
        "invoice_date",
        "currency",
        "subtotal",
        "tax_amount",
        "total_amount",
    ]

    field_correct_counts: Dict[str, int] = {f: 0 for f in fields_to_eval}
    field_total_counts: Dict[str, int] = {f: 0 for f in fields_to_eval}
    routing_scores: List[float] = []
    document_results: List[Dict[str, Any]] = []

    start_time = time.perf_counter()

    for inv in invoices:
        inv_id = inv["id"]
        filename = inv.get("filename", f"{inv_id}.pdf")
        text = inv.get("input_text", "")
        expected = inv.get("expected", {})

        # Run routing
        routing = assess_text_quality(text, media_type=inv.get("media_type", "application/pdf"), filename=filename)
        routing_scores.append(routing.text_quality_score)

        # Run extraction
        extracted, warnings = extract_with_heuristics(text, filename)

        doc_eval: Dict[str, Any] = {
            "id": inv_id,
            "filename": filename,
            "routing_mode": routing.mode,
            "text_quality_score": routing.text_quality_score,
            "fields": {},
        }

        # Evaluate each field
        for f in fields_to_eval:
            exp_val = expected.get(f)
            if exp_val is not None:
                field_total_counts[f] += 1
                ext_val = extracted.get(f)
                match = False

                if f == "supplier_name":
                    match = _compare_names(ext_val, exp_val)
                elif f in ("total_amount", "subtotal", "tax_amount"):
                    match = _compare_amounts(ext_val, exp_val, currency=expected.get("currency", "VND"))
                elif f == "invoice_date":
                    match = _compare_exact(_normalize_date_str(ext_val), _normalize_date_str(exp_val))
                elif f == "invoice_number":
                    match = _compare_exact(ext_val, exp_val) or (
                        ext_val and exp_val and (str(ext_val).lstrip("0") == str(exp_val).lstrip("0"))
                    )
                else:
                    match = _compare_exact(ext_val, exp_val)

                if match:
                    field_correct_counts[f] += 1

                doc_eval["fields"][f] = {
                    "expected": exp_val,
                    "extracted": ext_val,
                    "match": match,
                }

        document_results.append(doc_eval)

    elapsed_time = time.perf_counter() - start_time
    avg_time_per_doc = (elapsed_time / total_invoices) * 1000  # ms

    # Calculate metrics
    field_accuracies = {
        f: (field_correct_counts[f] / max(1, field_total_counts[f])) * 100.0
        for f in fields_to_eval
    }
    total_expected_fields = sum(field_total_counts.values())
    total_correct_fields = sum(field_correct_counts.values())
    overall_accuracy = (total_correct_fields / max(1, total_expected_fields)) * 100.0

    summary = {
        "total_documents": total_invoices,
        "elapsed_seconds": round(elapsed_time, 3),
        "avg_ms_per_doc": round(avg_time_per_doc, 2),
        "overall_accuracy_pct": round(overall_accuracy, 2),
        "field_accuracies": {k: round(v, 2) for k, v in field_accuracies.items()},
        "avg_text_quality_score": round(sum(routing_scores) / max(1, len(routing_scores)), 3),
        "document_results": document_results,
    }

    # Generate Markdown Report
    report_md = _generate_markdown_report(summary)
    report_path = Path(__file__).resolve().parent / "results_report.md"
    report_path.write_text(report_md, encoding="utf-8")

    return summary


def _generate_markdown_report(summary: Dict[str, Any]) -> str:
    lines = [
        "# 📊 Báo Cáo Đánh Giá Benchmark Độ Chính Xác (Ground Truth)",
        "",
        f"- **Tổng số hóa đơn kiểm thử:** {summary['total_documents']}",
        f"- **Thời gian xử lý trung bình:** {summary['avg_ms_per_doc']} ms / chứng từ",
        f"- **Độ chính xác tổng thể (Field-level Accuracy):** **{summary['overall_accuracy_pct']}%**",
        f"- **Điểm chất lượng văn bản trung bình:** {summary['avg_text_quality_score']}",
        "",
        "## 1. Độ chính xác theo từng trường thông tin",
        "",
        "| Trường thông tin | Tổng mẫu | Số mẫu đúng | Tỷ lệ chính xác (%) | Đánh giá |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ]

    for field, acc in summary["field_accuracies"].items():
        eval_tag = "✅ Xuất sắc" if acc >= 90 else ("⚠️ Khá" if acc >= 75 else "🛑 Cần cải thiện")
        lines.append(f"| `{field}` | {summary['total_documents']} | — | **{acc}%** | {eval_tag} |")

    lines.extend([
        "",
        "## 2. Chi tiết từng chứng từ kiểm thử",
        "",
        "| ID | Tệp hóa đơn | Routing Mode | Điểm Text | Kết quả trường số liệu |",
        "| :--- | :--- | :---: | :---: | :--- |",
    ])

    for doc in summary["document_results"]:
        correct_fields = sum(1 for f_info in doc["fields"].values() if f_info["match"])
        total_fields = len(doc["fields"])
        status_icon = "✅" if correct_fields == total_fields else ("⚠️" if correct_fields >= total_fields - 1 else "❌")
        lines.append(
            f"| {doc['id']} | `{doc['filename']}` | `{doc['routing_mode']}` | {doc['text_quality_score']:.2f} | "
            f"{status_icon} {correct_fields}/{total_fields} trường khớp |"
        )

    lines.append("")
    lines.append("---")
    lines.append("*Báo cáo được tạo tự động bởi `benchmark/run_benchmark.py`.*")
    return "\n".join(lines)


if __name__ == "__main__":
    result = run_benchmark()
    print("=" * 60)
    print(f"BENCHMARK COMPLETED: {result['total_documents']} documents evaluated.")
    print(f"Overall Accuracy: {result['overall_accuracy_pct']}%")
    print(f"Average speed: {result['avg_ms_per_doc']} ms/doc")
    print("=" * 60)
    for field, acc in result["field_accuracies"].items():
        print(f"  - {field:20s}: {acc}%")
    print("=" * 60)
