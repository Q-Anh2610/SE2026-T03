# AGENTS.md - Luật chung Codex và Claude cho AI-04

`AGENTS.md` là nguồn luật chung; `CLAUDE.md` nạp file này và `CONTRIBUTING.md`, không duy trì một bộ luật sao chép độc lập hoặc import ngược.

## 0. Đồng bộ luật

- Codex và Claude cùng tuân thủ các quy tắc phạm vi, Git, kiểm thử và bảo mật dưới đây; chi tiết riêng công cụ chỉ áp dụng cho công cụ tương ứng.
- Khi sửa luật chung, kiểm tra cả `AGENTS.md` lẫn `CLAUDE.md` và giữ `CONTRIBUTING.md`, `docs/BRANCHING.md`, PR template nhất quán. Chỉ sửa file có nội dung/tham chiếu bị ảnh hưởng, không tạo diff vô nghĩa.
- Bàn giao luật bằng đường dẫn và SHA hoặc diff local; agent đang chạy phải đọc lại trước phần việc phụ thuộc. Quy tắc này không tự cấp quyền spawn agent, commit/push, approve hoặc merge.

## 1. Mục tiêu và cách làm việc

Bạn hỗ trợ nhóm 5 người xây Semantic Search cho thư viện 3D assets trong 8-10 tuần. Đọc `ROADMAP.md`, README, tài liệu contract và hướng dẫn trong thư mục liên quan trước khi sửa. Hướng dẫn này áp dụng trong repository; không thay thế chỉ dẫn hệ thống, quyền môi trường hoặc yêu cầu trực tiếp của người dùng.

Thực hiện **Issue/milestone được giao**, không tự xây cả dự án trong một lượt. Tiến hành các quyết định triển khai nhỏ và sửa lỗi trong phạm vi được giao; hỏi khi thiếu yêu cầu quyết định contract/phạm vi hoặc cần thay đổi lớn. Không tạo luồng xin phép cho mọi sửa đổi nhỏ.

Giao tiếp, báo cáo và tài liệu người dùng bằng tiếng Việt; tên mã/identifier bằng tiếng Anh. Không tự điều phối thêm agent hay sửa module của người khác ngoài phạm vi cần thiết. Nếu cần mở rộng phạm vi, nêu lý do và ảnh hưởng.

## 2. Kiểm tra trước khi bắt đầu

1. Đọc `git status --short`, nhánh hiện tại và diff liên quan. Tôn trọng thay đổi chưa commit của người khác.
2. Xác định Issue, người phụ trách trong bảng phân công ở mục 4, acceptance criteria và vùng file.
3. Đọc implementation hiện có trước khi thêm abstraction/dependency.
4. Kiểm tra manifest/script/lockfile để biết lệnh và môi trường thực tế.
5. Repo mới: chỉ scaffold phần được giao; không tạo module rỗng để trông đầy đủ.
6. Nếu owner/Issue chưa nêu, làm phần rõ ràng trong yêu cầu; không bịa danh tính, số Issue, tiến độ hay liên kết PR.

## 3. Kiến trúc và scope

- Frontend: React + TypeScript + Vite.
- Backend: Python + FastAPI; PostgreSQL + migrations.
- Vector database: Qdrant.
- Baseline: `openai/clip-vit-base-patch32`.
- Thử nghiệm sau baseline: `google/siglip2-base-patch16-224`, E5 `intfloat/multilingual-e5-small`, RRF.
- Dataset: Objaverse subset; ABO là phương án thay có ADR.
- Batch runner đơn giản trước; không thêm Redis/Celery/Kubernetes/microservices nếu chưa được yêu cầu hoặc có căn cứ rõ.
- Không tự đổi sang Elasticsearch/Supabase, thêm LLM trả phí hoặc dịch vụ cloud.
- Không sinh 3D, huấn luyện từ đầu, làm payment/chat/marketplace trong MVP.

Không đổi stack, nguồn dataset, default model hay cấu trúc repo lớn chỉ để hợp sở thích. Với thay đổi quan trọng, trình bày dữ liệu đo/tradeoff và ghi `docs/adr/` sau khi lựa chọn được chốt.

## 4. Ranh giới module và phối hợp

