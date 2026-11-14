# Explanation text/image search W5 — Issue #116

Owner backend: Quỳnh Anh. Review semantics retrieval: Chi. Bên nhận UI: Duy.
Contract dưới đây đã triển khai local; **chưa có xác nhận tiếp nhận riêng cho
#116 của Chi/Duy**. Không coi tests hoặc tài liệu là approval của owner.

## Đầu vào và phạm vi

CLIP text/image service, mapping metadata PostgreSQL, search events và hai
runtime adapter đã có từ #63/#65/#76/#80. Frontend hiện đọc explanation dạng
chuỗi và retrieval_sources dạng mảng. Không cần chờ dữ liệu mới hoặc build
E5 để làm explanation cho baseline này.

Theo trao đổi tại #91, E5/RRF vẫn ở service thử nghiệm; CLIP giữ mặc định.
Kết quả validation #91 không tự thay shared HTTP API/runtime/search events.
#116 không bật E5, SigLIP2, fusion, không sửa retrieval/index hoặc benchmark.

## Request và response

Giữ nguyên routes và request:

- `POST /api/v1/search/text`: JSON query/filters/page/limit.
- `POST /api/v1/search/image`: multipart image/filters/page/limit.

Response `mock=false` bổ sung **`results[i].score_type="cosine"`**.
Các trường cũ và hình dạng explanation chuỗi giữ nguyên. Không thêm migration,
dependency hoặc thay đổi versions/event schema.

| Trường | Text | Image |
|---|---|---|
| retrieval_sources | `["clip_text_to_preview"]` | `["clip_image_to_preview"]` |
| score_type | `"cosine"` | `"cosine"` |
| score | Cosine giữa embedding văn bản và ảnh preview | Cosine giữa embedding ảnh truy vấn và ảnh preview |
| explanation | Mô tả so khớp văn bản/preview | Mô tả so khớp ảnh/preview |
| versions | Model/index/config/dataset thực sự từ service | Cùng quy tắc, lấy từ luồng image thực tế |

Ví dụ các trường của một kết quả text (minh họa cấu trúc, không phải kết quả
đo quality):

```json
{
  "score": 0.25,
  "score_type": "cosine",
  "retrieval_sources": ["clip_text_to_preview"],
  "explanation": "CLIP so khớp văn bản truy vấn với ảnh preview; xếp hạng theo cosine giảm dần. Điểm cosine không phải xác suất hay phần trăm chính xác."
}
```

Image dùng cùng cấu trúc, source `clip_image_to_preview`, explanation:

> CLIP so khớp ảnh truy vấn với ảnh preview; xếp hạng theo cosine giảm dần.
> Điểm cosine không phải xác suất hay phần trăm chính xác.

Response đầy đủ và ví dụ hợp lệ nằm trong OpenAPI: `openapi-text-search.json`,
`openapi-image-search.json`, `openapi-feedback.json`. `openapi.json` mặc định
vẫn mô tả search mock. JSON Schema W3 được xuất lại theo model mới tại
`docs/contracts/text-search-w3.schema.json`.

## Ý nghĩa score, thứ hạng và giới hạn explanation

- Giữ nguyên giá trị cosine service trả về trong [-1,1], bao gồm số âm và 0;
  API không nhân 100, không scale sang [0,1], không làm tròn để xếp lại hạng.
- Score cao hơn đứng trước; hòa score theo asset ID tăng dần. Chỉ diễn giải
  so sánh trong cùng query/model/index/config. Không coi score text và image,
  hoặc score của hai model khác nhau, là một thang xác suất chung.
- Retrieval dùng filters/dedup trước cửa sổ tối đa 200 ứng viên. API giữ thứ tự,
  phân trang và đánh rank lại từ 1 trên mỗi trang theo contract hiện có.
- Explanation mô tả tín hiệu đã dùng, không giải thích nhân quả vì sao một
  điểm ảnh/đặc điểm cụ thể khiến mô hình chọn asset. Không suy diễn mesh,
  độ chính xác, license, hình học hoặc metadata thiếu từ score.
- Filters category/license/formats/face_count dựa trên metadata, không phải
  tín hiệu semantic được bịa vào explanation. Bản này không thêm matched-tags,
  caption, token attribution hay contribution khi service không cung cấp.
- Model/index/config/dataset lấy nguyên từ candidates. Không điền versions
  mock hoặc versions của model đang thử vào kết quả CLIP thật.
- Empty/trang ngoài phạm vi: `results=[]`, giữ pagination/versions và ghi event
  như trước; không tạo kết quả hoặc explanation giả để lấp chỗ trống.
