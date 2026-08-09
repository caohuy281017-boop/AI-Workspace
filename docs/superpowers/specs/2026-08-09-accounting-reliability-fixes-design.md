# Thiết kế sửa lỗi và tăng độ tin cậy cho ứng dụng hóa đơn

## Mục tiêu

Sửa các lỗi quan trọng của ứng dụng xử lý hóa đơn để dự án đủ ổn định cho giai đoạn phát triển MVP tiếp theo:

- Excel chỉ chứa hóa đơn đã được người dùng duyệt.
- Hệ thống không tự suy diễn hoặc bịa số liệu kế toán.
- Giao diện không báo lưu thành công khi máy chủ lưu thất bại.
- Việc tải file có giới hạn rõ ràng.
- File gốc được lưu với tên an toàn.
- Test không làm thay đổi dữ liệu thật của dự án.

Đăng nhập, phân chia dữ liệu theo doanh nghiệp và OCR chạy trên máy sẽ được thiết kế ở giai đoạn riêng vì đây là những thay đổi lớn.

## Những lỗi hiện tại

- Chức năng xuất Excel vẫn đưa cả hóa đơn `needs_review` và `rejected` vào báo cáo.
- Bộ đọc theo quy tắc lấy số lớn nhất trong tài liệu làm tổng tiền, sau đó tự giả định thuế VAT 10%.
- Nút “Duyệt tất cả” và nút lưu trong cửa sổ kiểm tra có thể hiển thị thành công dù backend lưu thất bại.
- Người dùng có thể tải lên quá nhiều file hoặc file quá lớn.
- Tên file do người dùng cung cấp được dùng trực tiếp khi lưu xuống ổ đĩa.
- Một số test dùng database và thư mục lưu file thật.
- Các test chưa thống nhất kiểu kết quả trả về của `extract_with_heuristics()`.

## Cách sửa đã chọn

Giữ nguyên công nghệ hiện tại gồm FastAPI, SQLite, JavaScript thuần và pytest. Chúng ta chỉ sửa các lỗi ảnh hưởng trực tiếp tới độ chính xác và ổn định, không xây thêm hệ thống tài khoản, hàng đợi xử lý hoặc OCR mới trong lần này.

Các địa chỉ API hiện có sẽ được giữ nguyên để giao diện tiếp tục sử dụng được. Mỗi thay đổi hành vi phải có test chứng minh lỗi trước khi sửa code.

## Sửa phía backend

### Chỉ xuất hóa đơn đã duyệt

Endpoint xuất Excel chỉ chọn bản ghi có trạng thái chính xác là `approved`.

Các trạng thái sau sẽ không được xuất:

- `needs_review` — đang chờ kiểm tra;
- `rejected` — đã từ chối;
- file xử lý lỗi;
- trạng thái không hợp lệ.

Nếu batch chưa có hóa đơn nào được duyệt, API trả lỗi HTTP 400 với thông báo tiếng Việt rõ ràng.

### Không tự suy diễn số liệu kế toán

Bộ đọc theo quy tắc chỉ nhận số tiền khi số đó nằm gần các nhãn kế toán rõ ràng, ví dụ:

- tổng thanh toán;
- tổng cộng;
- tiền trước thuế;
- tiền thuế hoặc VAT;
- các nhãn tiếng Anh tương ứng.

Hệ thống sẽ không còn:

- lấy số lớn nhất trong tài liệu làm tổng tiền;
- tự chia cho `1.1` để đoán tiền trước thuế;
- tự giả định thuế VAT 10%;
- ghi cứng thông tin của một số nhà cung cấp;
- tự tạo một dòng hàng hóa khi tài liệu không có dữ liệu này.

Trường không đọc được sẽ để trống hoặc bằng `0`, đồng thời tạo cảnh báo để người dùng kiểm tra.

Kết quả từ Gemini cũng phải được kiểm tra kiểu dữ liệu và chuẩn hóa theo schema. Giá trị không hợp lệ sẽ được thay bằng giá trị an toàn và kèm cảnh báo.

Hàm `extract_with_heuristics()` sẽ luôn trả về hai phần:

```text
(dữ liệu trích xuất, danh sách cảnh báo)
```

Tất cả code và test sẽ sử dụng cùng một quy ước này.

### Giới hạn file tải lên

API áp dụng các giới hạn:

- tối đa 20 file trong một batch;
- tối đa 20 MiB cho mỗi file;
- hỗ trợ PDF, PNG, JPEG và TIFF;
- phần mở rộng file phải phù hợp với loại nội dung được phép.

File không hợp lệ sẽ tạo một kết quả báo lỗi riêng, không làm hỏng các file hợp lệ trong cùng batch.

Để tránh nạp file quá lớn vào bộ nhớ, backend chỉ đọc tối đa giới hạn cho phép cộng thêm một byte để phát hiện file vượt quá dung lượng.

