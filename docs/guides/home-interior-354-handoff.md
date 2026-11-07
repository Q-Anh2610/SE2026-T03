# Snapshot nội thất 354 và bàn giao — Issue #62

Người thực hiện: Trịnh Thị Thu Huyền (@TrinhHuyen05).

Issue: https://github.com/Q-Anh2610/SE2026-T03/issues/62

## Phiên bản và phạm vi

- Snapshot mở rộng: `home-interior-354-v1`.
- Thành phần: 200 asset mốc + 154 asset bổ sung.
- Bộ mốc `home-interior-clear-200-v3` được giữ nguyên.
- Không thay cấu hình dataset mặc định hoặc dữ liệu benchmark của Issue #46.
- Preview là ảnh đại diện; gói không chứa mesh GLB.

Manifest SHA-256 của bộ 354:

`93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614`

Manifest SHA-256 của bộ mốc 200:

`9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`

## Metadata trong repository

Thư mục: `data/manifests/home-interior-354-v1/`.

| File | Nội dung |
|---|---|
| `assets_354.json` | 354 bản ghi chuẩn hóa theo source adapter |
| `assets_354.annotations.json` | Annotations gốc |
| `assets_354.provenance.json` | Revision nguồn, checksum và thông tin preview |
| `assets_354.curation.json` | Quyết định giữ ảnh, phân loại và ghi chú duyệt ảnh |

Metadata nguồn được giữ nguyên; phân loại sau duyệt nằm riêng trong curation.
Không suy đoán hoặc thay thế author, license, formats hay face_count.

Revision nguồn Objaverse:

`556637099bf4fa79ea7b239d0d9c328b8a2e9ac8`

## Lựa chọn và kiểm tra dữ liệu

Các đợt bổ sung có tổng cộng:

- 379 ứng viên.
- 355 preview tải được và đã được AI kiểm tra trực quan.
- 24 trường hợp tải thất bại.
- Giữ 154, loại 140, uncertain 61.
- Các trường hợp uncertain không nằm trong tập chính.

Ưu tiên nội thất và thiết bị trong nhà dễ nhận ra, kiểu dáng hiện đại.
Không tuyên bố toàn bộ ảnh đã được một thành viên khác kiểm duyệt độc lập.

Bộ 354 đã được kiểm tra:

- Asset ID duy nhất: 354.
- Cặp source/source_id duy nhất: 354.
- Preview đọc được: 354.
- Checksum preview duy nhất: 354.
- Manifest và annotations khớp provenance.
- Metadata chuẩn hóa khớp annotations qua source adapter.

Checksum ảnh khác nhau không chứng minh các mesh khác nhau hoàn toàn.

## Bằng chứng local

### Ingestion và PostgreSQL

- Unit tests ingestion: 144 passed.
- Sáu trường hợp bổ sung kiểm tra cache mất/hỏng/sai checksum và preview lỗi.
- Database local `semantic_search_interior354` có 354 asset.
- Tất cả ở trạng thái `downloaded`.
- Nhập lại vẫn có 354 bản ghi, không phát sinh trùng.
- API danh sách tại cổng 8001 đã trả đủ 354 ID, khớp manifest, `mock: false`.

Tests dùng fixture không thay thế kiểm chứng ảnh và database thật.

### Embedding và Qdrant — kiểm chứng ngày 04/11/2026

- CLIP: `openai/clip-vit-base-patch32`.
- Model revision: `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`.
- Preprocessing: `clip-slow-processor-rgb-l2-v1`.
- Device: CPU; batch size: 8.
- 354 embedding thành công, 0 failed, 0 skipped.
- Vector 512 chiều, chuẩn hóa L2; similarity cosine.
- Qdrant persistent local mode.
- Collection riêng: `interior354_clip_local_v1`.
- Index version: `interior354-clip-local-v1`.
- Số point: 0 → 354 → 354 sau hai lần upsert.
- Đã đối chiếu UUID ổn định, payload, cấu hình và vector.
- Lần upsert thứ hai dùng lại cùng embedding, không phải inference lần hai.
- Smoke truy vấn ảnh và ba câu tiếng Anh chạy thành công.

Đây là smoke ở cấp module, không phải benchmark chất lượng, kiểm chứng
tiếng Việt hoặc kiểm chứng HTTP Search API/frontend.

## Gói bàn giao

Tên gói:

- `home-interior-354-v1.zip`
- `home-interior-354-v1.zip.sha256`

Gói chứa metadata, preview, ready manifest, báo cáo và `SHA256SUMS`.
Ảnh, ZIP, model weights, cache và dữ liệu Qdrant chỉ lưu local.

Sau khi giải nén, đường dẫn ảnh trong ready manifest, provenance và curation
được tính từ thư mục gốc của gói `home-interior-354-v1`, không phải thư mục
`data/manifests/home-interior-354-v1` trong repository.

Người nhận cần kiểm tra checksum ZIP trước khi giải nén, rồi đối chiếu
354 asset ID và checksum từng ảnh trước khi sử dụng.

## Trạng thái bàn giao

Theo xác nhận của Trịnh Thị Thu Huyền (@TrinhHuyen05), gói 354 đã được
gửi qua email cho Lê Thị Linh Chi (@LLC536).

- [x] Chuẩn bị gói và kiểm tra nội dung ZIP.
- [x] Đã gửi gói qua email theo xác nhận của người gửi.
- [ ] Chờ Lê Thị Linh Chi (@LLC536) xác nhận tải được và checksum khớp.
- [ ] Chờ xác nhận nhận đủ 354 asset và đường dẫn preview hợp lệ.
- [ ] Chờ xác nhận đầu vào phù hợp cho index và filters.
- [ ] Chờ xác nhận đồng bộ snapshot đánh giá với Đoàn Thị Minh Khuê (@doanminhkhue25).

Việc đã gửi không đồng nghĩa người nhận đã kiểm tra hoặc tích hợp thành công.

## Giới hạn và phần chờ tích hợp

- Chưa chạy Qdrant server/Docker cho bộ 354.
- Chưa nối collection 354 vào HTTP Search API/frontend.
- Chưa đổi `.env` hoặc đánh dấu `searchable` trong PostgreSQL.
- Chưa thay thế bộ 200 dùng cho benchmark.
- Chưa tuyên bố CI, review, PR hoặc toàn bộ W3/M2 hoàn thành.

Phối hợp Lê Thị Linh Chi (@LLC536) về index/search,
Vũ Nguyễn Quỳnh Anh (@Q-Anh2610) về API/persistence và
Đoàn Thị Minh Khuê (@doanminhkhue25) về evaluation.

## Chạy unit tests bằng Git Bash

Từ gốc repository:

```bash
mkdir -p work
test_tmp=$(mktemp -d "$PWD/work/pytest-ingestion-XXXXXX")
./backend/.venv/Scripts/python.exe -m pytest backend/tests/unit/ingestion -q -p no:cacheprovider --basetemp="$test_tmp"
```

Hướng dẫn các trường hợp kiểm thử:
`docs/guides/ingestion-batch-validation.md`.

## Kiểm chứng bổ sung W4 — Issue #92

- [Báo cáo tổng hợp](../reports/issue92/audit.md).
- [Độ phủ danh mục và cách tái lập](../reports/issue92/category-coverage.md).
- [Rà nghi trùng bằng AI và giới hạn](../reports/issue92/visual-review.md).

Snapshot giữ nguyên 354 asset. Cặp nghi trùng còn uncertain
và các xác nhận từ retrieval, PostgreSQL, evaluation tiếp tục
được theo dõi; chưa coi Issue #92 hoàn tất chỉ từ báo cáo.
