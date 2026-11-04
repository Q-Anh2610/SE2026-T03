# CLIP text-to-preview retrieval - Issue #60

## Phạm vi và trạng thái

Service nằm ở `backend/app/search/text_search.py`, dùng encoder chung và
Qdrant store đã được khởi tạo. Đây là phần retrieval để TV1 tích hợp theo
`docs/contracts/text-search-w3.md`; chưa nối HTTP router hoặc search events.
Unit tests dùng encoder fixture và Qdrant memory. Smoke với CLIP thật và
Qdrant local lưu trên đĩa đã đạt trên snapshot `home-interior-354-v1`.

## Interface bàn giao TV1

```python
from app.schemas.text_search import TextSearchFilters
from app.search.text_search import TextSearchService, SearchUnavailableError

service = TextSearchService(encoder, store)
candidates = service.search_text(
    query="wooden chair",
    filters=TextSearchFilters(format="glb"),
    candidate_limit=200,
)
```

Caller nạp encoder một lần, tái sử dụng cùng service/store trong tiến trình.
`TextSearchCandidates` chứa `hits=[{asset_id, score}, ...]` và `versions` theo
schema `app.schemas.text_search`. `candidate_limit` là integer 1-200, mặc định
200. API nhận toàn bộ cửa sổ này rồi mapping DB và chia trang; không truyền
limit của từng trang vào service. Service không tạo event hoặc HTTP response.

Query trim, 1-500 Unicode code points; không dịch hay bỏ dấu. Encoder dùng
processor/tokenizer cùng model/revision đã pin. Truy vấn dài được truncate
theo `model.config.text_config.max_position_embeddings` (checkpoint CLIP
baseline là 77 token, gồm special tokens). Chuỗi query để echo/lưu event vẫn
là query đã trim, không phải chuỗi được dựng lại từ token đã cắt.

## Filters, ranking và versions

- Tái sử dụng `TextSearchFilters`: category/license khớp chính xác sau trim,
  format thuộc mảng formats, face_count có cận bao gồm. Kết hợp AND.
- Filter null/bỏ qua không áp dụng; metadata thiếu/null không khớp filter
  tương ứng. Không suy mặt từ tam giác. Filter sai bị validation từ chối.
- Qdrant nhận filters trước khi tính và chọn các điểm khớp. Query dùng named
  vector của store và `SearchParams(exact=True)`, không đặt score threshold.
- Score cosine lớn hơn tốt hơn, âm vẫn hợp lệ; không phải xác suất đúng.
  Sai số số thực vượt biên +/-1 trong phạm vi `1e-6` được chặn về biên;
  score không hữu hạn hoặc vượt dung sai là lỗi index.
- Gom theo asset_id, giữ score cao nhất; sắp score giảm dần rồi asset_id tăng
  dần; cuối cùng cắt `candidate_limit`. IDs phải dùng được với asset detail.
- Model/index/dataset versions lấy từ IndexConfig thực tế của store.
  Config version là `clip-text-exact-all-filtered-v1-k<cap>`; cap mặc định 200.

## Chi phí và tính nhất quán

Baseline cho subset nhỏ đọc exact count và toàn bộ points khớp filter qua
Qdrant, gồm cả những points hòa ở biên top 200. Nhờ vậy dedup và tie-break
diễn ra trước khi cắt cửa sổ, không chỉ sort lại một tập top K tùy ý.
Chi phí truy vấn, truyền payload và bộ nhớ tăng theo số point khớp (M),
sort tối đa O(M log M). Đây chưa phải chiến lược cho index lớn.

Không ghi dữ liệu, không tạo collection, không embed lại ảnh asset.
`QdrantStore.validate_collection()` chỉ đọc; đường ingestion vẫn dùng
`ensure_collection()` để tạo khi cần. Service kiểm tra model/revision/dimension/
preprocessing với config, named vector/schema và versions trong payload trả về.
Không thêm version filter để âm thầm bỏ payload sai phiên bản.

