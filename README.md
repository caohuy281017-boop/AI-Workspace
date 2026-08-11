# AI Workspace

Nền tảng File-First AI xử lý tài liệu doanh nghiệp bằng các workflow chuyên biệt, có bước kiểm duyệt của con người và khả năng thay thế parser/OCR/LLM mà không làm thay đổi nghiệp vụ.

## Cấu trúc

```text
apps/                         Ứng dụng nghiệp vụ độc lập
  accounting/                Sản phẩm hóa đơn và kế toán (đang phát triển chính)
  document-translator/       Bộ khung dịch tài liệu
  meeting-notes/             Bộ khung biên bản cuộc họp

packages/                     Thành phần dùng chung
  platform-core/             Domain models và ports, không phụ thuộc nhà cung cấp
  platform-adapters/         Docling, LLM gateway và bộ xuất XLSX

server/                       Điểm khởi động HTTP
frontend/                     Giao diện web
scripts/dev/                  Công cụ thử nghiệm dành cho lập trình viên
docs/                         Kiến trúc, sản phẩm và kiểm kê giấy phép
_legacy/                      Mã cũ chỉ dùng để đối chiếu, không thuộc runtime/test
```

Quy tắc phụ thuộc:

```text
apps ───────────────→ platform-core
  │                         ↑
  └──→ platform-adapters ───┘

server → apps + adapters
platform-core → không phụ thuộc app, web framework hoặc SDK nhà cung cấp
```

## Accounting MVP

Luồng đang chạy:

```text
Upload PDF/ảnh
→ AccountingBatchService
→ parser
→ heuristic/Gemini extractor
→ SQLite
→ người dùng kiểm duyệt
→ xuất XLSX các hóa đơn đã duyệt
```

Mỗi file lỗi được cô lập, không làm hỏng toàn bộ batch. Khóa Gemini truyền trong request chỉ thuộc request/job đó và không được ghi vào trạng thái môi trường toàn tiến trình.

## Chạy ứng dụng

Từ thư mục gốc:

```powershell
python server/run_server.py
```

Mở `http://localhost:8000`.

## Chạy kiểm thử

```powershell
python -m pytest -q
```

Kiểm thử Docling thật được đánh dấu `integration` và không chạy mặc định:

```powershell
python -m pytest -m integration packages/platform-adapters/tests/integration
```

## Nguyên tắc phát triển

- Tìm và mở rộng thành phần hiện có trước khi tạo class/package mới.
- Nghiệp vụ của từng app nằm trong app đó; không đưa model kế toán vào lõi dùng chung.
- SDK Gemini, OpenAI, Docling và openpyxl chỉ xuất hiện ở lớp adapter/composition.
- API chỉ nhận/trả dữ liệu và gọi application service; không tự điều phối workflow dài.
- Mọi engine bên thứ ba phải được ghi nhận trong `docs/REPO_MAP.md` trước khi tích hợp.

Xem thêm [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PRODUCT.md](docs/PRODUCT.md) và [docs/STRUCTURE.md](docs/STRUCTURE.md).
