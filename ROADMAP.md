# ROADMAP - AI-04: Semantic Search cho thư viện 3D assets

Phiên bản: 1.0 | Ngày: 08/10/2026 | Nhóm: 5 người | Thời gian: 8 tuần + 2 tuần dự phòng.

Đây là kế hoạch triển khai, không phải xác nhận tính năng đã hoàn thành. Tất cả milestone ban đầu có trạng thái **chưa bắt đầu**. Xác nhận rubric môn học trước khi chốt yêu cầu cuối.

## 1. Mục tiêu và phạm vi

Web tìm asset 3D bằng văn bản hoặc ảnh, dựa trên metadata và ảnh preview. Có filters, chi tiết asset, giải thích dựa trên tín hiệu thực tế, feedback, ingestion theo batch và benchmark tái lập được.

### Bắt buộc

- Text search và image search; top K kết quả là asset duy nhất.
- Filters trên các thuộc tính có dữ liệu: danh mục, định dạng, số mặt, license.
- Asset detail: preview, metadata, nguồn, tác giả/license và liên kết hợp lệ.
- Ingestion: chuẩn hóa, checksum, chống trùng, retry, trạng thái lỗi theo asset.
- Feedback phù hợp/không phù hợp gắn search event và phiên bản cấu hình.
- Keyword baseline, embedding baseline, Recall@K benchmark, dataset card, batch pipeline tests và model/index versioning.
- Môi trường chạy local bằng Docker Compose và hướng dẫn dựng từ máy sạch.

### Ngoài MVP

Không huấn luyện foundation model, sinh mesh, phân tích hình học trực tiếp, làm marketplace/thanh toán/chat. Viewer GLB, multi-view và caption tự động là mở rộng. Không đưa Elasticsearch/Supabase vào chỉ vì nhóm từng dùng ở dự án khác.

## 2. Hướng kỹ thuật

| Thành phần | Định hướng |
|---|---|
| UI | React + TypeScript + Vite; UI tiếng Việt |
| API | Python + FastAPI; OpenAPI là contract thực thi |
| Dữ liệu nghiệp vụ | PostgreSQL; migration có phiên bản |
| Vector | Qdrant; named vectors/payload filters |
| Embedding baseline | `openai/clip-vit-base-patch32` |
| Model cần thử | `google/siglip2-base-patch16-224` |
| Metadata retrieval tùy chọn | `intfloat/multilingual-e5-small` |
| Hợp nhất | RRF; cấu hình ứng viên/trọng số chỉnh trên validation |
| Thực thi batch | CLI/job runner đơn giản; chưa cần Celery/Redis nếu chưa có nhu cầu đo được |
| Chạy và kiểm thử | Docker Compose, pytest, frontend lint/typecheck/build, E2E luồng chính |

**Nguyên tắc chọn model:** CLIP trước để có luồng hoàn chỉnh. Thử SigLIP 2 trên cùng benchmark. E5 + fusion chỉ giữ nếu cải thiện đủ để bù chi phí vận hành. Model cuối là kết quả thí nghiệm, không phải quyết định sẵn rằng model mới hơn luôn tốt hơn.

### Luồng dữ liệu

1. Source adapter → manifest → metadata chuẩn hóa → tải/kiểm tra ảnh.
2. Ghi asset/status PostgreSQL; encoder tạo embedding theo batch.
3. Upsert Qdrant và ghi index version; chỉ asset index thành công được đánh dấu searchable.
4. Query → validation → encoder → retrieval + filters → fusion/deduplication → result + explanation.
5. Feedback lưu cùng query/event, cấu hình retrieval và model/index version.

Metadata nghiệp vụ trong PostgreSQL là nguồn chính. Payload Qdrant phục vụ tìm kiếm; cập nhật/xóa asset phải có đồng bộ và khả năng retry. Không coi thao tác hai hệ lưu trữ là một transaction tự động.

## 3. Dataset và đánh giá

### Dataset chính

Objaverse 1.0 subset: bắt đầu 200 asset, mục tiêu 1.000-3.000 asset kiểm tra được thuộc một miền (nội thất/đồ gia dụng hoặc game props). Không tải toàn bộ dataset. Lọc nguồn/license rõ, preview tải được, metadata hữu ích. Ghi số lượng loại bỏ và lý do.

