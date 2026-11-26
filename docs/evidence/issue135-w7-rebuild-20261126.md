# W7 rebuild CLIP/E5 — bằng chứng local #135

## Kết quả và provenance

Run `20261126T140828Z-c593def6`: `rebuild_and_service_smoke_verified`, stage complete.
26/11/2026, 21:08:28–21:09:15 UTC+7. Đây là lượt model thật offline trên CPU,
base commit `bff65ac2a29ae213042ae942524966ed6cd3ea5f`, working_tree_dirty=true.
Code/module hashes nằm trong report; không gán commit tạo sau cho lượt đo trước.
Quyền review/merge và xác nhận tái lập độc lập là các bước riêng.

| Kiểm chứng | Kết quả |
|---|---|
| CLIP preview index | 200 embedded, 0 failed/skipped; 512D, pin revision W6 |
| E5 metadata index | 200 embedded, 0 failed/skipped; 384D, pin corpus/recipe/revision W6 |
| IDs/point IDs/payload/filter fields | Auditors hiện có kiểm đủ 200, không trùng/mất; IndexConfig/payload khớp reference, cho khác index_version |
| Vector đối chiếu reference | Cả hai: 0 vector khác, max component abs delta=0.0; tolerance 1e-6 đã ghi trước |
| Persisted reopen | Fingerprints khớp chính xác trước query và sau smoke |
| Smoke services thật | Text CLIP/E5/fusion và image: filters rỗng đúng 200 IDs, category vắng trả 0; params/order/dedup/versions đạt |
| Bảo toàn nguồn | original_inputs_and_freeze_unchanged=true; original_storage_bytes_unchanged=true |
| Fixture regression checkout thật | 310 passed, 0 failed/errors/skipped; JUnit `issue135-user-regression-r3.xml` |

Report gốc SHA-256: `4d7e9a1fb1c667eb1eda944a8199eb6b17242fb2ae28b3801c58fb4cb4a6f19b`.
Protocol v1 SHA-256: `01130a382181aed65ac461d7b6a8b55c35d6c301f3ce759b57c77e5baa40900a`.
JUnit cuối SHA-256: `177670d6f6fa6d521c9e4f9d194d26fb79a3ee6d94a1ad85049197dda5f395be`.

## Raw artifacts và cách kiểm

Các file dưới đây là bản sao nguyên bytes, không sửa/sanitize/reserialize report
hay manifest để nhận commit/hash mới:

- [Report](issue135-rebuild-20261126T140828Z-c593def6/report.json)
- [Reference map còn pending](issue135-rebuild-20261126T140828Z-c593def6/reference-map.json)
- [CLIP manifest mới](issue135-rebuild-20261126T140828Z-c593def6/clip/index-manifest.json)
- [E5 manifest mới](issue135-rebuild-20261126T140828Z-c593def6/e5/index-manifest.json)
- [E5 persistence audit](issue135-rebuild-20261126T140828Z-c593def6/e5/persistence-audit.json)
- [Input inventory](issue135-rebuild-20261126T140828Z-c593def6/input-inventory.json)
- [Protocol đã dùng](issue135-rebuild-20261126T140828Z-c593def6/protocol.json)
- [Checksums gốc](issue135-rebuild-20261126T140828Z-c593def6/CHECKSUMS.sha256)

Từ repo root (Git Bash), kiểm đúng 10 file JSON đã bàn giao:

```bash
(cd docs/evidence/issue135-rebuild-20261126T140828Z-c593def6 && sha256sum -c CHECKSUMS.sha256)
```

Đây là gói evidence nhỏ, không phải storage/index hoặc gói inputs hoàn chỉnh.
Không chứa weights, previews, Qdrant storage, bulk rankings hoặc secrets. E5
corpus/source references giữ nguyên hashes, corpus JSONL và storage ở ngoài Git.
Các path runtime gốc là provenance của máy đã chạy, không phải dữ liệu đã commit.

## Manifest và khác biệt hợp lệ

CLIP có version `issue135-20261126T140828Z-c593def6-clip`, named vector mới và fingerprint payload
mới vì index_version/_index/named-vector khác; vectors vẫn khớp reference từng
thành phần. Không sửa reference W6 để ép fingerprint mới bằng fingerprint cũ.

E5 giữ version `issue91-e5-metadata-1588f4dc33fbe62609d8` theo version xác định từ
corpus+manifest hiện có. Fingerprint persisted khớp reference, nhưng manifest
rebuild có timestamp/code provenance/hash mới và root/run riêng; không coi đó là
cùng artifact lịch sử. Mapping schema `issue135-index-reference-map-v1` chỉ phục
vụ review; loader W6 không tự chấp nhận mapping này làm binding mới.

## Lịch sử kiểm thử và giới hạn

- Lượt terminal đầu: 309 passed/1 failed, do copy fixture E5 storage đạt đường
  dẫn 260 ký tự trên Windows. Giữ JUnit/raw output, không sửa assertions.
- Kiểm riêng ca lỗi với temp ngắn: 1 passed. Lượt toàn nhóm từ công cụ agent:
  291 passed, 1 failed/18 errors ở tests manifest cũ do môi trường công cụ không
  đọc được Git worktree; không ghi nhận lượt đó là passed.
- Lượt terminal cuối dùng temp ngắn: 310 passed; code, protocol, tolerance và
  assertions giữ nguyên. Không cộng số tests của các lượt để tạo tổng giả.
- Lịch sử staging trước áp dụng được lưu riêng trong bàn giao chat, không thay
  thế kết quả terminal trên checkout thật.
- Không chạy held-out queries/benchmark, chọn model/k hoặc đo HTTP/end-to-end
  latency. Không suy ra ranking giống tuyệt đối chỉ từ vector audit/smoke.
- Fixture tests bao phủ tie-break, filters có kết quả, errors/mismatch/no fallback;
  smoke model thật chỉ kiểm properties cố định, không so relevance hoặc tune.
- Chưa activate runtime, chưa review binding benchmark, chưa có thành viên khác
  tự rebuild theo guide, CI/approval/merge W7 chưa được xác nhận.

## Nghiệm thu theo bằng chứng

- [x] Kiểm pins/inputs và tái sử dụng builders/encoders/store hiện có.
- [x] Rebuild thật CLIP/E5 vào output riêng, ghi provenance/counts và bảo toàn reference.
- [x] Compatibility/reference comparison và persisted reopen đạt protocol trước đo.
- [x] Fixture regression và smoke model thật được ghi riêng, không tune theo test.
- [ ] Review artifact/mapping và giới hạn; consumer binding mới chỉ khi có phạm vi review riêng.
- [ ] Thành viên khác tự rebuild embedding/index/search trên output riêng và xác nhận.
- [ ] Issue/PR checklist, CI head mới nhất, approval và merge hoàn tất đúng trạng thái.