| Vùng | Chủ trì | Quy tắc |
|---|---|---|
| `backend/app/api/`, `schemas/`, `core/`, `db/`, `services/`, `backend/migrations/` | Vũ Nguyễn Quỳnh Anh | Contract, nghiệp vụ, persistence |
| `backend/app/ingestion/`, `data/manifests/` | Trịnh Thị Thu Huyền | Source/download/normalize/retry/dedup |
| `backend/app/embedding/`, `search/` | Lê Thị Linh Chi | Encoders, Qdrant, filters, retrieval/fusion |
| `frontend/src/features/search/`, `assets/`, `feedback/`, UI chung | Nguyễn Văn Duy | UI và API client |
| `evaluation/`, admin UI, E2E, CI/Docker | Đoàn Thị Minh Khuê | Tooling, metric, vận hành/tích hợp |
| `docs/`, module tests | Cả nhóm | Cập nhật phần thực sự thay đổi |

Owner là người phối hợp/review, không phải ACL. Hạn chế diff ngoài module được giao. Shared contracts, migrations, lockfiles, compose và components chung cần ghi ảnh hưởng cho owner review.

### Dependency boundaries

- UI → HTTP API, không truy cập PostgreSQL/Qdrant trực tiếp.
- API router mỏng: validation/DTO rồi gọi nghiệp vụ; không chứa toàn bộ pipeline.
- Ingestion sử dụng encoder chung; không nhân đôi code nạp model.
- Search gọi vector store abstraction đơn giản, áp dụng filters và gom asset.
- Evaluation dùng cùng search implementation/API của sản phẩm, không làm thuật toán khác rồi gắn tên sản phẩm.
- Không thêm abstraction nhiều tầng nếu một module/hàm rõ ràng là đủ.

## 5. Contract API và dữ liệu

Giữ OpenAPI, schema backend và kiểu frontend nhất quán. Tái sử dụng contract hiện có. Chưa có contract: đề xuất request/response tối thiểu cho nhiệm vụ, ghi tài liệu và mock tương ứng trước khi hai phía triển khai.

Các route gợi ý, **chưa phải endpoint đã có**:

- `GET /api/v1/assets`, `GET /api/v1/assets/{asset_id}`.
- `POST /api/v1/search/text`: query, filters, limit.
- `POST /api/v1/search/image`: multipart image và trường filters/limit có quy ước rõ.
- `POST /api/v1/feedback`: search_event_id, asset_id, relevance.
- Jobs/status/reindex: chỉ tạo khi milestone yêu cầu; giới hạn truy cập quản trị.

Response search gồm query/event ID, asset metadata, rank, nguồn truy xuất/explanation và index/model/config version cần thiết. Score nếu hiển thị phải mô tả đúng nghĩa, không gọi là phần trăm chính xác.

Không ghi bí mật vào logs. Validate ảnh theo nội dung decode được, không chỉ đuôi file; giới hạn kích thước/dimensions và xử lý ảnh hỏng. Validate filters/limit. Không thực hiện tải URL tùy ý do người dùng gửi trong search MVP; ingestion dùng source adapter kiểm soát được.

## 6. Embedding, retrieval và versioning

- Dùng processor/tokenizer đúng checkpoint; pin revision và dependencies khi chốt thí nghiệm.
- Nạp model một lần mỗi service/process; inference mode; batch asset trước.
- Chỉ so vector tương thích trong cùng model/không gian; không so/cộng E5 với vector ảnh SigLIP/CLIP.
- Chuẩn hóa vector và cấu hình similarity nhất quán; ghi preprocessing trong manifest.
- E5: query có `query: `; metadata có `passage: `.
- Text → preview qua multimodal encoder; text → metadata qua E5 khi được bật.
- Image → preview; text phụ nếu có chạy luồng riêng.
- Fusion theo rank/RRF trước; không cộng cosine từ nhiều model nếu chưa hiệu chỉnh và đo.
- Cùng filters cho các luồng; kết quả top K là asset duy nhất.
- Multi-view chỉ khi được giao; nhóm theo asset ID, không để nhiều view chiếm nhiều kết quả.
- Thuộc tính định dạng/license/face_count là filter metadata; không đoán từ ảnh.
- Đổi model/preprocessing cần index mới hoặc rebuild rõ ràng; không trộn embedding cũ/mới.
- Lưu checkpoint/revision, dimension, preprocessing, dataset snapshot và index version.
- Không tuyên bố model tối ưu/tiếng Việt tốt khi chưa có benchmark.

## 7. Ingestion và lưu trữ