Nếu dữ liệu không đủ hoặc việc tải không khả thi ở tuần 1, cân nhắc ABO subset cho miền nội thất. Chỉ lấy sản phẩm có model 3D và ghép đúng ID ảnh/model. Ghi quyết định thay đổi trong ADR.

Các trường chuẩn: `asset_id`, `source`, `source_id`, `source_url`, `author`, `license`, `name`, `description`, `tags`, `category`, `thumbnail_path`, `model_path` nếu có, `formats`, `face_count` nếu biết, `checksum`, `ingestion_status`, `model_version`, `index_version`. Thuộc tính thiếu để null. Chuẩn hóa rõ `face_count` dùng đếm mặt hay tam giác; không diễn giải hai cách như nhau.

### Benchmark

- Mục tiêu 80-120 truy vấn: khoảng 60-80 text, 20-40 ảnh; điều chỉnh theo dữ liệu thực tế.
- Text có nhãn nhiều asset liên quan; relevance 0/1/2. Hai người kiểm tra nhãn được phân công.
- Ảnh tách tìm cùng ID và tìm asset tương tự; tránh dùng chính ảnh index làm toàn bộ truy vấn.
- Nhóm truy vấn gần trùng cùng một split; khoảng 40% validation / 60% test.
- Khóa test trước tối ưu. Không dùng test để chọn trọng số/model/threshold.
- Recall@5/10, nDCG@10; Hit@K cho cùng-ID; p50/p95 latency với máy và cách đo ghi rõ.
- Nếu nhãn chưa đầy đủ, công bố Recall theo tập nhãn đã biết và giới hạn việc đánh giá.
- So sánh keyword → CLIP → SigLIP 2 → model thị giác + E5/RRF. Multi-view là thí nghiệm riêng.
- Báo cáo riêng text/ảnh và tiếng Việt/tiếng Anh nếu có. Không bịa score hoặc đặt mục tiêu accuracy không có căn cứ.

## 4. Form thư mục ban đầu

| Đường dẫn | Trách nhiệm | Chủ trì |
|---|---|---|
| `frontend/src/app/` | Router/layout | Nguyễn Văn Duy |
| `frontend/src/features/search/` | Text/image query, filters, results | Nguyễn Văn Duy |
| `frontend/src/features/assets/` | Chi tiết asset | Nguyễn Văn Duy |
| `frontend/src/features/feedback/` | Feedback | Nguyễn Văn Duy |
| `frontend/src/features/admin/` | Job status, lỗi, reindex UI | Đoàn Thị Minh Khuê phối hợp Nguyễn Văn Duy |
| `frontend/src/components/`, `lib/api/`, `types/` | Thành phần/contract chung | Nguyễn Văn Duy + Vũ Nguyễn Quỳnh Anh |
| `frontend/tests/e2e/` | Luồng tích hợp trên web | Đoàn Thị Minh Khuê |
| `backend/app/api/`, `schemas/`, `core/` | API, DTO, cấu hình | Vũ Nguyễn Quỳnh Anh |
| `backend/app/db/`, `services/`, `migrations/` | Nghiệp vụ và persistence | Vũ Nguyễn Quỳnh Anh |
| `backend/app/ingestion/` | Source adapter, download, normalization, pipeline | Trịnh Thị Thu Huyền |
| `backend/app/embedding/` | Model adapter, batch encoding | Lê Thị Linh Chi |
| `backend/app/search/` | Vector store, retrieval, filters, fusion, explanation | Lê Thị Linh Chi |
| `backend/tests/unit/`, `tests/integration/` | Tests module và tích hợp | Chủ module + Đoàn Thị Minh Khuê |
| `evaluation/` | CLI, runner, metrics, configs, results, tests | Đoàn Thị Minh Khuê + Lê Thị Linh Chi |
| `data/manifests/`, `samples/`, `benchmark/` | ID, mẫu nhỏ, query/nhãn | Trịnh Thị Thu Huyền + Đoàn Thị Minh Khuê |
| `data/raw/`, `processed/`, `models/` | Dữ liệu local, không commit bulk | Trịnh Thị Thu Huyền |
| `scripts/`, `.github/` | Setup, smoke tests, CI và templates | Đoàn Thị Minh Khuê + chủ module |
| `docs/`, `docs/adr/` | Tài liệu, quyết định, đóng góp | Cả nhóm |