Index cần ổn định trong lúc chạy. Count không khớp số point truy vấn trả về
thì service báo unavailable (có thể do dữ liệu đổi hoặc point thiếu vector).
Đây không phải snapshot transaction: hai lần ghi giữ nguyên số lượng vẫn có
thể không được phát hiện. Không hứa phân trang bất biến qua các request hoặc
kiểm tra payload của asset bị loại bởi filter. Smoke/manifest cần audit toàn
collection và đối chiếu snapshot trước tích hợp.

## Lỗi và trách nhiệm tích hợp

`SearchUnavailableError` có message an toàn và `reason` chẩn đoán: encoder
không tương thích/không sẵn sàng, collection thiếu/sai cấu hình, Qdrant lỗi,
vector/score/payload/ID sai hoặc cửa sổ đọc không đầy đủ. Không trả rỗng hoặc
fallback mock khi gặp những lỗi này. TV1 map lỗi có kiểu sang HTTP 503 theo
contract; validation đầu vào map 400, lỗi code/persistence map 500.
Không log exception gốc, query hoặc thông tin kết nối nhạy cảm.

TV1 phụ trách khởi tạo dependency, mapping metadata DB, HTTP, pagination/rank,
event persistence và response explanation/source `clip_text_to_preview`.
Kết quả smoke trên 354 asset dùng để bàn giao service. Benchmark Recall/nDCG
dùng snapshot 200 asset đã khóa và cần lần chạy đánh giá riêng.

## Retrieval config và index manifest

`docs/configs/clip-text-exact-v1.json` lưu cấu hình baseline cap 200.
Model `app.search.retrieval_config.RetrievalConfig` dùng chung với service;
không nhận policy, threshold hay options chưa được implementation hỗ trợ.
`RetrievalConfig.for_limit(cap)` trả cấu hình và version đúng cap thực thi.

`app.search.index_manifest.IndexManifest` mô tả index đã quan sát, gồm:

- Collection/named vector và toàn bộ IndexConfig; tên vector phải khớp hash
  được tính cùng một hàm với QdrantStore, không thay thuật toán đặt tên cũ.
- Revision model/processor/tokenizer, dimension, preprocessing, RGB, slow
  processor, L2/Cosine, giới hạn token và retrieval config.
- Manifest nguồn/ready manifest với SHA-256. Dataset snapshot phải trỏ đúng
  hash manifest nguồn. Đường dẫn này tính từ gói bàn giao, không phải repo.
- Số asset/point đã kiểm chứng, thời điểm quan sát và tạo manifest UTC.
  Baseline single-preview yêu cầu một point mỗi asset; không có giá trị
  mặc định giả cho số lượng hoặc thời điểm.
- HEAD commit, cờ working_tree_dirty và module SHA-256 để truy vết cả code
  chưa commit đang dùng. Commit HEAD riêng lẻ không đại diện uncommitted diff.

`load_index_manifest(path)` validate trước khi dùng;
`save_index_manifest(manifest, path)` revalidate và chỉ tạo file mới, không
ghi đè evidence. `verify_input_hashes(handoff_root)` đối chiếu source/ready
hash với gói nhận được. Kiểm tra này chỉ xác nhận bytes input; smoke còn phải
audit IDs/payload/vector trong collection và checksum ảnh để điền số liệu.
`manifest.make_store(client)` không gọi server hoặc tạo collection;
`manifest.check_encoder(encoder)` kiểm tra compatibility, gồm token limit.

### Đối chiếu hai snapshot 200 asset

`data/ACTIVE_DATASET.md` hiện chỉ ra `home-interior-clear-200-v3`, hash manifest
repo là `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`.
Gói `objaverse200-handoff-20261029-231353` của #39 có hash
`b37947fd1f2201dacf92e657d0580981315dd6252ad785e60657f4c1fe595e4a`;
index cũ dùng collection `issue39_objaverse200_clip_v1` và named vector
`clip_c243769d0cc6846b`. Hai hash đã được đối chiếu bằng đọc file local.