- Giữ metadata gốc và normalized record có provenance/license.
- Asset ID ổn định, checksum, trạng thái lỗi, retry có giới hạn và idempotent upsert.
- Lỗi một asset không làm mất cả batch; có summary thành công/thất bại/bỏ qua.
- Thiếu thuộc tính để null; không bịa số mặt, caption gốc hoặc license.
- PostgreSQL là nguồn metadata nghiệp vụ; Qdrant payload cần đồng bộ/reconciliation.
- Không đánh dấu searchable trước khi upsert index thành công. Delete/update có test cần thiết.
- Thumbnail nhiều độ phân giải không coi là nhiều góc render.
- Chỉ tải subset phù hợp. Không tự tải toàn bộ dataset/model lớn hay ghi đè index dùng chung.
- Caption sinh thêm phải ghi nguồn/model, tách khỏi metadata gốc; không dùng để tạo ground truth tự động.

## 8. Git và công việc song song

- Làm trên feature branch đã được giao; không tự chuyển nhánh khi working tree chứa thay đổi của người khác.
- Nếu cần nhánh mới và tree sạch: từ develop hiện có, đặt `feat/<issue>-<task>` hoặc fix/test/chore/docs. Không bịa Issue ID.
- Không push trực tiếp main/develop; không force push, reset --hard, clean -fd hoặc xóa thay đổi người khác.
- Chỉ commit/push/mở PR khi nhiệm vụ đã yêu cầu hoặc phạm vi phiên làm việc cho phép. Nếu chỉ yêu cầu sửa code, giao diff và báo cáo để người dùng commit.
- Khi commit, chỉ stage file liên quan; không dùng git add . một cách máy móc.
- Giữ danh tính Git của người dùng hiện tại; không tự đổi user.name/email, giả co-author hoặc tạo commit cho thành viên khác.
- Commit có ý nghĩa, ví dụ `feat(search): add image retrieval`; không tạo commit rỗng để đủ KPI.
- PR nhiệm vụ vào develop: mô tả hành vi, tests, schema/API/dependency changes và Issue thật.
- Không tự approve; merge/release phải theo phân quyền nhóm và yêu cầu cụ thể, không coi file này là quyền tự phát hành.
- Nếu nhiều người/agent làm đồng thời, dùng checkout/worktree riêng khi phù hợp; thống nhất shared files. Không can thiệp branch/worktree người khác.

### 8.1. Quy tắc commit dành cho Codex

**Quyền thực hiện:** yêu cầu sửa file hoặc thêm quy tắc không tự cho phép commit/push. Nếu người dùng đã giao commit, push hoặc mở PR trong phiên thì thực hiện đúng phạm vi đó, không hỏi lại cho từng commit. Quyền commit không tự bao gồm push; quyền push không tự bao gồm merge/release. Không commit trên `main`/`develop`; nếu chưa có bản clone Git hợp lệ hoặc nhánh nhiệm vụ đúng, giao diff và nêu blocker, không tự `git init` hay bịa Issue để tạo nhánh.

**Đơn vị commit:** mỗi commit giải quyết một thay đổi có mục đích rõ và review được. Gộp code, tests và docs trực tiếp liên quan khi cần để thay đổi nhất quán; tách refactor/format diện rộng hoặc thay đổi độc lập. Không chia thành commit theo từng file, không gộp nhiều Issue không liên quan, không tạo commit rỗng hoặc commit chỉ để tăng số lượng. Không bắt buộc một Issue chỉ có một commit.

**Commit message:** dùng `<type>(<scope>): <summary>`, hoặc `<type>(<scope>)!: <summary>` khi có breaking change. Viết summary tiếng Anh, động từ dạng mệnh lệnh, cụ thể và ngắn gọn (mục tiêu tối đa 72 ký tự cho dòng đầu); không dùng `update`, `fix stuff`, `WIP` làm mô tả chung chung. Scope có thể bỏ qua nếu thay đổi ở cấp repo không có module phù hợp.