File gốc: `README.md`, `ROADMAP.md`, `AGENTS.md`, `compose.yaml`, `.env.example`, `.gitignore`. Bản hướng dẫn giao dưới tên `AGENT.md`; đổi tên thành `AGENTS.md` trước khi dùng Codex. Chỉ tạo file/module cần cho Issue hiện tại.

## 5. Phân công và đóng góp thực chất

| Thành viên | Sở hữu đầu ra kỹ thuật | Phối hợp/review |
|---|---|---|
| Vũ Nguyễn Quỳnh Anh | API nghiệp vụ, DB/migrations, điều phối tích hợp | Nguyễn Văn Duy API/UI, Đoàn Thị Minh Khuê release |
| Trịnh Thị Thu Huyền | Pipeline ingestion, dataset snapshot, batch tests | Lê Thị Linh Chi schema/index, Đoàn Thị Minh Khuê chất lượng dữ liệu |
| Lê Thị Linh Chi | Encoder adapters, retrieval, filters, fusion, index versioning | Trịnh Thị Thu Huyền dữ liệu, Đoàn Thị Minh Khuê benchmark |
| Nguyễn Văn Duy | UI tìm kiếm/detail/feedback, API client | Vũ Nguyễn Quỳnh Anh contract, Đoàn Thị Minh Khuê admin/E2E |
| Đoàn Thị Minh Khuê | Evaluation CLI, admin job UI, CI/Docker/E2E | Lê Thị Linh Chi metric, Vũ Nguyễn Quỳnh Anh jobs/release |

Mỗi người đều có code, tests và tài liệu phần mình. Vũ Nguyễn Quỳnh Anh không chỉ quản lý; Đoàn Thị Minh Khuê không chỉ viết báo cáo. Người chủ trì thư mục không có quyền độc quyền sửa.

## 6. Milestones theo tuần

Mỗi nhiệm vụ dưới đây chuyển thành Issue có owner, reviewer, dependencies và acceptance criteria. Chia nhiệm vụ lớn thành PR nhỏ, tích hợp được; không yêu cầu một PR chứa toàn bộ công việc của một tuần.

### W1 / M0 - Chốt phạm vi và kiểm chứng môi trường

- Vũ Nguyễn Quỳnh Anh: SRS/use cases, FastAPI skeleton, asset schema, draft API contract.
- Trịnh Thị Thu Huyền: source reader, 200-ID manifest, kiểm tra metadata/thumbnail/license.
- Lê Thị Linh Chi: CLIP proof of concept trên 20-50 ảnh; đo encoding trên máy thực tế.
- Nguyễn Văn Duy: React skeleton và search UI mock theo contract.
- Đoàn Thị Minh Khuê: CI lint/smoke, Docker khung, evaluation CLI skeleton và kế hoạch nhãn.
- Gate: prototype nhỏ chạy; quy mô dữ liệu khả thi; lựa chọn ngôn ngữ truy vấn được ghi rõ.

### W2 / M1 - Dữ liệu và baseline

- Vũ Nguyễn Quỳnh Anh: migration, list/detail API, error format, pagination.
- Trịnh Thị Thu Huyền: batch download/cleaning, checksum, retry, chống trùng.
- Lê Thị Linh Chi: CLIP batch, Qdrant index và keyword baseline đơn giản.
- Nguyễn Văn Duy: list/detail nối API, filters UI mock.
- Đoàn Thị Minh Khuê: metric CLI bản đầu, tests metric, admin status UI mock và fixtures.
- Gate: 200 asset có trạng thái, chạy lại pipeline không trùng; baseline có kết quả đo thử.

### W3 / M2 - Text search xuyên suốt

- Vũ Nguyễn Quỳnh Anh: API text search gọi search service; search event schema.
- Trịnh Thị Thu Huyền: tăng dữ liệu; batch tests cho ảnh hỏng, thiếu trường, chạy lại.
- Lê Thị Linh Chi: text-to-preview retrieval, filters và index manifest.
- Nguyễn Văn Duy: tìm text thật, loading/empty/error, nguồn asset trên detail.
- Đoàn Thị Minh Khuê: smoke text search, báo cáo baseline, status UI nối API.
- Gate: text search trên web dùng dữ liệu thật; tag `v0.1.0` sau review.

### W4 / M3 - Image search và khóa dữ liệu đánh giá