Smoke index cũ phải dùng manifest/ready/preview trong gói bàn giao cũ.
Không dùng manifest hiện tại của repo để mô tả index cũ hoặc coi smoke cũ
chứng minh snapshot mới đã được index. Trước khi tích hợp API với bộ dữ liệu
mới, cần phối hợp TV1/TV2 đối chiếu snapshot/IDs và tạo index/version riêng
khi được giao; không xóa hoặc rebuild đè collection cũ.

## Kiểm tra unit từ gốc repository (Git Bash)

```bash
./backend/.venv/Scripts/python.exe -m pytest backend/tests/unit/test_index_manifest.py backend/tests/unit/test_text_search_service.py backend/tests/unit/test_qdrant_store.py -q
```

Các test dùng dữ liệu tự tạo, có kiểm tra tie-break trên 205 points, dedup
trước giới hạn, filters trước top K, score âm, versions, lỗi readiness và
truy vấn không sửa index memory. Chưa thay cho smoke CLIP/Qdrant server thật.

## Smoke với CLIP và Qdrant thật

`scripts/verify_issue60_text_retrieval.py` điều phối module `app.search.smoke`.
Script chỉ dùng các thao tác đọc Qdrant, không ghi PostgreSQL, tạo collection,
upsert, rebuild hay encode lại ảnh. Model được nạp một lần trên CPU bằng
`CLIPEncoder(local_files_only=True)` và `HF_HUB_OFFLINE=1` trong tiến trình
smoke. Thiếu cache đúng checkpoint thì báo lỗi ở stage model_cache; script
không tự tải model hoặc thay môi trường đang dùng.

Từ gốc repository (Git Bash), khi Qdrant local chứa index #39 đang chạy:

```bash
./backend/.venv/Scripts/python.exe -u scripts/verify_issue60_text_retrieval.py --handoff-root work/received-objaverse200-20261029-231353
```

Mỗi lần tạo một thư mục mới dưới `data/processed/issue60/smoke-<UTC>-<id>/`
với `report.json`; không ghi đè evidence có sẵn. Nếu tất cả kiểm tra đạt,
script ghi `index-manifest.json` và đọc/validate lại. Các file này là runtime
local đã được Git ignore, không tự biến thành bằng chứng đã review/commit.

Kiểm tra bao gồm:

- SHA-256 source/ready trong gói khớp reference evidence #39; đủ 200 IDs,
  metadata chính xác, 200 preview riêng biệt đúng checksum và decode được.
  Không so hash gói cũ với manifest snapshot mới trong repo.
- Audit toàn collection trước/sau: canonical point IDs, payload khớp metadata
  gốc và index versions; vector đúng named vector/dimension, hữu hạn và L2.
  Fingerprint gồm cả point IDs, payload và vectors phải không đổi.
- 10 cases: tiếng Anh/Việt không filter, category, license, format, min/max
  face_count, AND với cận min=max, filter rỗng và query 497 ký tự vượt token
  limit. Expected IDs được đối chiếu độc lập từ metadata gốc, không đoán từ ảnh.
- Một query chạy lại phải cho cùng thứ tự asset IDs và versions. Điểm cosine
  được so với sai số tuyệt đối tối đa `1e-12`. Báo cáo lưu đầy đủ
  IDs, scores, filter metadata, versions, số token và norm/dimension text vector.
  Không lưu embedding vectors hoặc coi những truy vấn này là ground truth.
- Source hashes trước/sau phải ổn định. Manifest có thời điểm/count thực đo,
  commit HEAD, dirty flag, module/script/config hashes và environment versions.