| Type | Khi dùng |
|---|---|
| `feat` | Thêm hành vi/tính năng cho sản phẩm |
| `fix` | Sửa hành vi sai hoặc lỗi |
| `test` | Thêm/sửa tests, không đổi hành vi sản phẩm |
| `docs` | Chỉ đổi tài liệu, bao gồm `AGENTS.md` |
| `refactor` | Đổi cấu trúc code, giữ nguyên hành vi |
| `perf` | Cải thiện hiệu năng; ghi bằng chứng đo thực tế nếu tuyên bố cải thiện |
| `build` | Dependencies, lockfiles, đóng gói hoặc cấu hình build |
| `ci` | GitHub Actions và quy trình CI |
| `chore` | Công cụ/cấu hình bảo trì ngoài các nhóm trên |
| `style` | Format code, không đổi hành vi; thay đổi giao diện có hành vi dùng `feat`/`fix` |
| `revert` | Hoàn tác commit, ghi SHA thật và lý do |

Scope theo phần thay đổi: `api`, `db`, `ingestion`, `embedding`, `search`, `frontend`, `feedback`, `admin`, `evaluation`, `ci`, `docker`, `deps`, `agents`. Type của commit phản ánh nội dung, không bắt buộc trùng prefix nhánh; ví dụ commit `refactor(search)` vẫn có thể nằm trên nhánh `chore/<issue>-<task>`.

Ví dụ: `feat(search): add image retrieval`, `fix(ingestion): preserve failed asset status`, `docs(agents): define commit rules`. Đây là ví dụ định dạng, không xác nhận tính năng đã có.

Với thay đổi cần giải thích, thêm body tiếng Việt nêu lý do, ảnh hưởng và kiểm thử thực tế. Thêm footer `Refs #<ID thật>` khi có Issue đã xác nhận; không điền placeholder hoặc bịa ID vào commit. Ưu tiên `Refs` khi tích hợp vào `develop`, không dùng `Closes` để ngụ ý Issue đã hoàn thành trước review/release. Thay đổi phá vỡ API/schema/index compatibility phải có `!`, footer `BREAKING CHANGE: ...`, hướng dẫn migration/rebuild liên quan và quyết định contract đã được chốt.

**Trước khi commit:**

1. Kiểm tra `rtk git status --short --branch`, diff của phần thay đổi và `rtk git diff --cached` để nhận diện cả staged changes có sẵn. Không đưa thay đổi của người khác vào commit, không tự unstage/stash chúng; nếu index lẫn thay đổi không thể tách an toàn, báo blocker.
2. Chạy kiểm tra phù hợp ở mục 9. Nếu lỗi do thay đổi hiện tại, sửa trước khi commit hoàn tất. Nếu môi trường chặn kiểm thử, ghi lệnh chưa chạy và blocker; không ghi `tests passed` hoặc đánh dấu DoD đạt. Không bỏ qua hooks bằng `--no-verify` hoặc biến môi trường để né lỗi.
3. Stage đường dẫn cụ thể bằng `rtk git add -- <file...>`; nếu file chứa nhiều nguồn thay đổi, chỉ stage các hunk thuộc nhiệm vụ khi có thể tách an toàn. Không dùng `git add .`/`git add -A` để gom toàn repo.
4. Đọc lại staged diff và chạy `rtk git diff --cached --check`; kiểm tra không có secret, `.env`, weights, bulk data, cache hoặc build output. Chỉ commit khi staged diff đúng phạm vi và message mô tả đúng nội dung.

**Sau khi commit:** kiểm tra commit vừa tạo và trạng thái working tree; báo SHA thật, message, kiểm thử và file còn chưa commit nếu có. Không tự amend/rebase lịch sử đã chia sẻ hoặc commit của người khác; mặc định sửa bằng commit mới. Khi push đã được giao, chỉ push nhánh nhiệm vụ cụ thể, không dùng `--all`, `--mirror`, `--force` hoặc push trực tiếp vào `main`/`develop`. Không tự thêm `Co-authored-by` hay đổi danh tính Git; giữ nguyên cấu hình attribution hợp lệ hiện có.

### 8.2. File được commit và file phải giữ ngoài Git

Chỉ commit file mới/sửa/xóa trực tiếp phục vụ nhiệm vụ đang làm, thuộc diff của mình và đã kiểm tra nội dung. Không stage cả thư mục chỉ vì nằm trong module được giao; file untracked không mặc nhiên là file cần commit. Các đường dẫn dưới đây là quy ước của dự án, không xác nhận đã tồn tại.

