# Kế hoạch triển khai sửa lỗi và tăng độ tin cậy ứng dụng hóa đơn

> **Dành cho agent thực thi:** BẮT BUỘC dùng skill `subagent-driven-development` (khuyến nghị) hoặc `executing-plans` để thực hiện từng task. Mỗi bước dùng ô kiểm tra `- [ ]` để theo dõi.

**Mục tiêu:** Sửa các lỗi đã xác nhận để Excel chỉ chứa hóa đơn được duyệt, bộ đọc không bịa số liệu, upload được giới hạn và lưu an toàn, giao diện không hiển thị trạng thái giả, và toàn bộ test chạy thành công.

**Kiến trúc:** Giữ FastAPI, SQLite, JavaScript thuần và pytest. Backend nhận các phụ thuộc có thể cấu hình để test dùng database/kho file tạm; bộ heuristic chỉ trích xuất số tiền có nhãn; frontend dùng một helper thuần để chỉ áp dụng thay đổi sau khi backend xác nhận.

**Công nghệ:** Python 3.11, FastAPI, Pydantic 2, SQLite, openpyxl, pytest, JavaScript ES2020 và Node built-in test runner.

## Ràng buộc chung

- Tối đa 20 file trong một batch.
- Tối đa 20 MiB cho mỗi file.
- Chỉ nhận PDF, PNG, JPEG và TIFF.
- Không thêm đăng nhập, multi-tenant hoặc OCR cục bộ trong kế hoạch này.
- Không sửa hoặc xóa database/file thật trong `data/`.
- Mọi thay đổi hành vi phải theo chu trình RED → GREEN → REFACTOR.
- Không tuyên bố hoàn thành khi còn test lỗi.

---

### Task 1: Khôi phục hợp đồng test và cô lập dữ liệu test

**Files:**
- Modify: `app-accounting-batch/tests/test_real_accounting.py`
- Modify: `app-accounting-batch/tests/test_api.py`
- Modify: `app-accounting-batch/src/app_accounting_batch/api.py`

**Interfaces:**
- Consumes: `SQLiteInvoiceRepository(db_path)` hiện có.
- Produces: `create_app(repo=None, storage_dir=None)` để mọi test dùng tài nguyên tạm.

- [ ] **Bước 1: Sửa test hợp đồng tuple đang lỗi**

Đổi lời gọi trong `test_extract_with_heuristics` thành:

```python
values, warnings = extract_with_heuristics(text, "HOA_DON_MAI_LINH.pdf")
assert values["supplier_tax_id"] == "0101234567"
assert values["total_amount"] == 1650000.0
assert values["currency"] == "VND"
```

- [ ] **Bước 2: Buộc test API dùng database và storage tạm**

Trong `TestAccountingBatchAPI.setUp`, tạo `TemporaryDirectory`, repository tạm và app tạm:

```python
self.temp_dir = tempfile.TemporaryDirectory()
root = Path(self.temp_dir.name)
self.repo = SQLiteInvoiceRepository(str(root / "test.db"))
self.app = create_app(self.repo, storage_dir=root / "storage")
self.client = TestClient(self.app)
```

Trong `tearDown`:

```python
self.temp_dir.cleanup()
```

- [ ] **Bước 3: Chạy test để xác nhận RED đúng nguyên nhân**

Run:

```powershell
$env:PYTHONPATH='..\core-shared\src;src'
pytest tests/test_api.py tests/test_real_accounting.py -q
```

Expected: lỗi vì `create_app` chưa nhận `storage_dir`; test tuple không còn lỗi.

- [ ] **Bước 4: Thêm tham số storage tạm tối thiểu**

Trong `api.py`:

```python
def create_app(
    repo: Optional[SQLiteInvoiceRepository] = None,
    *,
    storage_dir: Path | str | None = None,
) -> FastAPI:
    repository = repo or SQLiteInvoiceRepository()
    active_storage_dir = Path(storage_dir) if storage_dir else Path("data/storage")
    active_storage_dir.mkdir(parents=True, exist_ok=True)
```

Mọi thao tác lưu/tải file trong factory phải dùng `active_storage_dir`, không dùng biến toàn cục.