Acceptance chỉ đạt khi mọi check true và errors rỗng. Thiếu Qdrant/model,
snapshot/index không khớp hoặc audit sai làm script exit 1; không fallback
mock. Báo cáo ghi stage và mã lỗi an toàn, không in exception gốc/credentials.
Mỗi elapsed_seconds là thời gian quan sát của case, chưa phải benchmark latency.

Unit helper tests của runner #39 dùng ảnh nhỏ, encoder fixture và Qdrant
memory. Lệnh chạy từ gốc repo trong Git Bash.

```bash
./backend/.venv/Scripts/python.exe -m pytest backend/tests/unit/test_text_retrieval_smoke.py backend/tests/unit/test_clip_encoder.py backend/tests/unit/test_clip_text_encoder.py -q
```

## Index riêng cho gói 354 asset từ issue #62

Gói `home-interior-354-v1.zip` gồm 200 asset của `home-interior-clear-200-v3`
và 154 asset bổ sung. ZIP và các file bên trong đã được đối chiếu SHA-256.
Metadata của 200 asset mốc khớp manifest hiện tại của repo. Bộ benchmark
đã khóa vẫn dùng snapshot 200 asset được khai báo trong manifest benchmark.

Chạy từ gốc repo trong Git Bash, với checkpoint CLIP đã có trong cache local.

```bash
./backend/.venv/Scripts/python.exe -u scripts/verify_issue60_handoff_354.py --archive "$HOME/Downloads/home-interior-354-v1.zip"
```

Script kiểm tra SHA-256 của đúng ZIP đã đối chiếu, giải nén manifest, ready
records và previews vào thư mục runtime riêng dưới `data/processed/issue60/`.
Batch encoder tạo 354 vector preview bằng checkpoint đã pin. Qdrant local
lưu collection `issue60_home_interior_354_clip_v1` trên đĩa trong thư mục
của lần chạy. Mỗi lần chạy cấp thư mục mới. Smoke mở client mới khi audit
trước và sau retrieval để so fingerprint chính xác của point IDs, payload
và vectors đã lưu. Qdrant local 1.15.1 có thể chuẩn hóa vector trong bộ nhớ
khi tính cosine. Báo cáo lần chạy trên 354 asset phân biệt trạng thái đã lưu
với sai số điểm số khi truy vấn lại.

Các filter dùng metadata nguồn, kể cả `category` null. Smoke chạy 10 case,
đối chiếu các kết quả với metadata và kiểm tra giới hạn 200 ứng viên khi
có nhiều hơn 200 asset khớp filter. Báo cáo và index manifest ghi kết quả
Qdrant local. Kiểm thử HTTP Search API cần thực hiện ở môi trường tích hợp.

Lần chạy ngày 04/11/2026 đã encode thành công **354/354 asset** và đạt cả
**10 case**. Filter `category=architecture` trả 53/53, filter kết hợp với
`face_count_min=face_count_max=1958` trả 1/1, và filter danh mục vắng mặt trả
0. Truy vấn không filter trả 200 ứng viên trên 354 asset khớp. Query dài có
85 token trước truncation và được giới hạn ở 77 token.

Fingerprint của 354 point đã lưu khớp sau truy vấn. Query lặp lại giữ cùng
thứ tự asset và versions, với chênh lệch score tuyệt đối tối đa
`1.1102230246251565e-16`. Bằng chứng chia sẻ gồm [tóm tắt smoke](../evidence/issue60-home-interior-354-smoke.json)
và [index manifest](../evidence/issue60-home-interior-354-index-manifest.json).
Manifest ghi HEAD lúc chạy và SHA-256 của bytes từng module trong working
tree. Checkout với kiểu xuống dòng khác có thể làm đổi hash module.
Hai file bằng chứng JSON dùng LF để giữ checksum qua các lần checkout.
Báo cáo đầy đủ, previews và dữ liệu Qdrant nằm trong thư mục runtime đã được
Git ignore.
