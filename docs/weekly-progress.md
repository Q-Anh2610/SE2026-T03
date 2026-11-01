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

## Tuần 2 / M1 — Tổng kết và phần chuyển tiếp

Cập nhật ngày 30/10/2026 theo develop tại commit
[a501105](https://github.com/Q-Anh2610/SE2026-T03/commit/a501105).
Các kết quả dưới đây dựa trên PR, tài liệu và bình luận bàn giao; không phải
một lần chạy lại toàn bộ kiểm thử. Giữ nguyên kế hoạch W2 ở trên để đối chiếu.

### Kết quả từng thành viên

| Thành viên | Phần W2 đã hoàn thành | Bằng chứng | Chuyển tiếp |
|---|---|---|---|
| **TV1 — Vũ Nguyễn Quỳnh Anh** | Hoàn thành list/detail PostgreSQL, filters, phân trang và lỗi 400/404/500; kiểm chứng migration, seed chạy lại và ingestion → DB → API. Có 324 tests backend và 6 tests UI DB đạt theo báo cáo PR. | [PR #50](https://github.com/Q-Anh2610/SE2026-T03/pull/50), [PR #51](https://github.com/Q-Anh2610/SE2026-T03/pull/51), [PR #55](https://github.com/Q-Anh2610/SE2026-T03/pull/55), [hướng dẫn kiểm chứng](guides/asset-api-verification.md). | W3: nối text search với search service thật và hoàn thiện search event. |
| **TV2 — Trịnh Thị Thu Huyền** | Hoàn thành batch download/cleaning, checksum, retry, chống trùng và persistence; báo cáo 200 asset có trạng thái downloaded, chạy lại không trùng. Chi đã xác nhận nhận đủ 200 preview, checksum khớp và dùng được cho embedding. | [PR #52](https://github.com/Q-Anh2610/SE2026-T03/pull/52), [xác nhận tiếp nhận #41](https://github.com/Q-Anh2610/SE2026-T03/issues/41#issuecomment-6503152160). | Rà soát subset nội thất theo #58 để bàn giao benchmark; W3 tăng dữ liệu và bổ sung batch tests. |
| **TV3 — Lê Thị Linh Chi** | Hoàn thành CLIP batch, Qdrant store và keyword baseline. Đã kiểm chứng 200/200 asset thật tạo embedding/index thành công, 0 lỗi; chạy lại vẫn 200 point, tập ID không đổi và không trùng asset. Có script, cấu hình và bằng chứng chia sẻ; PR đã merge. | [PR #53](https://github.com/Q-Anh2610/SE2026-T03/pull/53), [PR #57](https://github.com/Q-Anh2610/SE2026-T03/pull/57), [bằng chứng 200 asset](evidence/issue39-real-assets.json). | Phối hợp Khuê đo baseline; W3 làm text-to-preview retrieval, filters và index manifest. |
| **TV4 — Nguyễn Văn Duy** | Hoàn thành list/detail nối API, phân trang và filters UI. Luồng UI gọi API PostgreSQL có kiểm thử tự động desktop/mobile trong PR #55. | [PR #29](https://github.com/Q-Anh2610/SE2026-T03/pull/29), [PR #55](https://github.com/Q-Anh2610/SE2026-T03/pull/55). | W3: text search thật và nguồn asset trên detail; đã có Draft PR #56 cho UI/tests, còn chờ API/index thật để nghiệm thu. |
| **TV5 — Đoàn Thị Minh Khuê** | Hoàn thành metric CLI Recall/Hit/nDCG, tests metric và admin status UI mock/fixtures. | [PR #43](https://github.com/Q-Anh2610/SE2026-T03/pull/43), [PR #45](https://github.com/Q-Anh2610/SE2026-T03/pull/45). | Còn query/nhãn và lần đo baseline ở #46; tiếp tục song song với W3, phối hợp Huyền/Chi trước khi chốt tập đo. |

### Kết quả chung và phần còn chờ

Đã tích hợp API/UI list/detail PostgreSQL, pipeline ingestion và CLIP/Qdrant
trên bộ 200 asset thật; có bằng chứng chạy lại không trùng ở cả ingestion và
index. Search/feedback HTTP vẫn mock; tìm text xuyên suốt là mục tiêu W3.

**M1 chưa chốt hoàn tất:** [Issue #46](https://github.com/Q-Anh2610/SE2026-T03/issues/46)
còn query/nhãn và kết quả đo thử baseline. Nhóm đã chốt benchmark chỉ gồm
asset nội thất; [Issue #58](https://github.com/Q-Anh2610/SE2026-T03/issues/58)
rà soát và tạo snapshot riêng, giữ nguyên snapshot W1 để truy vết. Huyền bàn
giao danh sách mới cho Khuê trước khi gán nhãn; Chi đối chiếu/rebuild index nếu
snapshot thay đổi. Kết quả index 200 asset cũ xác nhận kỹ thuật, chưa xác nhận
bộ đó hoàn toàn thuộc miền nội thất hoặc có chất lượng retrieval đạt yêu cầu.

## Tuần 3 / M2 — Kế hoạch và phụ thuộc

Mục tiêu theo ROADMAP: text search trên web dùng dữ liệu/index thật.
Bắt đầu các phần độc lập song song; phần benchmark W2 tiếp tục được theo dõi
ở #46/#58, không coi là đã hoàn thành khi chuyển sang W3.

### Công việc từng thành viên

| Thành viên | Làm ngay | Cần chờ để tích hợp / kiểm chứng | File hoặc vùng dùng chung cần phối hợp |
|---|---|---|---|
| **TV1 — Quỳnh Anh** | Rà search event schema hiện có; chốt contract với Chi/Duy, triển khai API text search gọi search service. Chỉ thêm migration khi schema thật sự thay đổi. | Chi bàn giao retrieval thật và index/config tương thích để nối API; cùng Duy/Khuê kiểm chứng HTTP và UI. | `backend/app/api/`, `services/`, `schemas/`, `models/`, `db/`, `alembic/`; `docs/openapi.json`, contract và frontend types. |
| **TV2 — Huyền** | Ưu tiên curate subset nội thất #58, bàn giao snapshot có version; tăng dữ liệu và tests ảnh hỏng, thiếu trường, chạy lại. | Đồng bộ ID/snapshot với Chi và Khuê trước khi index/gán nhãn; phối hợp Quỳnh Anh nếu đổi persistence hoặc trạng thái. | `backend/app/ingestion/`, `data/manifests/`, `data/benchmark/`; metadata, checksum, DB status và đường dẫn preview. |
| **TV3 — Chi** | Tái sử dụng CLIP/Qdrant W2; làm text-to-preview retrieval, filters, kết quả không trùng asset và index manifest. Bàn giao cách gọi baseline cho Khuê. | Dùng snapshot/ID đã đối chiếu với Huyền; thống nhất input/output, model/index/config và lỗi readiness với Quỳnh Anh. | `backend/app/embedding/`, `search/`; payload/filter schema, config Qdrant, manifest và contract search. |
| **TV4 — Duy** | Tiếp tục #54 và Draft PR #56: UI text search, loading/empty/error/retry và nguồn asset trên detail; tái sử dụng list/detail W2. | API text search và index thật sẵn sàng, ID search khớp detail để nghiệm thu. Tests mock hiện có chưa thay cho smoke thật. | `frontend/src/features/search/`, `assets/`, API client/types; contract và components chung với Khuê. |
| **TV5 — Khuê** | Tiếp tục #46 cùng Huyền/Chi; chuẩn bị smoke text search, báo cáo baseline và phần status UI nối API theo ROADMAP. | Chờ snapshot benchmark đã rà soát và retrieval thật để đo; chờ API/index để smoke UI. Status UI chỉ nối khi có contract và nguồn trạng thái thật được bàn giao. | `evaluation/`, `data/benchmark/`, frontend admin/E2E, CI/Compose; contract status và search. |

### Thứ tự bàn giao

1. **Chốt contract — Quỳnh Anh + Chi + Duy:** thống nhất request/response,
   filters, phân trang/giới hạn kết quả, event ID, versions và lỗi khi index
   chưa sẵn sàng. Tận dụng schema hiện có; ghi rõ thay đổi cần thiết.
2. **Dữ liệu/index — Huyền → Chi:** bàn giao snapshot/ID/preview có version;
   Chi tạo hoặc đối chiếu index tương thích, bàn giao manifest và cách chạy.
   Có thể phát triển retrieval trên bộ W2 trong lúc curate, nhưng không trộn
   kết quả của các snapshot hoặc coi bộ cũ là benchmark nội thất đã duyệt.
3. **Search API/UI — Chi → Quỳnh Anh → Duy:** retrieval thật → HTTP text search
   và search event → giao diện. Duy chuẩn bị UI/tests song song; nghiệm thu thật
   sau khi API/index sẵn sàng. Search và detail cần cùng hệ asset ID.
4. **Benchmark — Huyền + Chi → Khuê:** đồng bộ snapshot nội thất trước khi gán
   nhãn; dùng cùng implementation của sản phẩm để đo, lưu query/nhãn, kết quả
   và cấu hình. Cập nhật #46 để chốt phần W2 còn chờ.
5. **Status và smoke — Quỳnh Anh + Huyền/Chi → Khuê, phối hợp Duy:** chốt nguồn
   trạng thái/contract trước khi nối admin UI; không coi fixture là trạng thái
   job thật. Cả nhóm kiểm chứng tìm text trên web với API/index thật, lỗi và
   metadata nguồn; ghi bằng chứng trước khi đề nghị release `v0.1.0` sau review.

Khi tổng kết W3, bổ sung kết quả từng thành viên, phần chuyển tiếp và kế hoạch
W4 bên dưới; giữ lại lịch sử các tuần. Cập nhật riêng phần còn chờ của W2 khi
có bằng chứng hoàn thành, không tự đánh dấu cả M1/M2 đã đạt.