- Vũ Nguyễn Quỳnh Anh: image upload API, validation kích thước/định dạng, feedback API.
- Trịnh Thị Thu Huyền: dataset snapshot, loại trùng và kiểm tra độ phủ danh mục.
- Lê Thị Linh Chi: image retrieval; adapter SigLIP 2 để so sánh.
- Nguyễn Văn Duy: upload preview, filters thật, feedback UI.
- Đoàn Thị Minh Khuê: image/filter E2E, latency, nhãn và khóa tập test.
- Gate: hai luồng chạy; tập đánh giá/manifest được version hóa.

### W5 / M4 - MVP đầy đủ

- Vũ Nguyễn Quỳnh Anh: explanation response, jobs/reindex API theo runner đã chọn, nghiệp vụ tests.
- Trịnh Thị Thu Huyền: dataset card, cập nhật metadata và đồng bộ payload.
- Lê Thị Linh Chi: E5/RRF thử nghiệm trên validation, dedup theo asset.
- Nguyễn Văn Duy: explanation/feedback hoàn chỉnh, xử lý trạng thái cần thiết.
- Đoàn Thị Minh Khuê: admin job/reindex UI, integration tests, báo cáo so sánh ban đầu.
- Gate: chức năng bắt buộc hoàn chỉnh; tag `v0.5.0`; ngừng thêm tính năng lớn.

### W6 / M5 - Chọn cấu hình và sửa lỗi

- Vũ Nguyễn Quỳnh Anh: sửa API/DB, logging và tác vụ lỗi.
- Trịnh Thị Thu Huyền: dữ liệu gây lỗi, incremental update tests.
- Lê Thị Linh Chi: chọn model/fusion trên validation; ghi ADR và đóng băng cấu hình.
- Nguyễn Văn Duy: sửa UI sau user testing, component tests phù hợp.
- Đoàn Thị Minh Khuê: chạy test benchmark sau khi cấu hình khóa, integration CI, lỗi có bước tái hiện.
- Gate: decision record có chất lượng, latency và chi phí vận hành; báo cáo test không dùng để chỉnh lại cấu hình.

### W7 / M6 - Tái lập và ổn định

- Vũ Nguyễn Quỳnh Anh: API docs, release integration và lỗi ưu tiên.
- Trịnh Thị Thu Huyền: script dataset mẫu, license/attribution, manifest checks.
- Lê Thị Linh Chi: rebuild index, pin revision, search regression.
- Nguyễn Văn Duy: responsive/accessibility cơ bản, tài liệu UI.
- Đoàn Thị Minh Khuê: Docker đầy đủ, dựng trên máy sạch, E2E và hiệu năng.
- Gate: thành viên không phải tác giả dựng hệ thống theo README; benchmark tái lập.

### W8 / M7 - Bản nộp

- Vũ Nguyễn Quỳnh Anh: release PR, SRS/architecture và tổng hợp đóng góp.
- Trịnh Thị Thu Huyền: chốt pipeline/card/tests, demo retry/idempotency.
- Lê Thị Linh Chi: chốt retrieval/model/index và demo hạn chế.
- Nguyễn Văn Duy: chốt UI, demo tìm kiếm/filter/feedback.
- Đoàn Thị Minh Khuê: chốt evaluation/CI, kiểm thử main và hướng dẫn chạy.
- Gate: tag `v1.0.0`; cả 5 demo phần mình; không còn lỗi nghiêm trọng ở luồng chính.

### W9-W10 / M8 - Tùy chọn

Chọn **một** mở rộng sau M7: multi-view retrieval hoặc viewer GLB. Trịnh Thị Thu Huyền data, Lê Thị Linh Chi retrieval, Vũ Nguyễn Quỳnh Anh API, Nguyễn Văn Duy UI, Đoàn Thị Minh Khuê benchmark/E2E. W10 dành sửa lỗi và phát hành. Nếu không đủ thời gian, giữ bản 8 tuần.

## 7. Git và review

