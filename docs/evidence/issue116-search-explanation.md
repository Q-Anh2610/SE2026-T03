# Kiểm chứng explanation text/image — Issue #116

Ngày 14/11/2026. Nhánh local `feat/116-search-explanation`, base commit
`112df084f2424ee5d980d9fa55ab01aef45dd5b9`, có thay đổi chưa commit khi đo.
Không gán kết quả này thành CI hoặc xác nhận của Chi/Duy.

Contract và lệnh tái lập: [search-explanation-w5.md](../contracts/search-explanation-w5.md).

## Tests

| Phạm vi | Kết quả | Ý nghĩa |
|---|---|---|
| Nhóm backend API/schema/OpenAPI/runtime/mock/feedback và PostgreSQL integration tại contract | 190 passed, không skip, 21,73 giây | Mapping text/image, scores âm/0, versions, empty/page, lỗi mapping không commit event, hồi quy search/feedback |
| Frontend contract, AssetCard và image client hiện có | 179 passed trên 3 files, 8,28 giây | Hồi quy parser/component hiện hành; không thay cho UI E2E nối API mới |
| Export OpenAPI và JSON Schema W3 | Đạt; tests kiểm spec/schema/examples đạt | LiveSearchResult có score_type cosine, mock giữ schema riêng |
| git diff --check | Đạt | Không có lỗi whitespace trong diff tracked |

Lệnh frontend chạy tại `frontend/`:

```powershell
npm exec vitest run src/features/search/contract.test.ts src/features/search/AssetCard.test.tsx src/features/search/image/client.test.ts
```

Tests tích hợp dùng PostgreSQL thật với retrieval fixture có nhãn rõ; riêng
bootstrap có Qdrant thật/encoder fixture. Tests xác nhận DTO RRF không tương
thích bị từ chối trước DB. Không dùng fixture tests để tuyên bố relevance tốt
hơn, hoặc xác nhận đã tích hợp fusion vào HTTP API.

## Smoke HTTP/model/index thật

Report quan sát tại `2026-11-14T16:40:30.054114+00:00`, status **passed**.
Python 3.13.7; Uvicorn qua TCP localhost; PostgreSQL test_* trong schema UUID
riêng; CLIP CPU offline từ cache và hai Qdrant local storage hiện có.
Không tải lại model/dataset, không seed vào database phát triển.

| Thành phần | Phiên bản/đầu vào thực tế |
|---|---|
| Model | `openai/clip-vit-base-patch32@3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268` |
| Snapshot | `home-interior-354-v1`, 354 asset |
| Source SHA-256 | `93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614` |
| Text index | `issue65-home-interior-354-v1-clip-v1` |
| Text config | `clip-text-exact-all-filtered-v1-k200` |
| Image index | `issue76-clip-build-16556914413d` |
| Image config | `image-exact-all-filtered-rgb-v1-k200` |

Đã kiểm chứng:

- HTTP text/image trả `score_type=cosine`, đúng retrieval_sources và explanation
  của từng luồng. IDs, rank, pagination/filters/detail khớp candidates/metadata.
- Versions response khớp manifest/service thực tế và search event PostgreSQL.
- Text có 5 event, image có 7 event, tổng 12 event thành công; empty/trang vượt
  phạm vi vẫn có event theo contract. Không có explanation/result giả ở trang rỗng.
- Validation 400, index ảnh không sẵn sàng 503, ghi event ảnh lỗi 500 và request
  sau phục hồi đạt. Dòng log IntegrityError trong smoke là lỗi chủ động tạo ở
  schema test để kiểm rollback; không phải lỗi bị bỏ qua.
- So score của HTTP với lời gọi service trực tiếp. Đây là hai lần inference
  độc lập ở các thread khác nhau: dùng tolerance cosine có sẵn `1e-6`, không
  bắt float bit-identical giữa hai lần chạy. Sai số text lớn nhất đo được
  `1.1102230246251565e-16`; mapping fixture giữ nguyên score chính xác.
- Cả hai storage vẫn 354 points sau đóng/reopen; fingerprint trước/sau không đổi:
  text `4ec8a57d3532cb126ebca29d818d6e85aa1c36231eb88b2d208f6101b559c687`,
  image `e17e9c523799dfa35bbe2a9ea50e7787e380031a24a35afec57e8d6812348f8f`.

Runtime report đầy đủ cùng module hashes nằm ở
`data/processed/issue116/search-explanation-http.json`, giữ ngoài Git.
Verifier và lệnh tái lập được chia sẻ trong repo. Server đã dừng, schema và DB
test tự sinh đã dọn sau lượt kiểm chứng; không chuyển active index.

## Giới hạn và việc còn chờ

- Đây là kiểm chứng backend HTTP/DB/local Qdrant/CLIP. Query ảnh là preview đã
  có trong index, chỉ phục vụ diagnostic; không phải image benchmark có nhãn.
- Không chạy lại toàn bộ backend suite trong #116; đã chạy nhóm 190 tests chịu
  ảnh hưởng. Không chỉnh raw query/qrels/hash benchmark hoặc kết quả #91.
- Không chạy benchmark quality/latency mới, không bật E5/RRF/SigLIP2.
- Frontend source không thay đổi; Duy còn cần tiếp nhận contract và kiểm chứng
  UI với backend mới. Chi còn cần xác nhận semantics score/nguồn của #116.
- CI/review/merge ghi theo PR thực tế sau khi người dùng push; chưa có các xác
  nhận đó trong bằng chứng local này.
