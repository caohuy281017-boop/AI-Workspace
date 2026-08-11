from fastapi.testclient import TestClient

from accounting_app.api import create_app
from accounting_app.persistence import SQLiteInvoiceRepository


def make_client(tmp_path):
    repo = SQLiteInvoiceRepository(str(tmp_path / "custom-fields.db"))
    return TestClient(create_app(repo, storage_dir=tmp_path / "storage")), repo


def test_custom_field_crud_and_reorder(tmp_path):
    client, _ = make_client(tmp_path)
    first = client.post(
        "/api/v1/accounting/settings/custom-fields",
        json={"code": "contract_no", "name": "Số hợp đồng", "is_required": True},
    )
    second = client.post(
        "/api/v1/accounting/settings/custom-fields",
        json={"code": "cost_center", "name": "Trung tâm chi phí", "visible_in_list": True},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    edited = client.patch(
        "/api/v1/accounting/settings/custom-fields/contract_no",
        json={"name": "Mã hợp đồng", "llm_prompt": "Đọc mã hợp đồng trên chứng từ"},
    )
    assert edited.json()["name"] == "Mã hợp đồng"

    reordered = client.put(
        "/api/v1/accounting/settings/custom-fields/reorder",
        json={"codes": ["cost_center", "contract_no"]},
    )
    assert [field["code"] for field in reordered.json()["fields"]] == [
        "cost_center", "contract_no"
    ]

    deleted = client.delete("/api/v1/accounting/settings/custom-fields/contract_no")
    assert deleted.status_code == 204
    assert [field["code"] for field in client.get(
        "/api/v1/accounting/settings/custom-fields"
    ).json()["fields"]] == ["cost_center"]


def test_custom_field_validation_and_duplicate_code(tmp_path):
    client, _ = make_client(tmp_path)
    invalid = client.post(
        "/api/v1/accounting/settings/custom-fields",
        json={"code": "Bad Code", "name": "Bad"},
    )
    assert invalid.status_code == 422

    payload = {"code": "project_code", "name": "Mã dự án"}
    assert client.post("/api/v1/accounting/settings/custom-fields", json=payload).status_code == 201
    assert client.post("/api/v1/accounting/settings/custom-fields", json=payload).status_code == 409


def test_custom_field_values_are_saved_inside_invoice_extraction(tmp_path):
    client, repo = make_client(tmp_path)
    repo.save_batch("batch-1", [{
        "file_id": "file-1", "file_name": "invoice.pdf",
        "status": "needs_review", "extraction": {}, "warnings": [], "errors": [],
    }])
    response = client.patch(
        "/api/v1/accounting/batches/batch-1/items/file-1",
        json={"custom_fields": {"project_code": "PRJ-01"}},
    )
    assert response.status_code == 200
    assert response.json()["extraction"]["custom_fields"] == {"project_code": "PRJ-01"}
