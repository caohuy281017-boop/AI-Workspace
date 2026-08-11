# Workspace Structure

## Ownership

| Khu vực | Sở hữu | Không được chứa |
|---|---|---|
| `packages/platform-core` | Domain model và port dùng chung | FastAPI, SQLite, Docling, Gemini, OpenAI, openpyxl |
| `packages/platform-adapters` | Adapter cho engine/SDK bên ngoài | Quy tắc nghiệp vụ của một app cụ thể |
| `apps/accounting` | Schema, validation và workflow kế toán | Nghiệp vụ dịch tài liệu hoặc cuộc họp |
| `server` | Composition root và tiến trình HTTP | Logic trích xuất/validation |
| `frontend` | Giao diện và gọi API | Credential nhà cung cấp ở production |

## Thêm app mới

1. Tạo `apps/<app-name>/src/<app_name>_app`.
2. Dùng model/port từ `platform_core`; không sao chép chúng.
3. Nếu cần engine mới, thêm adapter vào `platform-adapters` sau khi cập nhật `REPO_MAP.md`.
4. Tạo application service riêng và để API gọi service đó.
5. Thêm đường dẫn test vào `pytest.ini`.

## Mã legacy

`_legacy/backend` là bản lưu có thể phục hồi của cây `file_first_ai` trùng trước khi tái cấu trúc. Nó không nằm trong Python path, runtime hoặc test mặc định. Chỉ xóa sau khi repository có Git history và đã xác nhận không cần đối chiếu nữa.