- Mapping không hợp lệ: 500 `INTERNAL_ERROR` an toàn, không commit search event.
  Index/dependency chưa sẵn sàng vẫn là 503; không fallback mock.
- DTO fusion không tương thích bị từ chối ở biên service. Không ép RRF score
  thành cosine dù giá trị số tình cờ nằm trong [-1,1]. Việc tích hợp fusion sau
  này cần DTO/contract được review riêng.

Mock vẫn dùng SearchResult riêng, score null và lời giải thích rõ là minh họa;
không bổ sung score_type cosine cho response mock.

## Bàn giao cho Duy

- Các trường explanation/retrieval_sources/score/versions vẫn ở vị trí cũ.
  Parser hiện tại chấp nhận trường bổ sung; không cần đổi shape explanation
  thành object hoặc đổi API client để tiếp tục đọc dữ liệu cũ.
- Khi cập nhật TypeScript dùng chung mock/live, có thể bổ sung
  `score_type?: 'cosine'`; response backend live mới luôn xuất trường này.
  Nếu thêm kiểm tra bắt buộc cho live, cập nhật fixtures/tests tương ứng.
- Hiển thị nhãn nguồn phù hợp cho text/image. Render explanation như text;
  có thể xem trong phần Chi tiết hiện có của AssetCard.
- Nếu hiển thị score, dùng nhãn **Điểm cosine**, giữ số thập phân và số âm;
  không nhân 100, thêm dấu `%` hoặc gọi là độ chính xác.
- Empty/error/retry tiếp tục theo contract cũ; giữ versions để truy vết.
- Tests parser/AssetCard hiện có không thay smoke UI nối backend mới; Duy cần
  xác nhận tiếp nhận và ghi kiểm chứng UI trong phần việc frontend.

## Chạy lại kiểm chứng

Từ `backend/`, dùng PostgreSQL test riêng `test_*`, cấu hình
`TEST_DATABASE_URL` trong môi trường terminal, không commit URL/credentials:

```powershell
.\.venv\Scripts\python.exe -m app.export_openapi
.\.venv\Scripts\python.exe -m app.export_text_search_contract
.\.venv\Scripts\python.exe -m pytest tests/unit/test_search_explanation.py tests/unit/test_text_search_contract.py tests/unit/test_text_search_api.py tests/unit/test_image_search_api.py tests/unit/test_feedback_api.py tests/unit/test_mock_api.py tests/unit/test_openapi.py tests/unit/test_text_search_runtime.py tests/integration/test_search_explanation_stack.py tests/integration/test_text_search_stack.py tests/integration/test_image_search_stack.py tests/integration/test_text_search_bootstrap.py tests/integration/test_feedback_stack.py tests/integration/test_search_events.py -q
```

Integration dùng PostgreSQL thật và retrieval fixtures để kiểm mapping/rollback;
không gọi đó là kiểm chứng chất lượng model. Smoke CLIP/Qdrant thật dùng lại
verifier #80 với assertion #116 cho hai luồng; từ gốc repo:

```powershell
.\backend\.venv\Scripts\python.exe scripts/verify_image_search_api.py --index-manifest data/processed/issue65/index-1718ec3c49a0/index-manifest.json --index-root data/processed/issue65/index-1718ec3c49a0 --qdrant-local-path data/processed/issue65/index-1718ec3c49a0/qdrant --image-index-manifest data/processed/issue76/clip-build-16556914413d/index-manifest.json --image-index-root data/processed/issue80/inputs-cfd29f05b4 --image-qdrant-local-path data/processed/issue76/clip-build-16556914413d/qdrant --output data/processed/issue116/search-explanation-http.json
```

Các đường dẫn index ở trên là gói local đã có trên máy tác giả; máy khác phải
nhận đúng gói rồi thay đường dẫn. Không tải thêm model hoặc dựng index chỉ
để chạy unit tests. Verifier tạo/xóa schema test riêng, không ghi DB phát triển;
kiểm fingerprint hai storage trước/sau. Không mở cùng storage local ở process
API khác trong lúc kiểm chứng. Bằng chứng smoke và giới hạn được ghi ở
[báo cáo #116](../evidence/issue116-search-explanation.md).

## Checklist xác nhận còn chờ

- [ ] Chi xác nhận cosine [-1,1], sources text/image, versions và giới hạn
  explanation phù hợp baseline; chưa tích hợp RRF vào HTTP contract.
- [ ] Duy xác nhận tiếp nhận score_type bổ sung, explanation chuỗi, cách hiển thị
  nguồn và score; UI E2E/smoke được ghi riêng.
- [ ] CI/reviewer khác tác giả/merge theo PR thực tế, không suy ra từ tests local.
