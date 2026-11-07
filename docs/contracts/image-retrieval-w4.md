# Bàn giao retrieval ảnh TV3 — Issue #76

Code retrieval đã merge qua PR #83. API #80 sử dụng interface dưới đây;
hướng dẫn HTTP tại [image search API](../guides/image-search-api.md).
Đã đối chiếu contract upload trong PR #82 tại commit
`70e6f1c5f9f23c77741e11c75aa81efcb3fd08e7`.
Phần tích hợp #80 gọi method/output/lỗi dưới đây và ghi bằng chứng kiểm thử
trong hướng dẫn HTTP.

```python
ImageSearchService(encoder, store).search_image(
    image_bytes: bytes,
    filters: TextSearchFilters,
    *, candidate_limit: int = 200,
) -> TextSearchCandidates
```

## Input và preprocessing

- Nhận trực tiếp bytes gốc của helper `read_validated_image` trong #79/#82.
  Không nhận URL/path, `UploadFile` hay PIL object ở public method này.
- Service tự kiểm tra bytes để hỗ trợ caller ngoài HTTP: JPEG/PNG thực sự
  verify/decode được, tối đa 5 MiB, tối đa 4096 px mỗi chiều. Sau đó decode
  frame đầu, chuyển RGB, không tự xoay EXIF, không thay bytes của caller.
  Policy này giữ cách xử lý pixel CLIP/batch hiện có và có version riêng.
- Official processor theo pinned revision thực hiện resize/rescale/normalize
  của từng model; không dùng processor CLIP để encode SigLIP 2.
- `filters` tái sử dụng strict `TextSearchFilters`: AND trước retrieval,
  null không áp dụng; metadata thiếu không khớp điều kiện tương ứng.
- `candidate_limit` integer 1–200, không nhận bool. Mặc định 200 là cửa sổ
  bàn giao API theo W3, **chưa phải cutoff image benchmark đã được TV5 chốt**.
  Runner diagnostic dùng K=10 và ghi cấu hình thật.

## Output và lỗi đề xuất

Tái sử dụng schema đã có `TextSearchCandidates`, không tạo bản schema thứ hai:
`hits=[{asset_id, score}]`, `versions={model_version,index_version,
config_version,dataset_snapshot}`. Dù tên schema có chữ Text, đây chỉ là
danh sách ứng viên và provenance, không chứa text query hoặc HTTP response.

- Exact cosine trên toàn bộ point khớp filters của subset nhỏ; score hữu hạn
  trong [-1,1], không threshold; dedup lấy max score theo asset ID, sắp score
  giảm dần rồi asset ID tăng dần trước cắt cửa sổ. Không trộn score hai model.
- Query không tạo/upsert/rebuild collection, không ghi metadata/event/DB.
  Collection/model/dimension/revision/preprocessing/index payload phải khớp.
- Kết quả rỗng vẫn có versions thật. API #80 phụ trách mapping metadata DB,
  đối chiếu ID, pagination/total/rank và lưu event; chưa triển khai ở #76.
- `InvalidQueryImageError.code`: `INVALID_IMAGE`, `UNSUPPORTED_IMAGE`,
  `IMAGE_TOO_LARGE`, `IMAGE_DIMENSIONS_EXCEEDED`; TV1 có thể map HTTP 400.
- `pydantic.ValidationError` cho filters và `ValueError` cho candidate_limit
  sai; API validate/mapping như W3, không bỏ qua filter.
- `SearchUnavailableError.reason` khi model/index/Qdrant chưa sẵn sàng hoặc
  sai compatibility. Cùng lớp lỗi được re-export từ `app.search.text_search`
  để giữ adapter W3 tương thích; TV1 cần map 503 `SEARCH_UNAVAILABLE` ở #80.
  Message cố định, không chứa exception gốc/đường dẫn/credentials.

## Model/index

| Model | Revision | Dimension | Processor | Preprocessing |
|---|---|---|---|---|
| openai/clip-vit-base-patch32 | 3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268 | 512 | CLIPProcessor, use_fast=False | clip-slow-processor-rgb-l2-v1 |
| google/siglip2-base-patch16-224 | 75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2 | 768 | AutoImageProcessor → SiglipImageProcessor, use_fast=False | siglip2-fixres-slow-processor-rgb-l2-v1 |

SigLIP 2 checkpoint FixRes có `model_type=siglip`; dùng `AutoModel` để chọn
đúng class, không ép `Siglip2Model` dành cho cấu hình NaFlex. Dùng ảnh features
L2 + cosine; không dùng sigmoid logits như xác suất relevance.
Nguồn: [pinned config](https://huggingface.co/google/siglip2-base-patch16-224/blob/75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2/config.json),
[pinned processor](https://huggingface.co/google/siglip2-base-patch16-224/blob/75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2/preprocessor_config.json).

Encoder được caller nạp một lần, inference mode và batch ảnh; chưa thêm
runtime HTTP hoặc cơ chế concurrent request cho image service ở #80.
Qdrant local storage chỉ mở bằng một process; caller không mở index cùng lúc.

`ImageIndexManifest` (`image-index-manifest-v1`) riêng với manifest text W3:
source/ready hashes, snapshot, processor class/config/revision, normalization,
similarity, named vector, collection, count, packages, code SHA/module hashes,
dirty flag, retrieval policy và link xác nhận snapshot. Named vector CLIP cũ
giữ nguyên; SigLIP 2 có prefix/hash riêng. Mỗi lượt build có thư mục/collection
storage riêng, không ghi đè index đã có. Đổi model cần encode/rebuild riêng.

## Snapshot và phối hợp

- TV1: xác nhận method nhận bytes, output, lỗi và candidate window trước nối #80.
  Contract multipart #79/#82 có sẵn, không suy ra live image response đã chốt.
- TV2 đã [xác nhận snapshot W4](https://github.com/Q-Anh2610/SE2026-T03/issues/76#issuecomment-6702522644) ngày 07/11/2026:
  `home-interior-354-v1`, gồm 200 asset mốc + 154 asset bổ sung, dùng cùng ảnh
  cho hai index CLIP/SigLIP 2 riêng. Source SHA-256:
  `93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614`;
  ready SHA-256:
  `7d0a3e59f4d1c697cb37fd8b82decea3ba3efa95d8c84235bda73b5afb67474c`.
  Checksum từng preview theo provenance của gói đã bàn giao ở #62.
  TV2 xác nhận 354 preview đọc được, không trùng asset ID, cặp source/source_id
  hoặc checksum ảnh; chưa xác nhận dedup hình dáng/mesh. Danh mục chưa cân bằng,
  chi tiết theo curation. Benchmark text bộ 200 giữ nguyên. Đã có căn cứ để
  kiểm tra input rồi build index W4, không coi đây là bộ image benchmark đã khóa.
- TV5: image queries và provenance/checksum, qrels/same-ID targets, split
  validation/test, cutoff, filters, quy tắc self-match, timing và raw result format.
  Không dùng self-preview smoke làm bằng chứng chất lượng/metric benchmark.
- W3 #60 đã có review interface của TV1:
  [phản hồi trực tiếp](https://github.com/Q-Anh2610/SE2026-T03/issues/60#issuecomment-6635198504).
  Chưa tự thay checklist GitHub trong phiên này.

Xem [hướng dẫn runner](../guides/image-retrieval-w4.md) để chạy lại.
