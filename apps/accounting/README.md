# Accounting App

Ứng dụng tiếp nhận lô hóa đơn PDF/ảnh, trích xuất dữ liệu, cho phép người dùng sửa/duyệt và chỉ xuất các bản ghi đã duyệt sang XLSX.

## Thành phần

```text
src/accounting_app/
  api.py                HTTP delivery adapter
  service.py            Đường điều phối batch duy nhất
  persistence.py        SQLite repository
  pdf_parser.py         Parser PDF nhẹ cho MVP
  smart_extractor.py    Heuristic + Gemini theo từng request
  extractor.py          Adapter trích xuất theo LLMProvider port
  schema.py             Schema hóa đơn phiên bản hóa
  models.py             Model riêng của nghiệp vụ kế toán
```

## Trạng thái

- Upload nhiều file và cô lập lỗi theo file.
- Kiểm tra định dạng, phần mở rộng, kích thước và đường dẫn lưu trữ.
- Trích xuất heuristic hoặc Gemini.
- Lưu file gốc và dữ liệu review bằng SQLite.
- Sửa và duyệt hóa đơn qua API.
- Chỉ xuất hóa đơn đã duyệt sang XLSX.
- Có frontend review cơ bản.

Các hạng mục tiếp theo: evidence/confidence theo trường, validation số học sâu, OCR fallback, job queue, workspace/auth và audit log.

## Kiểm thử

Chạy từ root:

```powershell
python -m pytest apps/accounting/tests -q
```
