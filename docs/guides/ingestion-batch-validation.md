# Kiểm chứng batch ingestion

## Phạm vi

Người thực hiện: Trịnh Thị Thu Huyền (@TrinhHuyen05).

Issue: https://github.com/Q-Anh2610/SE2026-T03/issues/62

Bổ sung kiểm thử điều phối pipeline khi cache không hợp lệ hoặc batch chứa preview lỗi. Chưa thay đổi code ingestion.

## Các trường hợp bổ sung

### Phục hồi cache

File: `backend/tests/unit/ingestion/test_pipeline_cache_recovery.py`

- File ảnh cache bị mất.
- File cache bị thay bằng ảnh khác có checksum không khớp.
- File cache bị thay bằng nội dung không phải ảnh.

Pipeline chỉ tải lại preview không hợp lệ, giữ cache hợp lệ, kiểm tra checksum kết quả và không sửa manifest nguồn.

### Preview lỗi trong batch

File: `backend/tests/unit/ingestion/test_pipeline_invalid_previews.py`

- Phản hồi rỗng.
- Phản hồi là HTML.
- Phản hồi chứa dữ liệu không phải ảnh.

Pipeline ghi nhận asset lỗi, tiếp tục xử lý asset hợp lệ phía sau, xuất summary đúng và không để lại file `.part`.

## Cách chạy bằng Git Bash

Chạy từ gốc repository:

```bash
mkdir -p work
test_tmp=$(mktemp -d "$PWD/work/pytest-ingestion-XXXXXX")
./backend/.venv/Scripts/python.exe -m pytest backend/tests/unit/ingestion -q -p no:cacheprovider --basetemp="$test_tmp"
```

Sử dụng thư mục tạm riêng để tránh lỗi quyền truy cập thư mục pytest mặc định trên máy Windows.

## Kết quả local

Ngày kiểm chứng: 01/11/2026.

- Trước bổ sung: 138 passed.
- File kiểm tra phục hồi cache: 3 passed.
- File kiểm tra preview lỗi: 3 passed.
- Toàn bộ unit tests ingestion sau bổ sung: 144 passed in 0.74s.

Kết quả được chạy trên máy local của Trịnh Thị Thu Huyền (@TrinhHuyen05), nhánh `feat/62-ingestion-batch-validation`, dựa trên develop tại commit `a501105`.

## Giới hạn

- Phản hồi mạng được giả lập; ảnh fixture được tạo trong thư mục tạm.
- Pipeline, cache validation và downloader sử dụng implementation hiện có.
- Không gọi Internet, PostgreSQL hoặc Qdrant trong các tests bổ sung.
- Kết quả này không chứng minh dữ liệu thật đã tải, DB thật không trùng hoặc index đã được rebuild.
- Chưa nghiệm thu phần mở rộng dataset, bàn giao hoặc toàn bộ Issue #62.
- Kết quả local không thay thế trạng thái CI, review hoặc approval.

## Regression tests cho snapshot mở rộng

File: `backend/tests/unit/ingestion/test_interior_snapshot.py`.

Bổ sung bốn tests offline:

- Metadata 354 khớp annotations nguồn và được SourceAdapter chấp nhận.
- Giữ nguyên metadata của 200 asset mốc, bổ sung đúng 154 asset duy nhất.
- Checksum manifest/annotations và thông tin preview nhất quán với provenance.
- Curation khớp preview, chỉ giữ quyết định keep và dùng đường dẫn portable.

Kết quả do Trịnh Thị Thu Huyền (@TrinhHuyen05) chạy trên local:

- File regression snapshot: 4 passed.
- Toàn bộ unit tests ingestion sau bổ sung: 148 passed.

Các tests mới chỉ đọc metadata trong repository; không gọi Internet,
PostgreSQL, Qdrant hoặc nạp model. Chúng không decode ảnh local và không
thay thế bằng chứng kiểm tra ảnh thật, tiếp nhận bàn giao hoặc tích hợp search.