| Nhóm file có thể commit | Điều kiện |
|---|---|
| `backend/app/`, `frontend/src/`, `evaluation/` | Source code liên quan nhiệm vụ; không kèm dữ liệu/output phát sinh lúc chạy |
| `backend/tests/`, `frontend/tests/`, tests của evaluation | Tests và fixtures nhỏ, không chứa secret/dữ liệu cá nhân; ảnh lỗi/mẫu dùng kiểm thử có nguồn và license phù hợp |
| `backend/migrations/` | Migration cần cho thay đổi schema; kèm hướng dẫn áp dụng, không kèm database dump |
| Manifest dependencies và lockfile tương ứng | Ví dụ `pyproject.toml`, `package.json`, `uv.lock`, `package-lock.json` khi repo dùng chúng; cập nhật đồng bộ, không tạo lockfile cho package manager khác |
| `.github/`, `scripts/`, Dockerfile, `compose.yaml` | Cấu hình/công cụ dùng chung cần cho nhiệm vụ; không chứa đường dẫn riêng của máy hay credentials |
| `.gitignore`, `.env.example`, cấu hình lint/typecheck/test | Cấu hình chia sẻ; `.env.example` chỉ có placeholder, không sao chép giá trị thật từ `.env` |
| `README.md`, `ROADMAP.md`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/` | Tài liệu thực sự liên quan thay đổi; không đánh dấu tiến độ/đóng góp không có bằng chứng |
| `data/manifests/`, `data/samples/`, `data/benchmark/` | Manifest, metadata, query/nhãn và mẫu nhỏ có provenance/license; không chứa URL có token hoặc dữ liệu cá nhân |
| Config/manifest thí nghiệm, dataset/model card, kết quả evaluation nhỏ | Đủ để tái lập: versions/configs/seed/máy và kết quả thật; không kèm weights, index hay toàn bộ ảnh/asset |

**Không commit:**

- Secret và cấu hình riêng: `.env`, `.env.*` chứa giá trị thật, tokens/API keys, private keys, certificates có private key, credentials, thư mục `.aws/`. Ngoại lệ là file mẫu như `.env.example` đã kiểm tra chỉ có giá trị giả.
- Dependencies và môi trường: `node_modules/`, `.venv/`, `venv/`, thư mục package/model tải về.
- Cache và file sinh tự động: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.cache/`, cache Hugging Face, `*.tsbuildinfo`.
- Build/test output: `dist/`, `build/`, `coverage/`, `.coverage`, `htmlcov/`, `playwright-report/`, `test-results/`, screenshots/video/trace phát sinh từ test. Ảnh minh họa tài liệu chỉ commit khi nhỏ, cần thiết và đã loại dữ liệu nhạy cảm.
- Dữ liệu lớn và model: `data/raw/`, `data/processed/`, `data/models/`, weights/checkpoints, archives dataset, bulk ảnh/mesh, embedding dumps. Không cấm mọi file ảnh/JSON/CSV: mẫu nhỏ hợp lệ theo bảng trên vẫn có thể commit.
- Trạng thái dịch vụ: PostgreSQL dumps/data directories, SQLite chạy local, Qdrant storage/snapshots/index, Docker volumes, dữ liệu runtime của jobs.
- File máy cá nhân và tạm: logs, PID, swap/backup files, `.DS_Store`, cấu hình IDE cá nhân. Chỉ commit cấu hình IDE dùng chung nếu nhiệm vụ cần và nhóm đã thống nhất.
- Nội bộ Git và agent: `.git/`, session history, transcript, cấu hình cá nhân trong `.codex/`/`.agents/`. Chỉ commit tài nguyên agent dùng chung được giao rõ; không đưa lịch sử hội thoại hoặc credentials vào repo.
- Thay đổi không liên quan hoặc của thành viên khác, kể cả khi file đó vốn đã tracked.

Nếu nhiệm vụ tạo ra file cần loại khỏi Git, cập nhật `.gitignore` với pattern cụ thể phù hợp; không ignore toàn bộ `data/`, `evaluation/`, lockfiles hoặc file mẫu cần tái lập. `.gitignore` không loại file đã tracked: không tự xóa/untrack dữ liệu của người khác. Nếu phát hiện secret đã tracked/commit, không push; báo vị trí file mà không in giá trị secret, phối hợp thu hồi secret và xử lý lịch sử theo quyền được giao. Không dùng `git add -f` để vượt quy tắc loại trừ.

### 8.3. Push nhánh nào và mở PR về đâu

