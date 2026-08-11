# 📊 Báo Cáo Đánh Giá Benchmark Độ Chính Xác (Ground Truth)

- **Tổng số hóa đơn kiểm thử:** 20
- **Thời gian xử lý trung bình:** 0.65 ms / chứng từ
- **Độ chính xác tổng thể (Field-level Accuracy):** **86.16%**
- **Điểm chất lượng văn bản trung bình:** 0.967

## 1. Độ chính xác theo từng trường thông tin

| Trường thông tin | Tổng mẫu | Số mẫu đúng | Tỷ lệ chính xác (%) | Đánh giá |
| :--- | :---: | :---: | :---: | :---: |
| `supplier_name` | 20 | — | **85.0%** | ⚠️ Khá |
| `supplier_tax_id` | 20 | — | **78.95%** | ⚠️ Khá |
| `invoice_number` | 20 | — | **85.0%** | ⚠️ Khá |
| `invoice_date` | 20 | — | **100.0%** | ✅ Xuất sắc |
| `currency` | 20 | — | **100.0%** | ✅ Xuất sắc |
| `subtotal` | 20 | — | **80.0%** | ⚠️ Khá |
| `tax_amount` | 20 | — | **80.0%** | ⚠️ Khá |
| `total_amount` | 20 | — | **80.0%** | ⚠️ Khá |

## 2. Chi tiết từng chứng từ kiểm thử

| ID | Tệp hóa đơn | Routing Mode | Điểm Text | Kết quả trường số liệu |
| :--- | :--- | :---: | :---: | :--- |
| inv-01 | `1C26TAP_00008228_0317333953.pdf` | `text_only` | 0.98 | ⚠️ 7/8 trường khớp |
| inv-02 | `HD_AZDIGI_357073.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |
| inv-03 | `VIETTEL_TELECOM_0012903.pdf` | `text_only` | 0.98 | ⚠️ 7/8 trường khớp |
| inv-04 | `VNPT_MEDIA_004561.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |
| inv-05 | `FPT_TELECOM_77889.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |
| inv-06 | `GOOGLE_CLOUD_INV_2025.pdf` | `text_only` | 0.98 | ❌ 3/8 trường khớp |
| inv-07 | `AMAZON_AWS_2025_05.pdf` | `text_only` | 0.92 | ❌ 3/8 trường khớp |
| inv-08 | `MICROSOFT_AZURE_INV.pdf` | `text_only` | 0.92 | ❌ 3/8 trường khớp |
| inv-09 | `OPENAI_SUBSCRIPTION_06.pdf` | `text_only` | 0.79 | ❌ 3/7 trường khớp |
| inv-10 | `THE_GIOI_DI_DONG_098.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |
| inv-11 | `GOLDEN_GATE_RESTAURANT.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |
| inv-12 | `HIGHLANDS_COFFEE_INV.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |
| inv-13 | `FAHASA_BOOKSTORE_09.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |
| inv-14 | `TIKI_GLOBAL_CORP.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |
| inv-15 | `GRAB_VIETNAM_INV.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |
| inv-16 | `SHOPEE_EXPRESS_VN.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |
| inv-17 | `VIETRAVEL_AIR_TICKET.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |
| inv-18 | `VIETNAM_AIRLINES_INV.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |
| inv-19 | `PETROLIMEX_XANG_DAU.pdf` | `text_only` | 0.98 | ⚠️ 7/8 trường khớp |
| inv-20 | `EVN_DIEN_LUC_HN.pdf` | `text_only` | 0.98 | ✅ 8/8 trường khớp |

---
*Báo cáo được tạo tự động bởi `benchmark/run_benchmark.py`.*