- [ ] **Bước 5: Chạy lại test Task 1**

Expected: các test API không ghi vào `data/`; chỉ còn lỗi hành vi export đã biết.

---

### Task 2: Chỉ xuất hóa đơn đã được duyệt

**Files:**
- Modify: `app-accounting-batch/src/app_accounting_batch/api.py`
- Modify: `app-accounting-batch/tests/test_audit_fixes.py`
- Modify: `app-accounting-batch/tests/test_api.py`

**Interfaces:**
- Consumes: `repository.get_batch(batch_id)`.
- Produces: XLSX chỉ từ `status == "approved"`; HTTP 400 nếu không có bản ghi hợp lệ.

- [ ] **Bước 1: Giữ hai regression test hiện đang RED**

Hai test sau phải tiếp tục thất bại trước khi sửa:

```text
test_excel_export_approval_filter_only
test_excel_export_fails_when_zero_approved
```

- [ ] **Bước 2: Sửa test API cũ để duyệt trước khi export**

Trong `test_export_batch_returns_xlsx`, lấy `file_id` từ batch vừa upload, PATCH trạng thái thành `approved`, rồi mới gọi export. Test không được ngầm cho phép xuất bản nháp.

- [ ] **Bước 3: Sửa endpoint export tối thiểu**

```python
approved_records = []
for item in batch["items"]:
    if item.get("status") != "approved" or not item.get("extraction"):
        continue
    approved_records.append({
        "source_file_id": item["file_id"],
        **item["extraction"],
    })

if not approved_records:
    raise HTTPException(
        status_code=400,
        detail="Không có hóa đơn nào đã được duyệt để xuất Excel.",
    )
```

Không thêm cột nhãn cho hóa đơn nháp vì hóa đơn nháp không được phép đi vào workbook.

- [ ] **Bước 4: Chạy test export**

Run:

```powershell
pytest tests/test_audit_fixes.py tests/test_api.py -q
```

Expected: PASS.

---

### Task 3: Trích xuất tiền theo nhãn, không suy diễn

**Files:**
- Modify: `app-accounting-batch/src/app_accounting_batch/smart_extractor.py`
- Modify: `app-accounting-batch/tests/test_real_accounting.py`
- Modify: `app-accounting-batch/tests/test_audit_fixes.py`

**Interfaces:**
- Produces: `extract_with_heuristics(text, filename) -> tuple[dict, list[str]]`.
- Produces: `_parse_labeled_amount(text, labels) -> float | None`.
- Produces: `_normalize_extraction_values(raw) -> tuple[dict, list[str]]`.

- [ ] **Bước 1: Viết regression test cho số lớn không có nhãn**

```python
def test_large_identifier_is_not_used_as_total():
    values, warnings = extract_with_heuristics(
        "MST: 0317333953\nSo tai khoan: 1234567890123",
        "invoice.pdf",
    )
    assert values["total_amount"] == 0.0
    assert values["subtotal"] == 0.0
    assert values["tax_amount"] == 0.0
    assert values["items"] == []
    assert warnings
```

- [ ] **Bước 2: Viết test cho các số có nhãn rõ ràng**

```python
def test_labeled_amounts_are_extracted_without_calculation():
    text = "Tiền trước thuế: 1.000.000\nTiền thuế GTGT: 80.000\nTổng thanh toán: 1.080.000"
    values, _ = extract_with_heuristics(text, "invoice.pdf")
    assert values["subtotal"] == 1_000_000
    assert values["tax_amount"] == 80_000
    assert values["total_amount"] == 1_080_000
```

- [ ] **Bước 3: Chạy hai test mới để xác nhận RED**

Expected: test số lớn thất bại vì code đang lấy `max`; test item rỗng thất bại vì code đang tự tạo item.

- [ ] **Bước 4: Viết bộ đọc số tiền có nhãn**

Tạo helper nhận các nhãn Việt/Anh, chỉ tìm số trên cùng dòng hoặc ngay sau dấu hai chấm. Chuẩn hóa dấu phân cách Việt Nam nhưng không thực hiện phép tính thuế.

Ánh xạ:

```python
subtotal_labels = ("tiền trước thuế", "cộng tiền hàng", "subtotal")
tax_labels = ("tiền thuế gtgt", "thuế vat", "tax amount", "vat amount")
total_labels = ("tổng thanh toán", "tổng cộng", "total payment", "grand total")
```

Nếu không tìm thấy nhãn tương ứng, giữ `0.0` và thêm cảnh báo. Luôn giữ `items=[]` nếu không thật sự trích xuất được dòng hàng.

- [ ] **Bước 5: Xóa hardcode nhà cung cấp**

Xóa các nhánh đặc biệt cho AZDIGI và Cổng Việt Nam. Regex chung hoặc Gemini phải cung cấp dữ liệu; nếu không thì để trống/cảnh báo.

- [ ] **Bước 6: Chuẩn hóa kết quả Gemini**

`_normalize_extraction_values` chỉ cho phép đúng các trường schema, ép các trường tiền thành số không âm, chuỗi thành chuỗi, và `items` thành danh sách object hợp lệ. Dữ liệu sai kiểu trở về giá trị an toàn và sinh cảnh báo.

- [ ] **Bước 7: Chạy toàn bộ test extractor**

Run:

```powershell
pytest tests/test_real_accounting.py tests/test_audit_fixes.py tests/test_extractor.py -q
```

Expected: PASS.

---

### Task 4: Giới hạn upload và lưu file an toàn

**Files:**
- Modify: `app-accounting-batch/src/app_accounting_batch/api.py`
- Modify: `app-accounting-batch/src/app_accounting_batch/persistence.py`
- Create: `app-accounting-batch/tests/test_upload_safety.py`

**Interfaces:**
- Produces: `sanitize_upload_name(name: str) -> str`.
- Produces: `create_app(..., storage_dir=..., parser=..., extractor=...)` để test cô lập lỗi.
- Persists: trường `storage_uri` nullable trong `invoice_items`.

- [ ] **Bước 1: Viết test RED cho chính sách upload**

Test các trường hợp:

```text
21 file → HTTP 400
application/x-msdownload → error item, không lưu file
file PDF lớn hơn MAX_FILE_BYTES → error item
filename ../../outside.pdf → file thực vẫn nằm trong storage tạm
```

- [ ] **Bước 2: Viết test RED cho cô lập lỗi**

Tiêm parser test có chủ đích ném lỗi cho `bad.pdf` và trả document cho `good.pdf`. Khẳng định response có hai item, một item có `errors`, item còn lại có extraction.

- [ ] **Bước 3: Viết test RED cho tải file gốc**

Upload file hợp lệ vào storage tạm, gọi `/api/v1/accounting/files/{file_id}`, khẳng định nội dung trả về đúng byte đã upload.

- [ ] **Bước 4: Thêm giới hạn và kiểm tra loại file**

Trong `api.py`:

```python
MAX_BATCH_FILES = 20
MAX_FILE_BYTES = 20 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {
    "application/pdf": {".pdf"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/tiff": {".tif", ".tiff"},
}
```

Đọc file bằng `await upload.read(MAX_FILE_BYTES + 1)` và từ chối nếu dài hơn giới hạn.

- [ ] **Bước 5: Làm sạch tên file**

Chỉ giữ basename, Unicode chữ/số, dấu chấm, gạch dưới và gạch ngang; thay ký tự khác bằng `_`; tên rỗng trở thành `invoice` cộng phần mở rộng hợp lệ. Sau khi resolve, xác nhận đường dẫn con vẫn nằm trong `active_storage_dir.resolve()`.

- [ ] **Bước 6: Lưu storage URI trong SQLite**

Thêm cột `storage_uri TEXT` vào câu lệnh tạo bảng. Với database cũ, đọc `PRAGMA table_info(invoice_items)` và chạy:

```sql
ALTER TABLE invoice_items ADD COLUMN storage_uri TEXT
```

chỉ khi cột chưa tồn tại. Cập nhật save/get để đọc ghi trường này.

- [ ] **Bước 7: Tải file bằng đường dẫn đã lưu**

Thêm repository method tìm item theo `file_id`; endpoint chỉ trả file nếu record tồn tại và đường dẫn resolve vẫn nằm trong storage được cấu hình. Không dùng `glob(f"{file_id}_*")`.

