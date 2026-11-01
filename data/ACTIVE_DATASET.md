# Dataset đang sử dụng

Snapshot: `home-interior-clear-200-v3`, gồm 200 asset và 200 preview khác nhau, chia thành 28 nhóm đồ nội thất và thiết bị trong nhà. Ưu tiên vật thể dễ nhận ra và kiểu dáng hiện đại. Việc chọn ảnh được AI kiểm tra trực quan qua bảng ảnh và lượt xem ảnh lớn; chưa có xác nhận duyệt toàn bộ của người khác.

## Thành phần

- `manifests/objaverse_200.json`: manifest ingestion chính, giữ metadata và category từ nguồn.
- `manifests/objaverse_200.annotations.json`: annotations gốc, giữ tác giả, license và mô tả đa ngôn ngữ.
- `manifests/objaverse_200.provenance.json`: revision nguồn, checksum manifest/annotations và checksum, URL, kích thước từng preview.
- `manifests/objaverse_200.curation.json`: nhóm đồ vật sau kiểm tra ảnh; tách riêng để không sửa sai metadata nguồn. Đường dẫn preview tính từ gốc repo.
- `raw/objaverse/previews/`: ảnh local, được Git bỏ qua. Preview không phải mesh GLB; checksum ảnh không chứng minh checksum mesh.

Manifest chính giữ contract của Objaverse Source Adapter. Không tự đưa category kiểm duyệt vào PostgreSQL hoặc Qdrant; thay đổi phân loại nghiệp vụ cần phối hợp owner API/search.

## Tải trên máy khác

Chạy từ gốc repo, sau khi cài môi trường backend:

```powershell
$runTag = Get-Date -Format "yyyyMMdd-HHmmss"
.\backend\.venv\Scripts\python.exe -m backend.app.ingestion.cli --manifest data/manifests/objaverse_200.json --output-dir data/raw/objaverse/previews --report "data/processed/ingestion/clear200-$runTag.json"
```

Đối chiếu kết quả và SHA-256 ảnh với provenance trước khi dùng. URL bên ngoài có thể hết hạn hoặc đổi nội dung; bản ZIP bàn giao chứa đúng ảnh đã kiểm tra giúp khôi phục snapshot. Không commit ảnh, ZIP, báo cáo runtime hoặc `.env` vào Git.

Nếu có sẵn ảnh và báo cáo tải cùng snapshot, thêm `--previous-report` trỏ tới báo cáo đó và dùng tên `--report` mới. Chỉ thêm `--persist-db` khi `.env` đã trỏ đúng PostgreSQL local cần nhập; Git không mang theo database. Khi thay bộ cũ trên một máy khác, lưu bản sao riêng trước và kiểm tra lại toàn bộ asset IDs; upsert không tự xóa asset cũ ngoài manifest.

## Bằng chứng và giới hạn

- Unit tests ingestion kiểm tra 200 records khớp annotations nguồn và provenance; hash manifest phải khớp nội dung file.
- Trên máy local của Huyền, kết quả được cung cấp qua terminal/ảnh chụp: nhập lại lưu 200 asset, không tăng bản ghi; SQL có 200 IDs và 200 cặp nguồn duy nhất, trạng thái `downloaded`.
- Kiểm tra API do Huyền chạy: tổng 200, 200 IDs duy nhất, chênh lệch với manifest bằng 0, `mock: false`. Đây là kiểm tra local, không phải kết quả CI.
- Qdrant chưa được rebuild cho snapshot này; không đánh dấu `searchable`. Owner embedding/search cần tạo lại index và đối chiếu asset IDs trước khi dùng kết quả tìm kiếm.
- Báo cáo W1/W2 trong README thuộc snapshot cũ. Không dùng chúng làm bằng chứng cho snapshot mới; nhãn benchmark cũ cũng cần rà soát lại.

Để hoàn tác phần metadata trong Git, dùng quy trình revert commit qua PR; ảnh local, PostgreSQL và Qdrant cần khôi phục riêng từ bản sao phù hợp, không được phục hồi tự động bởi Git.
