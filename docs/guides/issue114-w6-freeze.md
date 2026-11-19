# Kiểm tra và bàn giao cấu hình W6 — #114

[ADR 0001](../adr/0001-w6-retrieval-config.md) ghi quyết định được Khuê/Quỳnh Anh phản hồi ngày 19/11/2026. Text chọn CLIP+E5/RRF k=20; ảnh giữ CLIP với pins benchmark candidate200. Freeze không tự đổi shared API/runtime hoặc chứng minh đáp ứng HTTP latency target.

## 1. Xác định đúng artifact

- File: `evaluation/configs/issue114-w6-retrieval.frozen.json`.
- Schema: `issue114-frozen-retrieval-v1`.
- Version: `w6-clip-e5-rrf-k20-candidate200-v1`.
- SHA-256 raw: `1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5`.
- Sidecar: `evaluation/configs/issue114-w6-retrieval.frozen.sha256`.

Hash phải đối chiếu với artifact/commit đã review và bàn giao; tự tính hash của file đang đọc hoặc thay cả file lẫn sidecar không chứng minh approval. Commit chứa artifact được ghi ngoài JSON trong comment bàn giao, tránh self-reference. Khi thay lựa chọn/pins, tạo version/hash/decision mới có giải thích; không âm thầm chỉnh bản đã bàn giao.

Artifact UTF-8 không BOM, LF, một LF cuối. E5 snapshot manifests trong `evaluation/configs/issue114/` là raw copies, không sửa provenance/status lịch sử. Không đổi EOL/pins của W5 để ép checker đạt. Không dùng config `.draft.json` được trao đổi ngoài repo hoặc config input-confirmed #91 thay bản này.

## 2. Kiểm tra tracked pins, không nạp model

Từ gốc repo, sau khi có các file #114:

```bash
backend/.venv/Scripts/python.exe -B scripts/verify_issue114_frozen_config.py --repo . --expected-sha256 1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5
```

Kỳ vọng `status=frozen_config_verified`, mode `clip_e5_rrf`, rank_constant 20, source limits/cutoff 200, `models_loaded=false`, `benchmark_executed=false`, `test_authorized=false`. Exit 2 khi hash/bytes/schema/policy/pin/dependency không hợp lệ; không fallback sang mode khác.

Trên máy có local inputs đúng pins, bổ sung kiểm raw local manifests/corpus/input bytes:

```bash
backend/.venv/Scripts/python.exe -B scripts/verify_issue114_frozen_config.py --repo . --expected-sha256 1e1962058528e22b5235d989a3613b5077c02d479b8ac19e8dbc28fee0bd08d5 --local-inputs
```

Kỳ vọng thêm `local_inputs_verified=true`. Đây vẫn không mở Qdrant storage hoặc nạp weights; `live_qdrant_verified=false`. Các source factories/services gốc phải kiểm cache/model/index readiness trước benchmark. Máy chưa có dependencies local sẽ bị chặn; không chép đè index, tải weights hoặc dựng index mới chỉ để làm checker xanh.

Các root local được pin trong artifact; nếu cần bố trí khác, phối hợp trước, ghi config version/pins/commands tương ứng. Không chuyển sang snapshot 354 hoặc corpus mới mà vẫn gọi cùng phép so sánh.

## 3. Unit tests phù hợp thay đổi

```bash
backend/.venv/Scripts/python.exe -B -m pytest -c backend/pytest.ini backend/tests/unit/test_issue114_frozen_config.py backend/tests/unit/test_rrf.py -q -p no:cacheprovider
```

Tests kiểm artifact hash bên ngoài, schema/status, model/tokenizer/index/corpus mismatch, params/filters/source/order/dedup policy, đường dẫn/dependency, EOL/duplicate JSON, lỗi CLI và gọi RRF implementation hiện có trên ví dụ nhỏ biết đáp án. Local input fixtures được tạo giả, không cần index/corpus/model cache riêng của Chi trong CI. Không dùng kết quả unit tests làm bằng chứng chất lượng model hoặc latency.

## 4. Bàn giao trước test

Chi đăng bằng chứng gồm ADR, file config + sidecar + SHA-256 + commit thật, PR/checks/review hiện tại, các lệnh ở trên và references tới báo cáo/evidence/raw W5. Không điền commit giả hoặc dùng approval W5 thay approval thay đổi #114.

Raw W5: [bàn giao ZIP](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6872346483), [Khuê xác nhận](https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-6872477076), [báo cáo](../evaluation/issue91-e5-rrf-validation-20261114.md), [grid evidence](../evidence/issue91-e5-rrf-validation-20261114.json), [archive evidence](../evidence/issue105-archive-metrics-review-20261116.json).

Khuê đối chiếu config/hash/commit, protocol và dependencies, phản hồi tiếp nhận trước test. Nếu review chưa xong hoặc thiếu dependency, giữ test chưa sẵn sàng. CLI không tự xác thực GitHub/approval/merge.

Đối với consumer do Khuê chuẩn bị, đọc qua loader và truyền `frozen.rrf_config` vào `ExperimentalFusionService.search_text` hiện có, cùng `frozen.filters`; source roots lấy từ cùng đối tượng. Loader chỉ hỗ trợ mode/k/policies của version này. Không dùng một retrieval implementation khác hoặc tự đổi các params để chạy cho tiện. Image dùng service hiện có, CLIP/index pins của artifact, candidate_limit 200.

**Không có lệnh benchmark test mới được tạo trong #114.** Runner `run_e5_rrf_validation.py` của #91 chỉ chạy validation; không sửa nó thành test hoặc giả rằng một CLI test đã tồn tại. Entry point test thuộc phần Khuê, phải dùng cấu hình này và implementation hiện có sau gate review/handoff.

Protocol cần giữ: cùng query/qrels/split/candidate pins và filters, binary relevance >=1, Recall@5/10 và binary nDCG@10/Hit@5/10 theo split thích hợp; latency ghi máy/phạm vi/p50/p95/raw samples/errors riêng. 21/28 và 7 no-positive là thống kê validation, không hardcode làm mẫu số test. Với ảnh similarity không áp dụng Hit@K same-ID; không suy quality ảnh từ text/smoke. Điều kiện timing mới phải ghi trước lượt đo, không gộp với raw W5 như cùng run.

Mọi kết quả test báo cáo riêng, không chọn lại model/k/passage/filters/ngưỡng. Nếu có lỗi thực sự, ghi lỗi/version/ảnh hưởng đánh giá trước khi sửa; không dùng test để chọn cấu hình tốt hơn. Ngân sách/kiểm chứng HTTP-end-to-end trên máy demo vẫn cần chốt riêng trước nghiệm thu vận hành.