- `main`: ổn định; `develop`: tích hợp; cả hai không push trực tiếp.
- Nhánh nhiệm vụ từ `develop`: `feat/<issue>-<task>`, `fix/`, `test/`, `chore/`, `docs/`.
- Chủ nhánh làm code; PR → develop cần một reviewer khác tác giả + CI đạt + comments giải quyết.
- Sau điều kiện đạt, tác giả hoặc người tích hợp merge; ưu tiên squash cho PR nhiệm vụ.
- PR develop → main do Vũ Nguyễn Quỳnh Anh và Đoàn Thị Minh Khuê điều phối; dùng merge commit; người khác review; tạo release tag.
- PR nhỏ thường 1-3 ngày; reviewer phản hồi trong một ngày làm việc; người khác thay nếu vắng.
- Chủ nhánh cập nhật develop và xử lý conflict cùng người sửa vùng liên quan.
- Không force push nhánh chung, không reset lịch sử để bỏ lỗi. Revert bằng PR nếu cần.
- Shared files: dependency/lockfile, migrations, compose, schema/API phải phối hợp owner.
- GitHub protections là cấu hình repo cần thực hiện, không được coi file Markdown đã tự áp dụng.

## 8. Điều phối tải và bằng chứng

Ước lượng 1/2/3/5 points; >5 chia nhỏ. Mục tiêu khoảng 20% tải/người, cân theo thực tế; review/test/documentation được tính. Mỗi tuần: đầu tuần chọn việc, giữa tuần xử lý blocker, cuối tuần demo và cân lại.

Mục tiêu mỗi người có một PR thực chất/tuần và một review hữu ích khi có PR phù hợp. Không đếm commit làm KPI cứng, không tạo commit rỗng. Task dài dùng Draft PR, issue updates và pair work có ghi nhận.

`docs/contributions.md` dùng mẫu:

| Tuần | Thành viên | Issue/PR | Kết quả + kiểm thử | Review/hỗ trợ | Blocker/tải tuần tới |
|---|---|---|---|---|---|
| W1 | Vũ Nguyễn Quỳnh Anh; Trịnh Thị Thu Huyền; Lê Thị Linh Chi; Nguyễn Văn Duy; Đoàn Thị Minh Khuê (mỗi người một dòng) | Link thật | Bằng chứng thật | Link/ghi nhận | Ghi thực tế |

Không đánh dấu milestone hoàn thành nếu chưa có code/test/demo. Codex hỗ trợ kỹ thuật; mỗi người phải hiểu, kiểm tra và trình bày phần mình. Không giả danh người khác trong commit.

## 9. Definition of Done và bàn giao

- Acceptance criteria đạt; tests liên quan chạy; CI phù hợp đạt.
- API/schema/dependency thay đổi có docs và migration cần thiết.
- Không có secret, bulk dataset, cache hoặc model weights trong Git.
- Review xong, merge develop; cập nhật trạng thái bằng bằng chứng.
- README chỉ dẫn lệnh thực sự tồn tại, sample data và cách tạo index.
- Nộp dataset/model card, test plan, evaluation report, version manifest, release tag và đóng góp.

## 10. Bảng theo dõi ban đầu

| Milestone | Tuần | Trạng thái | Bằng chứng |
|---|---|---|---|
| M0 Prototype/contracts | 1 | Chưa bắt đầu | Chưa có |
| M1 Dataset/baseline | 2 | Chưa bắt đầu | Chưa có |
| M2 Text search | 3 | Chưa bắt đầu | Chưa có |
| M3 Image search | 4 | Chưa bắt đầu | Chưa có |
| M4 MVP | 5 | Chưa bắt đầu | Chưa có |
| M5 Model decision | 6 | Chưa bắt đầu | Chưa có |
| M6 Reproducibility | 7 | Chưa bắt đầu | Chưa có |
| M7 Submission | 8 | Chưa bắt đầu | Chưa có |
| M8 Optional extension | 9-10 | Chưa bắt đầu | Chưa có |

## 11. Tài liệu nguồn

- CLIP: https://github.com/openai/CLIP
- SigLIP 2: https://huggingface.co/google/siglip2-base-patch16-224
- E5: https://huggingface.co/intfloat/multilingual-e5-small
- Qdrant fusion: https://qdrant.tech/documentation/search/hybrid-queries/
- Objaverse API: https://objaverse.allenai.org/docs/objaverse-1.0/
- Objaverse dataset/license: https://huggingface.co/datasets/allenai/objaverse
- ABO: https://amazon-berkeley-objects.s3.amazonaws.com/index.html
- Codex instructions: https://developers.openai.com/codex/guides/agents-md
