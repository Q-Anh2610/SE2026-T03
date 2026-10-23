# Tiến độ và điều phối theo tuần

[Kế hoạch tổng thể](../ROADMAP.md). Mỗi tuần ghi kết quả đã làm, phần chuyển tiếp
và kế hoạch bàn giao cho tuần sau; giữ lại báo cáo các tuần trước.

## Tuần 1 / M0 — Tổng kết

Cập nhật ngày 23/10/2026 theo develop tại commit
[8d58397](https://github.com/Q-Anh2610/SE2026-T03/commit/8d5839787057b1e4d7674f618a36d2469ccda540).
Bằng chứng kiểm thử tham khảo trong các PR được dẫn bên dưới.

### Kết quả từng thành viên

| Thành viên | Phần W1 đã hoàn thành | Bằng chứng | Chuyển tiếp sang tuần sau |
|---|---|---|---|
| **TV1 — Vũ Nguyễn Quỳnh Anh** | Hoàn thành SRS/use cases, FastAPI skeleton, health check, cấu hình Docker; ORM và Alembic, seed; API contract, OpenAPI và 5 API mock. | [PR #12](https://github.com/Q-Anh2610/SE2026-T03/pull/12), [PR #23](https://github.com/Q-Anh2610/SE2026-T03/pull/23), [PR #24](https://github.com/Q-Anh2610/SE2026-T03/pull/24). | W2: list/detail đọc PostgreSQL, lỗi và phân trang. Search/feedback thật triển khai theo các tuần sau. |
| **TV2 — Trịnh Thị Thu Huyền** | Đã triển khai Source Adapter, chuẩn hóa 18 trường metadata, kiểm tra và phân loại bản ghi lỗi; có manifest mẫu và unit tests. | [PR #30](https://github.com/Q-Anh2610/SE2026-T03/pull/30), [manifest](../data/manifests/objaverse_200.json). | W2: batch download/cleaning, checksum, retry và chống trùng. Xác nhận lại bản manifest đầy đủ trước khi bàn giao dữ liệu. |
| **TV3 — Lê Thị Linh Chi** | Đã triển khai PoC CLIP trên ảnh online, trích xuất đặc trưng và ghi thời gian chạy mẫu. | [PR #21](https://github.com/Q-Anh2610/SE2026-T03/pull/21), [script PoC](../backend/app/embedding/clip_poc.py). | W2: CLIP batch, Qdrant index và keyword baseline; bổ sung bằng chứng chạy mẫu theo quy mô kế hoạch. |
| **TV4 — Nguyễn Văn Duy** | Hoàn thành React skeleton, UI tìm text mock và các trạng thái giao diện; API client, đối chiếu contract và tests tích hợp/CI. | [PR #18](https://github.com/Q-Anh2610/SE2026-T03/pull/18), [PR #25](https://github.com/Q-Anh2610/SE2026-T03/pull/25). | List/detail W2 đã có ở PR #29; tiếp tục kiểm chứng khi backend chuyển sang PostgreSQL. |
| **TV5 — Đoàn Thị Minh Khuê** | Hoàn thành khung CLI benchmark, adapter gọi Search API, lưu config/provenance và tests; tài liệu gán nhãn, chia tập đánh giá, chọn tiếng Anh cho benchmark chính. | [PR #31](https://github.com/Q-Anh2610/SE2026-T03/pull/31), [PR #27](https://github.com/Q-Anh2610/SE2026-T03/pull/27). | W2: mở rộng metric/tests, admin status UI mock và chuẩn bị đo baseline cùng Chi. |

### Ghi chú bàn giao

- Bản develop đối chiếu có 1 bản ghi trong manifest và 3 URL ảnh trong PoC.
  Nhờ Huyền/Chi xác nhận hoặc bổ sung bản bàn giao/bằng chứng tương ứng với
  mục tiêu W1 là 200 asset và 20–50 ảnh; không cần làm lại phần code đã có.
- API mock và khung evaluation là đầu ra đúng phạm vi W1. Kết nối dữ liệu thật
  và đo baseline là bước phát triển tiếp theo, không tính là thiếu sót của mock.

### Kết quả chung

Nhóm đã tích hợp nền tảng backend/PostgreSQL, API mock, giao diện, Source Adapter,
PoC CLIP và khung evaluation vào develop. Đã có kiểm thử Frontend gọi FastAPI
qua HTTP với dữ liệu mẫu; W2 tập trung nối dữ liệu thật và xây baseline.

## Tuần 2 / M1 — Kế hoạch và phụ thuộc

Trạng thái: **Đề xuất điều phối, chờ các thành viên review**. Dựa trên W2 trong
ROADMAP và code tại commit đối chiếu; không thay đổi phạm vi milestone.
Các phần độc lập có thể làm song song. Cột “Cần chờ” nêu điều kiện tích hợp/đo
thật, không mặc định chặn toàn bộ việc viết code.

| Thành viên | Làm ngay | Cần chờ để tích hợp / kiểm chứng | File hoặc vùng dùng chung cần phối hợp |
|---|---|---|---|
| **TV1 — Quỳnh Anh** | Tái sử dụng migration hiện có; làm list/detail PostgreSQL, lỗi và phân trang bằng DB test. Chỉ thêm migration nếu thật sự đổi schema. | Huyền bàn giao dữ liệu để kiểm chứng ingestion → DB → API; Duy phối hợp thử giao diện với DB. Không cần chờ pipeline để viết API bằng fixture DB. | `backend/app/models/`, `db/`, `core/`, `schemas/`, `alembic/`; `docs/openapi.json`, contract API. |
| **TV2 — Huyền** | Đối chiếu manifest bàn giao; batch download/cleaning, checksum, retry, chống trùng; kiểm chứng nguồn/license/preview. | Quỳnh Anh chốt trước nếu cần đổi schema, cách ghi DB hoặc trạng thái. Bàn giao batch nhỏ đã kiểm tra cho Chi trước khi mở rộng. | Models/migrations, DB session; `data/manifests/`; quy ước `thumbnail_path`, ID và ingestion status. |
| **TV3 — Chi** | Bổ sung bằng chứng PoC theo kế hoạch; CLIP batch, code Qdrant index và keyword baseline bằng mẫu nhỏ. | Dữ liệu/preview sạch, ID và manifest từ Huyền để index/đo thật; chốt model/vector/payload version trước khi tạo index dùng chung. | Metadata/payload schema, manifests; config Qdrant, dependencies và Docker Compose. |
| **TV4 — Duy** | Tái sử dụng list/detail, pagination và filters UI đã merge ở [PR #29](https://github.com/Q-Anh2610/SE2026-T03/pull/29); rà contract và chuẩn bị kiểm chứng DB, không làm lại UI đã có. | Quỳnh Anh bàn giao list/detail PostgreSQL để kiểm chứng luồng dữ liệu thật. Báo lại nếu cần thay đổi response, URL preview hoặc cách xử lý lỗi. | API contract/types, HTTP client; components/layout dùng cùng Khuê. |
| **TV5 — Khuê** | Mở rộng metric CLI và tests bằng ví dụ biết đáp án; admin status UI mock/fixtures; phối hợp Huyền chuẩn bị nhãn theo kế hoạch. | Kết quả baseline từ cùng search implementation của Chi và query/nhãn tương ứng để đo thật. Chốt adapter CLI/service nếu chưa đi qua API; không đẩy API text search W3 vào W2. Admin mock không cần chờ status API thật. | `evaluation/`, `data/benchmark/`; dependencies phát triển, pytest/CI, Docker Compose và UI chung với Duy. |

### Thứ tự bàn giao

1. **Chốt phần nền — Quỳnh Anh + các owner liên quan:** schema/DB session,
   asset ID, metadata null, trạng thái ingestion, đường dẫn preview và contract
   list/detail. Tái sử dụng phần đã có, giải quyết chỗ chưa khớp trước khi nối.
2. **Nhánh dữ liệu — Huyền → Chi → Khuê:** Huyền giao manifest và batch preview
   đã kiểm tra; Chi dùng cùng batch để tạo embeddings/index và baseline; Khuê
   nhận cách gọi baseline, kết quả có version/config và nhãn để chạy đo thử.
3. **Nhánh API/UI — Quỳnh Anh → Duy:** Quỳnh Anh giao API list/detail PostgreSQL,
   ví dụ request/response và cách chạy; Duy kiểm chứng danh sách, detail, phân
   trang và lỗi. Luồng này làm song song với nhánh dữ liệu bằng fixture DB.
4. **Kiểm chứng cuối tuần — cả nhóm:** Huyền và Quỳnh Anh kiểm tra dữ liệu đã
   ghi DB; Duy thử UI với API DB; Chi và Khuê ghi kết quả baseline. Đối chiếu gate
   M1: 200 asset có trạng thái, chạy lại pipeline không trùng và baseline có
   kết quả đo thử. Phần chưa có bằng chứng tiếp tục ghi là tồn đọng.

Khi tổng kết W2, bổ sung một mục mới bên dưới với kết quả từng thành viên,
kết quả chung ngắn gọn và kế hoạch W3; giữ nguyên lịch sử W1 và kế hoạch W2,
ghi chú điều chỉnh nếu có.
