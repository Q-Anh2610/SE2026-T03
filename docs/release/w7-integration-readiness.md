# W7/M6 — Tích hợp và chuẩn bị phát hành W8 (#146)

Trạng thái ngày 28/11/2026: **đang chuẩn bị, chưa đủ điều kiện phát hành**.
Snapshot đầu vào: develop `213472bdeff7b6eef9b9f7ac6c54c79099831589`
(PR #153/#145). Nhánh thực hiện: `chore/146-release-integration-readiness`.
Không mở release PR, merge develop → main hoặc tạo tag trong #146.

## Đầu vào và bằng chứng đã có

| Phần | Đầu vào hiện có | Trạng thái sử dụng |
|---|---|---|
| API docs — Quỳnh Anh | [#145](https://github.com/Q-Anh2610/SE2026-T03/issues/145), [PR #153](https://github.com/Q-Anh2610/SE2026-T03/pull/153), [guide](../guides/api-reproducibility-w7.md) | Đã merge; Duy review client, Khuê review setup/bằng chứng |
| Dữ liệu — Huyền | [#142](https://github.com/Q-Anh2610/SE2026-T03/issues/142), [PR #143](https://github.com/Q-Anh2610/SE2026-T03/pull/143) | Đã đóng/merge; sample có provenance/attribution, không thay candidate 200 |
| Index/search — Chi | [#135](https://github.com/Q-Anh2610/SE2026-T03/issues/135), [PR #144](https://github.com/Q-Anh2610/SE2026-T03/pull/144), [guide](../guides/issue135-w7-rebuild.md) | Đã đóng/merge; có tái lập độc lập của Khuê. Không tự dùng rebuild làm binding benchmark mới |
| Docker — Khuê | [#148](https://github.com/Q-Anh2610/SE2026-T03/issues/148), [PR #152](https://github.com/Q-Anh2610/SE2026-T03/pull/152), [runbook](../guides/docker-clean-setup-w7.md) | Đã đóng/merge; bằng chứng hạ tầng tách khỏi semantic/E2E |
| E2E — Khuê | [#149](https://github.com/Q-Anh2610/SE2026-T03/issues/149) | **Chờ** PR/báo cáo UI → API → PostgreSQL/vector store thật |
| Hiệu năng — Khuê | [#150](https://github.com/Q-Anh2610/SE2026-T03/issues/150) | **Chờ** báo cáo cold/warm, p50/p95, cấu hình/máy và lệnh tái lập |
| UI — Duy | [#151](https://github.com/Q-Anh2610/SE2026-T03/issues/151) | Có kiểm chứng local ghi trong issue; **chờ** user testing và PR/merge theo checklist |

Đây là snapshot GitHub lúc rà soát; issue mở không có nghĩa chưa làm local.
Không lấy kết quả fixtures hoặc báo cáo W6 để tự tích mục E2E/hiệu năng W7.

Đầu vào evaluation phải giữ nguyên config
`w6-clip-e5-rrf-k20-candidate200-v1`, raw SHA-256
`1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5`,
snapshot `home-interior-clear-200-v3`, source SHA-256
`9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.
Pins/index binding chi tiết theo [protocol rebuild](../guides/issue135-w7-rebuild.md)
và [báo cáo benchmark W6](../evaluation/issue128-w6-test-benchmark.md).
HTTP API hiện tại vẫn là baseline CLIP/cosine; không gắn nhãn RRF cho smoke API.
Image Docker #148 dùng torch `2.8.0+cpu`; protocol #135 pin chuỗi `2.8.0`.
Không tự coi image hạ tầng đã đạt gate môi trường benchmark/rebuild nghiêm ngặt.

## Phần #146 làm trước và phần còn chờ

- [x] Đối chiếu đầu vào đã merge, owner và liên kết hướng dẫn/bằng chứng.
- [x] Lập bảng bàn giao và checklist W8 theo ROADMAP/quy trình Git hiện có.
- [x] Đã chạy và tổng hợp smoke hạ tầng/API mock trên checkout sạch ở
  [báo cáo #146](../evidence/issue146-integration-readiness.md); không coi đó là E2E semantic.
- [ ] Nhận kết quả #149 và đối chiếu với đúng commit/cấu hình/data/index.
- [ ] Nhận kết quả #150 và kiểm khả năng tái lập theo config/snapshot đã khóa.
- [ ] Nhận PR UI #151 đã merge và kết quả user testing thực tế.
- [ ] Đối chiếu lại develop sau các PR còn chờ, chạy lại checks bị ảnh hưởng.
- [ ] Chốt readiness với Khuê; cập nhật nghiệm thu #146 theo bằng chứng mới.

Smoke hạ tầng/mode mock có thể làm ngay; chưa xác nhận toàn stack semantic,
feedback PostgreSQL qua UI hoặc benchmark chỉ từ việc containers healthy.
Các mục nghiệm thu tổng của #146 giữ chưa hoàn thành đến khi có đủ bằng chứng.

## Các điểm cần theo dõi

| Điểm | Bằng chứng/phạm vi | Owner và bước tiếp |
|---|---|---|
| Proxy runtime OpenAPI — ưu tiên cao cho luồng feedback cùng origin | Đã tái hiện HTTP #146: backend trả JSON, nginx trả 200/text-html có React root. Chưa chạy browser E2E và chưa sửa | Quỳnh Anh triage tại [#147](https://github.com/Q-Anh2610/SE2026-T03/issues/147), phối hợp Khuê/Duy; #149 xác nhận UI sau sửa |
| Raw bytes inputs đã khóa | Checker trên checkout local dừng ở raw_hash_mismatch:queries.csv; bytes CRLF khác blob Git LF dù Git status sạch | Không sửa hash/frozen data. Dùng checkout sạch LF, kiểm raw pins trước benchmark; kết quả checker mới ghi riêng |
| Semantic Docker binding | Docker mặc định search/feedback mock; API CLIP/cosine không tự chuyển sang frozen E5/RRF | Khuê/Chi đối chiếu server collection/manifest/model cache, binding và phạm vi thật khi #149/#150 bàn giao |
| Benchmark tái lập W7 | Có harness/báo cáo W6, nhưng chưa nhận đầu ra #150 | Khuê bàn giao command/report/provenance; giữ nguyên frozen config và không tune từ test |

Không tự gán lỗi chưa tái hiện là lỗi sản phẩm đã xác nhận; không tự sửa nginx,
client, frozen config hoặc active index trong phần chuẩn bị #146 này.

## Bàn giao cần bổ sung

**Khuê — #149/#150:** PR/commit đã kiểm, commands, reports nhỏ hoặc link raw
ngoài Git kèm hashes; dữ liệu/index/model/config versions, môi trường, số ca,
phạm vi fixtures/thật, p50/p95/cold-warm và lỗi còn mở. Ghi rõ kiểm API baseline
hay frozen fusion service; không coi hai cấu hình là một.

**Duy — #151:** PR/merge commit, ghi nhận user testing, kết quả responsive/
accessibility và các vấn đề còn lại. #149 cần chỉ rõ UI build nào đã được kiểm.

**Chi/Huyền nếu có thay đổi đầu vào:** xác nhận pins/source/provenance và mapping
artifact trước khi dùng; không cần dựng lại phần đã nghiệm thu chỉ để đủ checklist.

**Quỳnh Anh:** tái hiện/triage vấn đề proxy tại #147; liên kết PR sửa thực tế và
tests. Cập nhật bảng này sau các bàn giao, không xóa giới hạn/lịch sử lượt cũ.

## Checklist readiness W8 — chưa phải quyền phát hành

- [ ] Chọn commit develop dự kiến phát hành; ghi rõ các PR đã tích hợp.
- [ ] Đã nhận đủ #149/#150/#151 và kiểm lại các phần bị ảnh hưởng sau merge.
- [ ] Dựng/smoke theo README trên checkout/môi trường sạch, có người khác tác giả
  kiểm chứng; ghi rõ dùng cache và mức cô lập, không gọi là máy vật lý mới nếu không có.
- [ ] UI text/image/filters/detail/feedback đạt trên stack thật ở cấu hình công bố.
- [ ] Vấn đề proxy OpenAPI đã được xử lý/kiểm chứng hoặc có quyết định phạm vi
  được nhóm chấp nhận; không bỏ qua lỗi chặn luồng demo chính.
- [ ] Benchmark tái lập có hashes/config/index/model/dataset và giới hạn rõ;
  không đổi model/params theo held-out test.
- [ ] Blocker ưu tiên cao đã xử lý; việc hoãn có owner/lý do/ảnh hưởng cụ thể.
- [ ] CI/required checks đạt trên commit mới nhất; có review và xử lý trao đổi chặn.
- [ ] Tài liệu API/setup, SRS/architecture và đóng góp W8 khớp phạm vi đã làm.
- [ ] Cả 5 thành viên hiểu và demo phần mình; ghi giới hạn hệ thống thực tế.
- [ ] Quỳnh Anh/Khuê điều phối release PR develop → main khi được giao riêng;
  reviewer khác approve, merge commit theo [quy trình nhánh](../BRANCHING.md).
- [ ] Sau release được giao: kiểm thử main và tag `v1.0.0` theo ROADMAP W8.

Nhánh nhiệm vụ của #146 chỉ mở PR vào develop. Tất cả mục W8 phía trên là việc
còn phải xác nhận trong giai đoạn phát hành, không tự tick từ smoke local #146.
