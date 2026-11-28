# Đối chiếu tài liệu API/OpenAPI W7 — Issue #145

Ngày 28/11/2026 (Asia/Bangkok), nhánh
`docs/145-api-openapi-reproducibility`, base
`1a2a86f8be0c7943ec10c07cc5d43becf8823255` (merge PR #152/#148).
Thay đổi local/uncommitted khi kiểm chứng; chưa có CI/review/merge của #145.

## Thay đổi và đối chiếu

| Nội dung cũ/thiếu | Tài liệu hiện hành |
|---|---|
| api-v1.md còn nói service/persistence đang chờ triển khai W3 | Tổng hợp routes đã có, bốn mode/spec, assets DB, CLIP service, feedback DB, jobs/reindex |
| Dễ coi docs/openapi.json là spec cho mọi server | Bảng bốn export profiles, phân biệt file Git và runtime /openapi.json |
| Mock/service/production và feedback source chưa rõ | Quy tắc đăng ký route, 404 khi mock tắt, feedback source độc lập và schema discovery của frontend |
| Thiếu cập nhật lỗi/tracing W6 | 400 parser/validation, 403/409/503, envelope và X-Request-ID/CORS, link runbook jobs |
| Backend README còn nói Compose chỉ có DB/backend, migration riêng | Đối chiếu #148: DB/Qdrant/migrate/backend/frontend; migrate tự chạy trong Compose, seed riêng |
| Thiếu lộ trình kiểm chứng API | Guide Uvicorn fixture, Docker mặc định và service có input; commands, expected results, giới hạn |

Nguồn đối chiếu: app/main.py, core/config.py/errors.py/request_logging.py,
api và schemas text/image/feedback/jobs/reindex, export_openapi.py;
frontend/lib/api/search.ts, search/contract.ts, image/client.ts,
feedback-client.ts và admin clients; Docker Compose/nginx và runbook #148.

Không sửa route/DTO/schema DB/persistence/retrieval/headers/runtime configuration,
Docker hoặc frontend product code; không thêm dependency, tải model/dataset,
ghi DB hoặc thay index. Chỉ đổi tài liệu và thêm 8 tests contract profiles.
Không cập nhật tiến độ cả tuần hoặc tự tích review của thành viên khác.

## OpenAPI

Đã chạy từ backend/: `python -m app.export_openapi` bằng backend venv.
Cả bốn file đã khớp exporter, **không có diff JSON**; không thay spec để tạo
diff. Tám tests mới đối chiếu exports, toàn bộ local refs, response examples,
feedback schema discovery và đăng ký route khi production/mock bị tắt.

| File | SHA-256 raw checkout sau export |
|---|---|
| docs/openapi.json | 8ac6213e45562ffbe6588dfc52e01505334ad1e61e6dd74e7092a04d3eb1e810 |
| docs/openapi-text-search.json | 820781151af6f002b5563226c32fdb3ea6f6b2c44b4189d9cf249bd3681ef1a3 |
| docs/openapi-image-search.json | 8dd56f76fa4b8817c6d64ed72963b316e45f70038514e0451964a2618ca6be3e |
| docs/openapi-feedback.json | 32874ed3d3b918cdb3fd7bc3ca83535abcc366a2898d1bc23ae5728db69b3b1b |

## Kết quả local

| Kiểm tra | Kết quả và giới hạn |
|---|---|
| Backend contract/API/logging unit | **187 passed**, không skip, 10,17 giây; gồm 8 tests profile mới |
| Frontend client/contract | **362 passed / 7 files**, 12,44 giây; fixtures/mock fetch |
| Frontend Feedback component | **15 passed / 1 file**, 2,23 giây; lượt riêng, không trùng nhóm 362 |
| Uvicorn TCP thật | **12 checks passed**, profiles fixture/mock, không DB/model |
| Kiểm tra tĩnh | git diff --check, cú pháp Python, whitespace và các link file Markdown trong diff đều đạt |
| Docker | Engine chưa chạy; không build/start stack hoặc tuyên bố đã kiểm proxy/UI thật |

Backend command đầy đủ tại [guide API W7](../guides/api-reproducibility-w7.md#4-export-và-hồi-quy-contract).
JUnit local `data/processed/issue145/pytest-contracts.xml`, bắt đầu
`2026-11-28T17:22:37.263863+07:00`, SHA-256
`23d2a4bac77cf20736f88e37f736e8ea489836d9996524dc4807e66452888f84`.
Không cộng lượt kiểm tra riêng 10 tests OpenAPI trước đó vào tổng 187.

Frontend từ frontend/, hai lượt:

```powershell
npm run test -- src/lib/api/search.test.ts src/features/search/contract.test.ts src/features/search/live-contract.test.ts src/features/search/image/client.test.ts src/features/admin/client.test.ts src/features/admin/reindex-client.test.ts src/features/admin/contract.test.ts
npm run test -- src/features/search/Feedback.test.tsx
```

Lượt đầu có thêm một filter path FeedbackControl.test.tsx không tồn tại nên
Vitest chỉ chạy 7 files; sau đó đã xác định đúng Feedback.test.tsx và chạy
riêng đạt 15 tests. Commands phía trên dùng các paths thực sự đã chạy.

HTTP smoke dùng app factory với Settings fixture tường minh tương đương mục 2
của guide, thêm key admin fixture để kiểm 403; chạy Uvicorn ở cổng loopback
ngẫu nhiên bằng helper http_server hiện có. Kiểm health, assets fixture,
runtime spec, text/image search, feedback memory; missing query/broken JSON/
multipart thiếu boundary → 400, route sai → 404, method sai → 405, thiếu key →
403. Cả 12 response có UUID v4 và CORS expose X-Request-ID cho origin được phép.
Không mở DB, không nạp model; không gọi đây là semantic smoke hoặc E2E browser.

Report local `data/processed/issue145/http-fixture.json`, kết thúc
`2026-11-28T10:22:41.512799+00:00`, SHA-256
`88d0aa04717444d74e2ad801affce1ea0a2dba71a6c908368361ba7412fa694c`.
JUnit/report runtime tiếp tục nằm ngoài Git. Môi trường Windows, Python 3.13.7,
backend venv và dependencies hiện có; frontend dùng Vitest 4.1.11 theo lockfile.

## Phát hiện bàn giao #147/#149

Đối chiếu tĩnh phát hiện frontend feedback fetch `/openapi.json` từ API base,
nhưng nginx của #148 chỉ proxy `/api/` và `/healthz`; `/openapi.json` được xử lý
bởi SPA fallback. Hạ tầng healthy/API trực tiếp chưa chứng minh feedback qua
UI Docker hoạt động. [Guide](../guides/api-reproducibility-w7.md#giới-hạn-proxy-feedback-cần-theo-dõi)
đã có lệnh kiểm curl và phân biệt origin backend với proxy.

Đây là phát hiện từ code, **chưa tái hiện qua Docker/UI trong lượt này** vì
Engine chưa sẵn sàng. Không khẳng định đã sửa hoặc đã xác nhận lỗi live;
#147 cần repro/triage, phối hợp Khuê/Duy trước khi sửa runtime. Không âm thầm
mở rộng #145 thành sửa nginx/client hoặc tự tạo issue/comment trên GitHub.

## Review và giới hạn

- Duy: đối chiếu mode/client, query/filters/page/rank, upload, error mapping,
  runtime spec và feedback persistence discovery; chưa có xác nhận mới #145.
- Khuê: đối chiếu README/Compose/setup, giới hạn proxy, cách tách hạ tầng,
  API fixtures, service thật và evaluation; chưa có xác nhận mới #145.
- Chưa chạy lại PostgreSQL integration, model smoke, Docker clean setup,
  browser E2E hoặc benchmark. Bằng chứng các issue trước vẫn là lịch sử riêng.
- CI trên PR, approval và merge chưa thực hiện; không dùng tests local để
  tích các mục đó hoặc nghiệm thu toàn W7.
