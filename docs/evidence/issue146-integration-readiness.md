# Bằng chứng chuẩn bị tích hợp W7 — Issue #146

Lượt chuẩn bị ngày 28/11/2026 (Asia/Bangkok), nhánh
`chore/146-release-integration-readiness`; base develop
`213472bdeff7b6eef9b9f7ac6c54c79099831589` (merge #153/#145).
Đây là phần làm trước, **chưa nghiệm thu toàn #146 hoặc phát hành**.

## Phần đã thực hiện

- Đọc README/ROADMAP, hướng dẫn API #145, Docker #148, rebuild #135 và quy trình
  release; đối chiếu GitHub và các bàn giao hiện có, không chỉ dựa vào ô tick.
- Xác nhận #145 đã merge, có Duy review client và Khuê review setup/bằng chứng
  trên [PR #153](https://github.com/Q-Anh2610/SE2026-T03/pull/153).
- Ghi bảng đầu vào #142/#135/#148 đã sẵn sàng, #149/#150/#151 còn chờ tại
  [readiness W7/W8](../release/w7-integration-readiness.md).
- Lập checklist W8, tách readiness khỏi quyền mở/merge release PR hoặc tag.
- Tạo checkout detached riêng từ đúng base để kiểm chứng, giữ nhánh của người
  dùng và .env/DB/index đang dùng nguyên trạng.

Không sửa backend/frontend runtime, nginx/Compose, frozen config, dataset,
manifest/hash lịch sử hoặc active index. Không thực hiện benchmark hoặc nhận
phần E2E/hiệu năng của Khuê thành việc đã hoàn thành trong #146.

## Raw pins và checkout

Checker trên checkout local với `--local-inputs` dừng ở
`raw_hash_mismatch:data/benchmark/queries.csv`; chưa kiểm hết local inputs.
Git status sạch không bảo đảm raw bytes giống artifact đã khóa khi Git tự
chuẩn hóa xuống dòng:

| Bytes | SHA-256 / quan sát |
|---|---|
| Git blob HEAD:queries.csv | e202a0dc62406826ec29a2946d489c359a222133e6c530a9954832760d965470; 0 CRLF |
| File local hiện có | 80e7de4db77929bc79c87ddb1da1bdb1f101832d39a2fd3c6549ec8db7ae30b9; 74 CRLF |

Đối chiếu trong bộ nhớ cho thấy file local chuyển CRLF→LF thì bằng blob Git;
không ghi phép chuyển đó lên file, không sửa hash đã khóa để bỏ qua gate.
`.gitattributes` hiện quy định text/eol=lf cho queries.csv và frozen config.

Checkout tạm tạo bằng `git -c core.autocrlf=false worktree add --detach ...`
từ đúng base, dirty=false. Checker repo pins tại đó đã đạt trước build Docker:

```powershell
python scripts/verify_issue114_frozen_config.py --repo <checkout-sạch> --expected-sha256 1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5
```

Đây là kiểm raw pins trong Git, **không** xác nhận local inputs/weights/storage
đã đủ, không mở Qdrant, không chạy retrieval hoặc benchmark. Khi #150 bàn giao,
cần kiểm thêm local inputs đúng byte hashes và binding theo protocol owner.

## Docker và smoke tích hợp

**Đạt phần hạ tầng/API mock; chưa nghiệm thu semantic/E2E/benchmark.**
Source chạy từ checkout detached sạch của base ở đầu báo cáo. Không build từ
working tree đang sửa tài liệu. Mỗi lượt tạo .env từ mẫu với password local
ngẫu nhiên không in ra log, ports loopback riêng, project UUID và volumes mới.
Không dùng DB/volumes của project phát triển hoặc tải weights/dataset.

| Lượt | Kết quả |
|---|---|
| 20261128-137e845b81 | Compose config/build/up đạt, bốn services healthy. Verifier PowerShell 5.1 không resolve được Get-FileHash nên dừng trước HTTP checks; giữ report failed, không coi lượt này đạt verifier |
| 20261128-99795272fd | Chạy nguyên verifier bằng PowerShell 7.6.9: initial và repeat đều infrastructure_verified; toàn quy trình partial_integration_verified |

Lượt đầu build dependencies/image; lượt sau dùng lại build/image cache nhưng
checkout và volumes mới. Không gọi đây là máy vật lý mới. `pip check` trong
build đạt. Môi trường Windows 11 build 26200, Docker Engine 29.8.2, Compose
5.6.0; verifier nguyên repo hỗ trợ PowerShell 5.1/7, lượt đạt dùng `pwsh`.
Không bỏ checks hoặc sửa verifier để vượt lỗi cmdlet ở môi trường đầu.

Lượt đạt từ `2026-11-28T12:12:06.154610+00:00` đến
`2026-11-28T12:13:42.609542+00:00`; source dirty=false trước/sau smoke:

- PostgreSQL, Qdrant, backend, frontend healthy; migration container exit 0,
  revision 0004/head. UI HTML có React root, backend và proxy liveness đạt.
- GET assets qua nginx đọc DB thật/mock=false, items rỗng đúng DB/volumes mới.
  Qdrant ready và 0 collection; đây không phải bằng chứng index semantic đã có.
- HTTP text/image search qua nginx trả 200/mock=true. POST feedback thủ công
  qua nginx trả 201/storage=memory; **không đi qua bước frontend đọc OpenAPI**,
  nên không chứng minh feedback UI hoạt động. Validation trả 400/INVALID_REQUEST.
- Chạy `compose up` lần hai trên cùng volumes rồi nguyên verifier lần hai:
  vẫn đạt. Không seed fixture/metadata/index vào DB/Qdrant để ép passed.
- Đã kiểm sau dọn: cả hai project không còn containers/volumes, cả hai worktree
  được remove thành công. Images/build cache được giữ lại; không prune chung.

### Repro proxy runtime OpenAPI

Đã kiểm bằng HTTP trên project riêng từ đúng base, không còn chỉ là nhận xét
tĩnh như lượt #145:

| Request | Quan sát |
|---|---|
| GET backend-origin/openapi.json | 200, JSON có paths |
| GET frontend-origin/openapi.json | 200, Content-Type text/html, có React root, không phải JSON |

Đối chiếu feedback-client.ts: client fetch path này trước khi POST, còn nginx
đưa vào SPA fallback. Ưu tiên cao đối với nghiệm thu feedback UI cùng origin;
chưa chạy browser E2E để ghi tác động người dùng ở lượt này. Chưa sửa nginx/
client và chưa tự đăng comment/issue. Bàn giao repro sang #147, phối hợp
Khuê/Duy và nhận xác nhận E2E sau sửa ở #149.

### Tái lập và artifact

Dùng checkout mới từ commit đã ghi, kiểm dirty status, tạo .env theo
[runbook #148](../guides/docker-clean-setup-w7.md); đặt bốn host ports trống và
password riêng. Từ checkout đó, chọn project mới do lượt chạy sở hữu:

```powershell
docker compose -p issue146-local -f docker-compose.yml config --quiet
docker compose -p issue146-local -f docker-compose.yml up --build -d --wait --wait-timeout 180
pwsh -NoProfile -File scripts/verify_docker_stack.ps1 -ProjectName issue146-local
```

Chạy up/verifier lần hai để kiểm dùng lại volumes; gọi health/assets, text/image
mock/feedback thủ công theo [guide API](../guides/api-reproducibility-w7.md).
Đối chiếu `/openapi.json` trên cả backend/frontend origins bằng curl. Khi dọn,
chỉ dọn project/volumes do chính lượt này tạo theo runbook; không prune chung.
Nếu dùng worktree tạm, kiểm absolute path nằm trong thư mục tạm riêng và xóa
.env của lượt chạy trước khi remove worktree; không force-remove thay đổi khác.

[Bằng chứng JSON nhỏ](issue146/clean-integration-20261128.json) có checks,
source hashes, image IDs, môi trường, raw report hashes của cả lượt fail/pass
và xác nhận dọn. Đã loại .env, credentials, logs và absolute worktree path.
SHA-256 JSON:
`4166a6aacec1b656f39fcbe598e3b2451aebfa7fef1add68a2bdb9881b1fadf2`.
Raw reports/logs giữ riêng ngoài Git ở
`data/processed/issue146/<run ID>/`; verifier báo issue 148 vì được tái sử dụng
nguyên bản, không đổi bằng chứng lịch sử #148. Bản JSON bổ sung thuộc #146.

Đã đối chiếu initial/repeat: source hashes và image IDs khớp. Kiểm tra cuối
`git diff --check`, whitespace, link file Markdown và JSON evidence đạt;
Git diff không chứa thay đổi runtime, frozen config hoặc data. Không thêm unit
tests cho thay đổi tài liệu; Docker/verifier/HTTP probes là kiểm chứng thực tế
ở lượt này, không mượn số tests của #145 để báo thành kết quả #146.

## Việc còn chờ

| Đầu ra | Người bàn giao | Điều kiện bổ sung |
|---|---|---|
| E2E #149 | Khuê, phối hợp Duy/Quỳnh Anh | PR/commit, UI/API/DB/vector store thật, reports/traces an toàn và lỗi còn mở |
| Hiệu năng #150 | Khuê, phối hợp Chi | Command, model/index/config/snapshot/hashes, máy, cold/warm, p50/p95 và giới hạn |
| UI #151 | Duy | User testing, PR đã merge và bằng chứng responsive/accessibility trên UI đã tích hợp |
| Proxy runtime spec | Quỳnh Anh triage #147, phối hợp Khuê/Duy | Tái hiện, PR sửa đúng owner, regression và #149 xác nhận feedback UI |
| Chốt #146 | Quỳnh Anh/Khuê | Đồng bộ develop sau các PR, kiểm lại phần bị ảnh hưởng và cập nhật readiness |

GitHub tại lượt rà: #149/#150/#151 còn mở, chưa có comments bàn giao mới;
#151 có kết quả local mô tả trong issue. Không khẳng định chưa ai làm local,
chỉ ghi chưa có đủ bằng chứng tích hợp. Giữ các mục chờ chưa tích, không đóng #146.

CI/review của nhánh #146 chưa thực hiện; không mượn checks/approval của #153
để coi thay đổi này đã qua CI/review. Không mở release PR hoặc tạo tag.
