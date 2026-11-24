# Bằng chứng runner/jobs/reindex W6 — Issue #138

Ngày 25/11/2026 (Asia/Bangkok), nhánh `feat/138-api-improvements`, base
`7becbde36aa8e5e503ae30d72c65516647de54d6` (PR #140/#137 đã merge).
Working tree dirty khi chạy; không gán commit sau này cho lượt kiểm chứng local.
Chưa commit/push, chưa có CI/review/merge của #138 tại thời điểm ghi báo cáo.

## Rà soát và sửa lỗi có tái hiện

| Phần W5 đã có | Phần bổ sung #138 |
|---|---|
| Timeout/child exit/output lỗi được phân loại | Kiểm thêm profile/hash/search-check/store với child exit 0; phân loại input đổi trước khi worker chạy |
| Lifecycle queued/running/terminal riêng transaction | Log job ID/stage/mã an toàn cho create/start/failure/final commit lỗi, không chỉ tên exception |
| Partial unique index/advisory lock và replay | Thêm concurrency khi operation lỗi, replay failed/restart, guard giữ khi không lưu được terminal |
| Commit cuối lỗi không báo succeeded | Mở rộng chẩn đoán, replay, CLI và scheduling lỗi cùng DB từ chối commit |
| Search/feedback cùng app test | Chạy lại hồi quy coexistence, lỗi DB/rollback và smoke index baseline riêng |

Trước sửa, **7 ca regression mới đều thất bại**:

- Outcome None không được ghi failed, chỉ ghi lỗi final state và có thể kẹt running.
- Outcome không có error nhưng exit_code khác 0, failed count >0 hoặc
  search_verified=false vẫn được gửi tới finish_job như thành công.
- Progress processed > total không được kiểm trước final commit.
- ReindexFailure.code ngoài allowlist được chuyển nguyên vào DB.
- CLI cũng xác nhận success cho Outcome exit_code khác 0 nhưng thiếu error.

Sau sửa, worker/CLI kiểm Outcome trước khi ghi kết quả. Outcome sai trở thành
failed/RUNNER_OUTPUT_INVALID nếu DB ghi được, không lưu result sai; code và
message lỗi được chuẩn hóa. Log phân biệt operation lỗi với ghi failed/final
state lỗi. `intended_status` chỉ là dự định, không phải xác nhận đã commit.

Không thêm route/DTO field/status/migration/dependencies; không sửa frontend,
model/encoder/store, frozen config, manifest nguồn hoặc active index. Bổ sung
hai mã operation REINDEX_INPUT_INVALID/RUNNER_OUTPUT_INVALID trong contract.
JOB_STATE_UNAVAILABLE chỉ nằm trong chẩn đoán log.

## Kiểm chứng local

| Nhóm | Kết quả/phạm vi |
|---|---|
| Unit mới | **32 cases**: Outcome, allowlist/privacy, CLI DB faults, phân biệt operation/persistence, 11 trường hợp guard artifact với child/store fixtures |
| PostgreSQL/HTTP/lifecycle | Thêm 12 cases so với baseline, gồm concurrency terminal lỗi, failed replay sau restart, invalid Outcome, start/failure/scheduling/CLI commit faults; mở rộng test final commit hiện có |
| Hồi quy cuối | **451 passed**, 0 errors/failures/skipped, **59,74 giây**; đã gồm tests mới, toàn thư mục integration và các unit API/DB/search/feedback/logging liên quan |
| Smoke CLIP thật | **Passed**: HTTP → worker/child thật → output riêng → job terminal → HTTP search; baseline fingerprint không đổi |
| Kiểm tra tĩnh và dọn test | git diff --check, cú pháp Python, whitespace/link tài liệu mới đạt; không còn database test_issue138_ do launcher tạo |

Lượt tập trung đầu đạt 87/87 (68,18 giây) trước khi thêm các ca artifact/CLI
cuối. Lượt unit riêng sau đó đạt 32/32 (14,36 giây); không cộng số tests các
lượt vào tổng 451.

**Lịch sử lượt hồi quy lỗi:** khi chạy song song smoke CPU thật, lượt đầu có
450 passed/1 failed (187,81 giây). Ca
`test_runner_failure_is_durable_sanitized_and_releases_resource[error0]`
hết hạn đợi fixture worker; log có start_state/JOB_STATE_UNAVAILABLE cho job
phục hồi. Chưa xác định chắc nguyên nhân lỗi start ở lượt đó, không khẳng định
đã sửa lỗi môi trường. Kiểm tra lại cả hai tham số riêng đạt 2/2 (4,09 giây),
rồi chạy lại nguyên nhóm hồi quy sau khi smoke kết thúc đạt 451/451.
Không đổi assertion, bỏ test hoặc tăng timeout để lấy kết quả xanh.

PostgreSQL dùng database `test_issue138_<UUID>` do launcher local tạo/dọn;
helpers tạo/dọn schema UUID, migrate 0004 và inject constraints riêng. Không
ghi DB nghiệp vụ hoặc tự sửa queued/running trong DB chung. Retrieval trong
tests coexistence dùng fixtures; không coi đó là benchmark hoặc model thật.

Môi trường: Windows 11, Python 3.13.7/backend venv, PostgreSQL Docker local,
dependencies theo requirements hiện có. Smoke chạy offline từ cache, đặt
HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1, OMP_NUM_THREADS=4, MKL_NUM_THREADS=4;
không tải weights/dataset. Không đo latency/SLO hoặc chọn lại cấu hình W6.

## Smoke thật, output mới

Tái sử dụng nguyên verifier `scripts/verify_reindex_api.py` của #117.
Report của verifier vẫn ghi issue 117; đây là lượt chạy mới cho #138, không
sửa hoặc ghi đè bằng chứng lịch sử #117.

- Lượt kết thúc: `2026-11-24T17:14:18.484001+00:00`, tức 00:14 ngày 25/11 tại UTC+7.
- Job success: `13e467d8-1801-4b94-a1f2-3ee30b2ab5c1`, 200/200 assets/points,
  succeeded=200, failed=0, search_verified=true; trạng thái cuối đọc từ DB.
- Job cache rỗng cố ý: `1ca0c551-1534-4802-abc4-ddc38dc1f2ee`, child thật
  thất bại, job failed/INDEXING_FAILED, result=null. Không sửa cache gốc.
- Replay dùng job cũ, request mới khi busy bị 409; auth/validation đạt.
- HTTP text search trên index mới trả 200/12 kết quả, cosine và versions
  khớp manifest/index_version `reindex-clip-13e467d818014b94a1f23ee30b2ab5c1`.
- CLIP pin `openai/clip-vit-base-patch32@3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`;
  snapshot home-interior-clear-200-v3, source SHA-256
  `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.
- Fingerprint baseline trước/sau giữ nguyên:
  `4ec8a57d3532cb126ebca29d818d6e85aa1c36231eb88b2d208f6101b559c687`.
  `active_index_changed=false`; không mở/activate cấu hình fusion W6.

Lệnh tại gốc repo, với TEST_DATABASE_URL trỏ DB test riêng:

```powershell
.\backend\.venv\Scripts\python.exe scripts/verify_reindex_api.py --cache-ready data/processed/issue65/index-1718ec3c49a0/ready.json --baseline-index-root data/processed/issue65/index-1718ec3c49a0 --output-root data/processed/issue138/reindex-20261125 --output data/processed/issue138/reindex-http-20261125.json
```

Report/runtime output nằm ngoài Git. Report SHA-256:
`6c720969346502b6ba7ef3cb5f58ae18abcb81e52ea9c4d3f399495471122e88`.
Output index mới ở `data/processed/issue138/reindex-20261125/<job UUID>/`.
Verifier ghi raw module hashes trong report. Ba module thay đổi khi chạy:

| Module | SHA-256 raw checkout |
|---|---|
| backend/app/services/job_runner.py | 0b701f769d5ed1afe1ace73622c98fc6717d20512f684fabe1f7a5990cd31c5c |
| backend/app/services/reindex.py | 2f7e31fb476485c8ec0ecaca44982460595b84da9d1817745f125f9ac0a30f0b |
| backend/app/services/job_diagnostics.py | a5d4429c77531460280866d29dc0735451f9d9c672123a7d44fbde642b15d0c0 |

## Tái lập tests

Đặt TEST_DATABASE_URL ngoài Git tới PostgreSQL riêng có tên database `test_*`,
driver postgresql+psycopg. Từ backend/, nhóm hồi quy đã chạy:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_job_failures.py tests/unit/test_request_logging.py tests/unit/test_api_error_envelope.py tests/unit/test_asset_list_errors.py tests/unit/test_asset_detail_errors.py tests/unit/test_health.py tests/unit/test_mock_api.py tests/unit/test_openapi.py tests/unit/test_text_search_contract.py tests/unit/test_text_search_api.py tests/unit/test_text_search_service.py tests/unit/test_text_search_runtime.py tests/unit/test_image_search_api.py tests/unit/test_feedback_api.py tests/unit/test_search_explanation.py tests/unit/test_jobs_api.py tests/unit/test_reindex_api.py tests/unit/test_reindex_builder.py tests/unit/test_config.py tests/unit/test_database_config.py tests/unit/test_asset_api_verification.py tests/integration -q --junitxml=../data/processed/issue138/pytest-regression-sequential.xml
```

Các JUnit local giữ riêng: pytest-focused.xml, pytest-regression.xml (lượt có
1 failure), pytest-recheck.xml và pytest-regression-sequential.xml (lượt cuối),
đều dưới data/processed/issue138/. Không ghi đè lượt lỗi bằng lượt passed.

JUnit cuối bắt đầu `2026-11-25T00:15:21.686908+07:00`, SHA-256:
`8e75143d2096aba7c25ca65e9df161bc7dfcbf2d2a1677b83a2bacc4369a7238`.

## Giới hạn và review còn chờ

- Job có thể còn queued/running nếu DB không ghi được trạng thái cuối hoặc
  process bị kill. Không tự retry operation, reset guard, resume/cancel hay sửa DB.
- Chưa chạy lại toàn bộ backend unit suite, E2E browser, benchmark hoặc smoke
  feedback bằng model thật; hồi quy feedback ở PostgreSQL với retrieval fixtures.
- Không sửa UI. Khuê cần review cách tiếp nhận mã lỗi mới và việc UI giữ trạng
  thái DB thật khi log báo commit lỗi, không tự coi job thành failed/succeeded.
- Chi review phân loại input/artifact và việc giữ profile/output riêng/baseline;
  không yêu cầu chốt lại model/index/config hoặc dựng thêm sản phẩm mới.
- Required CI, reviewer approval và merge là bước riêng sau mở PR; chưa tích
  thay người khác, chưa đóng Issue #138 từ kết quả local.

Hướng dẫn: [job-failure-diagnostics-w6.md](../guides/job-failure-diagnostics-w6.md).