| Loại công việc | Nhánh để commit/push | Nhánh đích của PR |
|---|---|---|
| Tính năng | `feat/<issue>-<task>` | `develop` |
| Sửa lỗi, kể cả lỗi phát hiện trên bản demo | `fix/<issue>-<task>` | `develop` |
| Kiểm thử | `test/<issue>-<task>` | `develop` |
| Cấu hình, CI/Docker/dependencies, refactor bảo trì | `chore/<issue>-<task>` | `develop` |
| Tài liệu, quy tắc trong `AGENTS.md` | `docs/<issue>-<task>` | `develop` |
| Release do Vũ Nguyễn Quỳnh Anh và Đoàn Thị Minh Khuê điều phối | Không tạo commit/push trực tiếp lên hai nhánh chung | `develop → main`, qua PR đã review và dùng merge commit |

Nhánh nhiệm vụ tạo từ `develop` hiện có; `<issue>` phải là Issue thật, `<task>` mô tả ngắn bằng chữ thường/số/gạch ngang. Không push vào nhánh cá nhân dài hạn, nhánh của thành viên khác, `main` hay `develop`. Không tự tạo luồng hotfix đi thẳng vào `main` để bỏ qua quy trình tích hợp.

Khi đã được giao push:

1. Kiểm tra tên nhánh bằng `rtk git branch --show-current`, trạng thái bằng `rtk git status --short --branch`, remote bằng `rtk git remote -v`. Không đưa remote URL chứa token vào báo cáo. Nếu đang ở `main`/`develop`, detached HEAD, chưa có commit hoặc chưa xác định được Issue/nhánh đúng, dừng phần commit/push và nêu blocker; không tự chuyển nhánh có thay đổi của người khác.
2. Fetch remote phù hợp và kiểm tra các commit sẽ được đẩy, không chỉ commit cuối. Nếu lịch sử có commit ngoài nhiệm vụ, secret hoặc nhánh đã phân kỳ, xử lý đúng phạm vi trước; không force push để bỏ lỗi. Không tự đổi `origin` hoặc upstream sang repo khác.
3. Push tới nhánh remote cùng tên với nhánh nhiệm vụ. Lần đầu dùng `rtk git push -u origin <nhánh-nhiệm-vụ>`; lần sau vẫn chỉ rõ `rtk git push origin <nhánh-nhiệm-vụ>`, không dựa vào upstream chưa kiểm tra. `origin` phải là remote đã xác nhận; nếu nhóm giao remote khác thì dùng đúng remote đó. Thay placeholder bằng tên nhánh thật, không chạy nguyên ví dụ.
4. Nếu mở PR đã được giao, PR nhiệm vụ có base `develop`; chỉ PR release được giao riêng mới có base `main`, head `develop`. Không tự approve/merge. Chỉ báo push thành công khi lệnh thành công; chỉ báo CI xanh khi đã kiểm tra kết quả CI thật.

Không tự push tags, dùng `--tags`/`--follow-tags`, xóa nhánh remote hoặc phát hành release khi chỉ được giao push nhánh nhiệm vụ. Việc xóa nhánh nhiệm vụ sau merge và tạo release tag thực hiện khi được giao hoặc nhóm đã cho phép trong phạm vi phiên.

### 8.4. Checklist Issue và pull request

- Mọi PR dùng [template chung](.github/PULL_REQUEST_TEMPLATE.md), liên kết Issue thật và có checklist riêng cho triển khai/kiểm chứng và review/tích hợp. PR nhiệm vụ vào `develop`; PR release vẫn theo mục 8.3.
- Chỉ đánh dấu `[x]` khi mục đó đã hoàn thành và có bằng chứng phù hợp: file/commit, lệnh kèm kết quả, report hoặc phản hồi review. Chưa làm, bị chặn hoặc chưa xác minh thì giữ `[ ]` và nêu việc còn thiếu. Không áp dụng: ghi `N/A` cùng lý do cạnh ô chưa tích; không tạo việc giả để tích đủ các ô.
- Kiểm thử local, trạng thái CI, review của thành viên khác và merge là các việc riêng. Không dùng test local để tích CI xanh; không tự tích approve/merge thay reviewer. Chỉ cập nhật trạng thái đã quan sát được trên GitHub.
- Sau khi sửa code, cập nhật bằng chứng và checklist theo commit mới; chạy lại kiểm tra bị ảnh hưởng. Không bỏ test, giảm coverage hoặc che lỗi để đủ ô tích. Nếu bỏ code không còn dùng cùng test riêng của nó, nêu lý do và kiểm tra hành vi ứng dụng còn lại.
- Khi bàn giao PR, cập nhật checklist acceptance criteria trong Issue liên quan và liên kết PR, giữ nguyên tiêu chí đã thống nhất. Mục cần owner review/chốt contract phải để chưa tích đến khi có xác nhận; không tự đóng Issue hoặc đánh dấu cả milestone xong chỉ vì có PR.
- Trước merge: required checks hiện có đạt, ít nhất một thành viên khác approve và các trao đổi chặn được xử lý; người có quyền và được giao mới merge. Checklist là công cụ theo dõi, không thay thế branch protection hoặc quyền review/merge.