- [ ] **Bước 8: Chạy test upload**

Run:

```powershell
pytest tests/test_upload_safety.py -q
```

Expected: PASS.

---

### Task 5: Chỉ cập nhật giao diện sau khi backend xác nhận

**Files:**
- Create: `frontend/src/state-sync.js`
- Create: `frontend/tests/state-sync.test.js`
- Modify: `frontend/index.html`
- Modify: `frontend/src/app.js`

**Interfaces:**
- Produces: `applyConfirmedUpdate(target, nextValues, persist) -> Promise<boolean>`.
- Consumes: callback `persist(nextValues) -> Promise<boolean>`.

- [ ] **Bước 1: Viết Node test RED cho helper đồng bộ**

```javascript
test('does not mutate target when persistence fails', async () => {
  const invoice = { status: 'needs_review', total: 100 };
  const ok = await applyConfirmedUpdate(
    invoice,
    { status: 'approved', total: 200 },
    async () => false,
  );
  assert.equal(ok, false);
  assert.deepEqual(invoice, { status: 'needs_review', total: 100 });
});

test('applies values after persistence succeeds', async () => {
  const invoice = { status: 'needs_review' };
  const ok = await applyConfirmedUpdate(
    invoice,
    { status: 'approved' },
    async () => true,
  );
  assert.equal(ok, true);
  assert.equal(invoice.status, 'approved');
});
```

- [ ] **Bước 2: Chạy Node test và xác nhận RED**

Run:

```powershell
node --test frontend/tests/state-sync.test.js
```

Expected: FAIL vì module chưa tồn tại.

- [ ] **Bước 3: Viết helper tối thiểu**

`state-sync.js` xuất CommonJS khi chạy Node và gắn `window.InvoiceStateSync` khi chạy trình duyệt. Helper gọi `persist` trước, chỉ `Object.assign(target, nextValues)` khi kết quả là `true`.

- [ ] **Bước 4: Dùng helper trong toàn bộ luồng giao diện**

Cập nhật inline edit, `approveInv`, `approveAll` và `saveInspector`. Không mutate `inv` trước khi PATCH thành công. `approveAll` đếm số callback trả `false` và thông báo một lần sau khi xử lý hết.

- [ ] **Bước 5: Nạp helper trước app.js**

Trong `index.html`, thêm:

```html
<script src="/src/state-sync.js"></script>
<script src="/src/app.js"></script>
```

- [ ] **Bước 6: Chạy Node test**

Expected: PASS.

---

### Task 6: Verification và review cuối

**Files:**
- Modify nếu cần: các file đã thay đổi ở Task 1–5.

**Interfaces:**
- Produces: bằng chứng test đầy đủ và báo cáo các phần cố ý để dành.

- [ ] **Bước 1: Chạy toàn bộ test ứng dụng hóa đơn**

```powershell
$env:PYTHONPATH='..\core-shared\src;src'
pytest tests -q
```

Expected: tất cả PASS, không có warning Pydantic `dict()`.

- [ ] **Bước 2: Chạy toàn bộ test backend cũ**

```powershell
python -m unittest discover -s tests -v
```

Expected: PASS; integration Docling có thể skip nếu dependency/model chưa cài.

- [ ] **Bước 3: Chạy test frontend**

```powershell
node --test frontend/tests/state-sync.test.js
```

Expected: PASS.

- [ ] **Bước 4: Kiểm tra cú pháp và dữ liệu thật không bị chạm**

Xác nhận `data/accounting_workspace.db` và các file đang có không bị test thay đổi thời gian sửa. Xác nhận không có file test bị ghi vào `data/storage`.

- [ ] **Bước 5: Review độc lập**

Reviewer kiểm tra approved-only export, không suy diễn tiền, giới hạn upload, path traversal, migration SQLite, frontend rollback và độ bao phủ test. Sửa mọi lỗi Critical/Important rồi chạy lại ba bộ test.

- [ ] **Bước 6: Báo cáo hoàn thành**

Báo số test đạt/thất bại/skip, liệt kê file chính đã sửa và nhắc rõ các phần chưa thuộc phạm vi: authentication, tenant isolation và OCR cục bộ.
