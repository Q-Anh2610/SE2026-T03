# Incremental ingestion W6 — Issue #131

## Trạng thái

Contract/phạm vi đã được Vũ Nguyễn Quỳnh Anh (@Q-Anh2610) xác nhận tại https://github.com/Q-Anh2610/SE2026-T03/issues/131#issuecomment-7013490872 và Lê Thị Linh Chi (@LLC536) xác nhận phía retrieval tại https://github.com/Q-Anh2610/SE2026-T03/issues/131#issuecomment-7012835522.

Áp dụng full-record ingestion cho asset chưa index; giữ guard từ chối cập nhật asset đã có index_version. Không bổ sung PATCH hoặc luồng ghi Qdrant mới trong #131. Xác nhận contract không thay thế nghiệm thu kết quả tests.

Baseline trước thay đổi: develop tại f1c65e8; ingestion unit tests đạt 201 passed in 4.02s, exit code 0.

## Luồng hiện có

- `SourceAdapter.normalize_and_validate()` kiểm tra và chuẩn hóa manifest.
- `run_batch()` xử lý preview và gọi persistence nếu được cấu hình.
- `DatabaseWriter` quản lý transaction riêng cho từng asset.
- `upsert_downloaded_asset()` thêm/cập nhật metadata PostgreSQL; caller quản lý commit/rollback.
- Preview được tái sử dụng từ cache vẫn đi qua persistence.
- Luồng này chưa cập nhật payload Qdrant.

## Định danh

- Asset được nhận diện bằng `asset_id` và cặp `source/source_id`.
- Không đổi source identity của asset đã tồn tại.
- Không dùng cùng source/source_id cho một asset ID khác.
- Xung đột phải được báo lỗi, không ghi đè bản ghi đang có.

## Semantics metadata đề xuất

Đợt kiểm chứng đầu tiên áp dụng full-record ingestion, không phải PATCH.

Source Adapter hiện tạo đủ 18 trường chuẩn. Trường tùy chọn bị bỏ qua và null đều được chuẩn hóa thành null; tags/formats thiếu hoặc null được chuẩn hóa thành danh sách rỗng. Những giá trị này có thể thay thế metadata cũ khi cập nhật.

Vì vậy, caller phải cung cấp đầy đủ metadata muốn giữ trong bản ghi mới. Không tuyên bố trường bị bỏ qua sẽ tự động giữ giá trị cũ.

Nếu cần PATCH phân biệt omitted/null/empty, phải thống nhất contract và giữ thông tin trường được cung cấp trước khi triển khai; không suy ra được sự khác biệt này sau bước chuẩn hóa hiện tại.

## Asset chưa index

- Thêm mới tạo đúng một asset, trạng thái downloaded sau persistence thành công.
- Cập nhật chỉ áp dụng khi định danh khớp và `index_version` là null.
- Chỉ cập nhật các trường trong `METADATA_FIELDS` của repository.
- Không ghi checksum preview vào trường checksum model.
- Giữ các trường model_path/checksum/model_version theo hành vi repository hiện có.
- Không tự gán searchable hoặc index version.
- Asset ngoài batch không thay đổi.

## Asset đã index

Giữ guard hiện có: asset có `index_version` khác null bị từ chối cập nhật tự động. Metadata và versions cũ phải được bảo toàn.

Không bỏ guard để làm test passed. Cập nhật metadata/payload cho asset đã index là phạm vi cần xác nhận riêng với backend và retrieval.

## Chạy lại và lỗi

- Chạy lại cùng input không tạo asset trùng.
- Idempotency được kiểm trên dữ liệu nghiệp vụ và số bản ghi; không yêu cầu `updated_at` bất biến vì repository hiện cập nhật timestamp mỗi lần upsert thành công.
- Cache preview hợp lệ không được làm bỏ qua bước ghi metadata.
- Persistence thất bại phải được ghi failed ở stage persistence, không báo saved.
- Transaction lỗi của một asset phải rollback; kiểm tra hành vi tiếp tục với asset tiếp theo.
- Retry preview có giới hạn theo max_attempts.
- Chưa coi replay batch là cơ chế tự động retry DB hoặc đồng bộ PostgreSQL–Qdrant.

## Kiểm chứng dự kiến

- Thêm mới và chạy lại không trùng.
- Cập nhật metadata đầy đủ cho asset chưa index.
- Phân biệt và kiểm chứng các trường hợp thiếu/null/rỗng theo contract full-record.
- Giữ model fields và asset ngoài batch.
- Từ chối xung đột định danh.
- Từ chối cập nhật asset đã index và giữ nguyên dữ liệu.
- Persistence vẫn chạy khi preview cache hit.
- Persistence thất bại không bị báo thành công.
- PostgreSQL integration tests trên môi trường test cô lập.

Fixtures không dùng benchmark đã khóa. Không tải model hoặc cập nhật index dùng chung.

## Phạm vi đã thống nhất

- Các trường METADATA_FIELDS được cập nhật theo full-record sau validation/normalization.
- Trường tùy chọn thiếu/null được ghi null; tags/formats thiếu/null/rỗng thành []; chuỗi rỗng hợp lệ được ghi theo giá trị chuẩn hóa. Không hiểu trường thiếu là giữ giá trị cũ.
- Giữ model_path, checksum model, model_version, index_version và created_at của bản ghi hiện có.
- Asset mới có ingestion_status=downloaded; cập nhật bản ghi cũ giữ ingestion_status hiện có.
- updated_at có thể thay đổi khi upsert thành công; idempotency không yêu cầu timestamp này bất biến.
- Asset đã index bị từ chối cập nhật và dữ liệu phải giữ nguyên.
- Payload update chưa được hỗ trợ/kiểm chứng tại entrypoint này; các mục chỉ áp dụng cho luồng payload ghi N/A theo phạm vi đã thống nhất.
- PostgreSQL tests không chứng minh đồng bộ DB–Qdrant hoặc asset đã searchable.

## Kết quả kiểm chứng local

- Hai unit tests mới kiểm tra cache hit truyền metadata hiện hành vào persistence và lỗi persistence khi cache hit được báo đúng, không làm dừng asset tiếp theo.
- PostgreSQL integration tests: 8 passed, exit code 0.
- Integration tests bao phủ bảo toàn toàn bộ bản ghi đã index khi bị từ chối; rollback sau lỗi constraint thật và tiếp tục batch; cache hit cập nhật metadata qua DatabaseWriter; full-record omitted/null/empty; giữ model fields và asset ngoài batch; thay đổi preview URL; chạy lại không trùng; từ chối xung đột định danh.
- PostgreSQL dùng database test_issue101; mỗi integration test tạo schema UUID riêng và tự dọn schema sau khi chạy.
- Preview trong tests là fixture. Kiểm tra preview URL/checksum ở tầng persistence không thay thế việc tải và xác minh ảnh mới thật.
- Không gọi mạng, model hoặc Qdrant trong các tests mới.
- Chưa phát hiện lỗi production qua các tests đã chạy; thay đổi hiện tại bổ sung kiểm chứng hành vi hiện có.
- Kết quả local không thay thế CI, review hoặc xác nhận tiếp nhận.