## 9. Kiểm thử và lệnh

Đọc `backend/pyproject.toml`, frontend `package.json`, lockfiles và README. **Chạy lệnh thực sự có trong repo**; các tên dưới đây là quy ước đề xuất cần thiết lập, không xác nhận đã tồn tại.

- Backend: pytest unit; integration khi thay DB/Qdrant/API/pipeline.
- Frontend: lint, typecheck, build; component tests cho hành vi; E2E cho luồng chính bị ảnh hưởng.
- Evaluation: test metric bằng ví dụ nhỏ biết đáp án; benchmark theo configs khi đổi retrieval.
- CI nhanh dùng fixtures/mock encoder có nhãn rõ; không tải model/dataset lớn mỗi PR.
- Smoke với model thật và benchmark là bước riêng trước quyết định/release.

Tests có ý nghĩa: ingestion chạy lại không trùng; ảnh hỏng không làm hỏng batch; filters giữ đúng điều kiện; top K không trùng asset; vector version không trộn; API/frontend contract khớp; feedback lưu đúng event. Không chỉ mock rồi khẳng định model retrieval đạt chất lượng.

Tách validation/test; không chỉnh theo test. Ghi máy, seed nếu có, versions, configs và raw results. Không bịa benchmark, test pass, CI status hay thời gian chạy. Nếu chưa chạy được, ghi blocker và lệnh cần chạy; chỉ tiếp tục phần độc lập.

## 10. Tài liệu, tiến độ và bảo mật

- Cập nhật docs trực tiếp liên quan; không rewrite toàn bộ kế hoạch cho một sửa nhỏ.
- Không đánh dấu ROADMAP milestone xong chỉ vì scaffold hoặc có code chưa test.
- `docs/contributions.md`: ghi hoạt động/PR/tests thật; chưa có PR thì ghi local/unmerged, không giả link hoặc tự nhận công người khác.
- Không commit .env, credentials, weights, caches, bulk data hoặc ảnh lớn. .env.example dùng giá trị giả.
- Dependency mới phải phục vụ Issue; giữ lockfile theo package manager của repo.
- Migration phải tương thích dữ liệu và có hướng dẫn; không tự drop DB/collection hay chạy destructive migration ở môi trường chung.
- Không giả UI/action thành công khi API thất bại. Mock chỉ ở chế độ phát triển/test được ghi rõ.

## 11. Báo cáo kết thúc nhiệm vụ

Trả lời ngắn bằng tiếng Việt:

1. Đã thay đổi gì và vì sao.
2. Module/file chính, ảnh hưởng API/schema/index nếu có.
3. Tests/lệnh đã chạy và kết quả thật.
4. Việc chưa làm, blocker hoặc giới hạn còn lại.
5. Trạng thái Git/PR nếu thao tác đó thực sự được thực hiện.

Definition of Done: acceptance criteria đạt, kiểm thử phù hợp, docs liên quan cập nhật, diff đúng phạm vi; review/merge/release là các bước riêng theo quy trình nhóm. Nếu người dùng giao toàn milestone, hoàn thành các phần phụ thuộc cần thiết trong milestone, không dừng ở proposal.

## 12. Mẫu giao việc cho Codex

```text
Đọc AGENTS.md và ROADMAP.md.
Tôi là Trịnh Thị Thu Huyền, thực hiện Issue #<ID thật>: ingestion idempotent thuộc W2.
Phạm vi: backend/app/ingestion/ và tests tương ứng.
Giữ nguyên API contract, encoder và dependency files trừ khi cần và nêu rõ lý do.
Tiêu chí: nhập lại không trùng; asset lỗi có trạng thái; retry có giới hạn.
Đọc code hiện tại, triển khai, chạy tests liên quan và báo cáo kết quả.
```

Tài liệu quy ước Codex: https://developers.openai.com/codex/guides/agents-md