### Lưu file gốc an toàn

Tên file lưu trên máy gồm mã file do server tạo và phần tên đã được làm sạch. Các thành phần đường dẫn, ký tự điều khiển và ký tự nguy hiểm trong tên do người dùng gửi lên không được phép thay đổi thư mục lưu trữ.

Hàm tạo ứng dụng sẽ nhận được thư mục lưu file tùy chọn. Khi chạy test, hệ thống dùng thư mục tạm thay vì thư mục dữ liệu thật.

Đường dẫn file gốc được lưu cùng bản ghi hóa đơn. Khi tải lại file, hệ thống dùng đúng đường dẫn đã lưu thay vì tìm bằng mẫu tên rộng.

### Một file lỗi không làm hỏng cả batch

Mỗi file luôn tạo ra một kết quả riêng. Nếu lưu file, đọc PDF, gọi Gemini hoặc kiểm tra dữ liệu thất bại, file đó được đánh dấu lỗi và các file còn lại vẫn tiếp tục xử lý.

Bản ghi lỗi giữ lại dung lượng thật nếu backend đã đọc được file. File lỗi không bao giờ được đưa vào Excel.

## Sửa phía giao diện

Mọi thao tác chỉnh sửa và phê duyệt tuân theo quy trình:

1. Giữ bản sao dữ liệu cũ.
2. Gửi yêu cầu cập nhật tới backend.
3. Chỉ hiển thị dữ liệu mới sau khi backend xác nhận thành công.
4. Nếu thất bại, giữ hoặc khôi phục dữ liệu cũ và thông báo lỗi.

Quy tắc này áp dụng cho:

- sửa nhanh một ô;
- duyệt một hóa đơn;
- duyệt tất cả;
- lưu trong cửa sổ kiểm tra chi tiết.

Khi duyệt tất cả, một hóa đơn lỗi không dừng các hóa đơn còn lại. Cuối quá trình, giao diện báo số lượng cập nhật thất bại.

Cơ chế chống chèn mã HTML hiện tại tiếp tục được giữ và có test cho dữ liệu hóa đơn không đáng tin cậy.

## Kế hoạch kiểm thử

Các test cần có:

- Excel chỉ chứa bản ghi `approved`.
- API trả lỗi 400 khi không có hóa đơn nào được duyệt.
- Mã số thuế hoặc số tài khoản lớn không bị hiểu thành tổng tiền.
- Tổng tiền, tiền trước thuế và thuế chỉ được đọc khi có nhãn rõ ràng.
- Không có dữ liệu dòng hàng thì trả danh sách rỗng.
- Dữ liệu Gemini sai kiểu được đưa về giá trị an toàn.
- Trạng thái không hợp lệ bị API từ chối với mã 422.
- File sai loại, quá lớn hoặc vượt số lượng bị từ chối đúng quy tắc.
- Batch gồm một file tốt và một file lỗi vẫn trả kết quả cho cả hai.
- Tên file không thể thoát ra ngoài thư mục lưu trữ.
- Chức năng tải file gốc hoạt động với thư mục test tạm.
- Test API không dùng database hoặc kho file thật.
- Giao diện giữ dữ liệu cũ nếu yêu cầu cập nhật thất bại.

Trước khi tuyên bố hoàn thành, toàn bộ test của ứng dụng hóa đơn và backend cũ phải chạy thành công.

## Cách xử lý lỗi

- Lỗi file do người dùng gửi lên được ghi vào kết quả riêng với thông báo an toàn.
- Chi tiết kỹ thuật đầy đủ được ghi vào log server, không trả stack trace cho trình duyệt.
- Nếu không thể lưu batch vào SQLite, API phải báo lỗi máy chủ, không giả vờ đã lưu thành công.
- Nếu giao diện không đồng bộ được với backend, người dùng phải nhìn thấy lỗi và trạng thái không được chuyển thành `approved`.

## Những việc để dành cho giai đoạn sau

Lần sửa này không bao gồm:

- đăng nhập và phân quyền;
- tách dữ liệu theo doanh nghiệp hoặc workspace;
- OCR chạy cục bộ cho ảnh và PDF scan;
- xử lý nền bằng hàng đợi công việc;
- lưu file trên object storage;
- chính sách tự động xóa hoặc lưu giữ file.

## Điều kiện hoàn thành

- Không có hóa đơn chưa duyệt trong Excel.
- Bộ đọc theo quy tắc không bịa số liệu tài chính.
- Lưu thất bại không thể xuất hiện như đã thành công trên giao diện.
- Số lượng, dung lượng và định dạng upload có giới hạn.
- File gốc luôn nằm trong thư mục lưu trữ được cấu hình.
- Test không làm thay đổi database hoặc kho file thật.
- Toàn bộ test ứng dụng hóa đơn và backend cũ đều chạy thành công, không có test lỗi.
