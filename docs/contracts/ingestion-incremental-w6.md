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

## Semantics metadata đã thống nhất

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

## Retry và phục hồi sau lỗi

### Preview

- download_preview_with_retry() giới hạn số lần thử bằng max_attempts; giá trị này bao gồm lần thử đầu tiên, mặc định là 3.
- Chỉ retry lỗi được downloader phân loại là tạm thời; lỗi vĩnh viễn không bị retry.
- Khi hết số lần thử, lưu số attempts và lỗi cuối. Pipeline ghi asset failed tại stage preview, không gọi persistence cho asset đó.
- Cache hợp lệ được tái sử dụng với attempts=0; bước persistence vẫn được thực hiện.

Các tests hiện có trong backend/tests/unit/ingestion/test_downloader.py kiểm chứng:

- test_retry_succeeds_after_temporary_failure
- test_retry_stops_at_limit_and_keeps_last_error
- test_permanent_failure_is_not_retried
- test_http_503_is_retried
- test_invalid_attempt_limit_is_rejected

Những tests này thuộc suite ingestion 203 tests đã chạy đạt; dùng phản hồi mạng giả lập, không phụ thuộc mạng thật.

### PostgreSQL

- DatabaseWriter không có vòng lặp retry DB tự động.
- Mỗi asset được ghi trong transaction riêng. Khi gặp lỗi SQLAlchemy, transaction asset rollback và lỗi được chuyển thành PersistenceError với thông báo an toàn.
- Pipeline ghi status=failed, stage=persistence và database_status=failed; preview thành công hoặc cache hit không được hiểu là DB đã lưu thành công.
- Batch tiếp tục xử lý asset tiếp theo. Integration test tạo lỗi constraint PostgreSQL sau insert và xác nhận insert đó rollback, trong khi asset tiếp theo vẫn được lưu.
- Có thể chạy lại batch sau khi xử lý nguyên nhân lỗi; đây là một lần chạy mới, không phải cơ chế retry DB tự động.
- Không cam kết tái sử dụng preview từ một record có status=failed trong báo cáo trước: loader cache hiện chỉ nhận record downloaded/skipped, nên lần chạy lại có thể tải lại ảnh.
- Không có cơ chế phục hồi hoặc đồng bộ PostgreSQL–Qdrant tại entrypoint này; phần payload được ghi N/A theo phạm vi đã thống nhất.

## Phạm vi kiểm chứng

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

## Môi trường kiểm chứng

- Windows, Git Bash.
- Chạy từ repository root, dùng virtualenv backend/.venv.
- Python 3.13.17 và pytest 9.1.1 theo môi trường local đã kiểm tra.
- PostgreSQL local tại 127.0.0.1:5432; database test_issue101 phải tồn tại trước khi chạy integration tests.
- Tài khoản test cần quyền tạo/dọn schema và chạy migrations trong database test.
- Mỗi integration test dùng schema UUID do isolated_asset_database() tạo và tự dọn sau test. Database test_issue101 được giữ lại.
- Preview là fixture; không cần model weights, Qdrant hoặc mạng để chạy các tests mới.
- Các lệnh bên dưới không cài đặt hoặc nâng cấp dependency.

### Chuẩn bị

```bash
cd /d/SE/SE2026-T03
source backend/.venv/Scripts/activate

python --version
python -m pytest --version
git --version
mkdir -p work
```

Nếu checkout ở vị trí khác, thay lệnh cd bằng repository root tương ứng.

### Unit tests ingestion

```bash
ingestion_test_tmp="$(mktemp -d "$PWD/work/pytest-131-unit-XXXXXX")"

python -m pytest backend/tests/unit/ingestion \
  --basetemp="$(cygpath -w "$ingestion_test_tmp")" \
  --tb=short -q

ingestion_test_exit=$?
echo "Exit code: $ingestion_test_exit"
```

Kết quả local đã ghi nhận: 203 passed, exit code 0. Số tests có thể thay đổi khi tích hợp thêm code; ghi đúng kết quả của commit được kiểm tra.

### Integration tests PostgreSQL

Chạy nguyên khối dưới đây trong Git Bash. Mật khẩu được nhập ẩn; TEST_DATABASE_URL chỉ được truyền vào tiến trình pytest, không ghi vào file hoặc in ra terminal.

```bash
python - <<'PY'
import getpass
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from sqlalchemy import URL, create_engine, text

password = getpass.getpass("PostgreSQL password (hidden): ")
url = URL.create(
    "postgresql+psycopg",
    username="postgres",
    password=password,
    host="127.0.0.1",
    port=5432,
    database="test_issue101",
)

print("Python:", sys.version.split()[0], flush=True)
for package in ("pytest", "SQLAlchemy", "psycopg", "Pillow"):
    print(
        f"{package}: {importlib.metadata.version(package)}",
        flush=True,
    )

engine = create_engine(
    url,
    hide_parameters=True,
    connect_args={"connect_timeout": 5},
)
try:
    with engine.connect() as connection:
        version = connection.scalar(text("SHOW server_version"))
        print("PostgreSQL:", version, flush=True)
finally:
    engine.dispose()

environment = os.environ.copy()
environment["TEST_DATABASE_URL"] = url.render_as_string(
    hide_password=False
)

work = Path("work").resolve()
work.mkdir(exist_ok=True)
temporary = tempfile.mkdtemp(prefix="pytest-131-postgres-", dir=work)
log = work / "issue131-integration-tests.log"

with log.open("w", encoding="utf-8") as output:
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "backend/tests/integration/test_ingestion_incremental.py",
            "--basetemp", temporary,
            "--tb=short", "-v",
        ],
        env=environment,
        stdout=output,
        stderr=subprocess.STDOUT,
        text=True,
    )

print(log.read_text(encoding="utf-8"))
print(f"Exit code: {result.returncode}")
raise SystemExit(result.returncode)
PY
```

Nếu tài khoản hoặc cổng PostgreSQL khác, điều chỉnh cấu hình kết nối trong runner cho môi trường test tương ứng.

Kết quả local đã ghi nhận: 8 passed, exit code 0. Kết quả skipped không được tính là đã kiểm chứng PostgreSQL.

### Đọc kết quả và dọn tài nguyên

- Có lỗi kết nối, migration hoặc test thất bại: giữ log, xử lý nguyên nhân rồi chạy lại; không đổi sang database nghiệp vụ để vượt lỗi.
- Nếu tiến trình kết thúc bình thường, helper tự dọn schema test kể cả khi test thất bại.
- Nếu tiến trình bị kill hoặc máy tắt đột ngột, có thể còn schema tạm; chỉ xử lý sau khi xác định đúng schema do lần chạy đó tạo.
- Log và thư mục pytest nằm trong work/, không đưa vào Git. Không xóa database hoặc schema dùng chung.
- CI và review được xác nhận riêng trên head PR; kết quả local không thay thế các bước này.