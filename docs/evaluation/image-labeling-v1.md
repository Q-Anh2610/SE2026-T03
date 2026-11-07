# Chấm nhãn ảnh W4 — Issue #89

Tập cần chấm gồm **20 query ảnh similarity × 200 asset = 4.000 cặp cho mỗi người**.
Hai người chấm độc lập: Đoàn Thị Minh Khuê và Trịnh Thị Thu Huyền.
Không trao đổi hoặc nạp file điểm của người còn lại trước khi cả hai hoàn tất.

## Bắt đầu

Mở [`annotator.html`](../../data/benchmark/annotator.html) bằng Chrome hoặc Edge.
Nạp các đầu vào sau từ thư mục gốc repository:

| Ô trên giao diện | File hoặc thư mục cần chọn |
|---|---|
| Queries CSV | `data/benchmark/image_queries_v1.csv` |
| Candidate assets CSV | `data/benchmark/candidate_assets.csv` |
| Query images folder | `data/benchmark/query_images/source_candidates/` |
| Preview images folder | `data/benchmark/objaverse/previews/` |
| Annotator | Chọn đúng tên của mình |

Ảnh query xuất hiện bên trái; preview asset xuất hiện bên phải. Gợi ý metadata
được bật mặc định theo yêu cầu: so khớp phần Target object: trong ghi chú query
với tên asset, không phân tích nội dung ảnh. Xem cả hai ảnh và sửa điểm/ghi chú
theo bằng chứng thực tế trước khi lưu. Có thể bỏ chọn **Use metadata suggestions**
để chấm độc lập. Các file ảnh chỉ lưu local, không đưa vào Git.

## Chấm và lưu tiến độ

1. Xem đối tượng đích trong ảnh query, ghi chú query và preview asset.
2. Chọn `0` (không liên quan), `1` (liên quan một phần) hoặc `2` (trực tiếp phù hợp)
   theo [quy trình relevance](benchmark-labeling.md). Đây là similarity,
   không mặc định cùng ID là đáp án.
3. Ghi bằng chứng ngắn vào **Evidence note**, rồi bấm **Save score and next**.
   Khi con trỏ đang ở ô ghi chú, Enter xuống dòng; dùng nút để lưu.
4. Nếu chưa đủ bằng chứng, dùng **Skip without label**; bỏ qua không có nghĩa là điểm 0.
5. Bấm **Download labels CSV** thường xuyên và trước khi đóng/tải lại trang.
   Trang giữ tiến độ trong bộ nhớ; cần xuất CSV để lưu bền vững.

Khi tắt gợi ý và chưa lưu nhãn có hỗ trợ, file xuất có tên:

- Khuê: `labels_image_v1_khue.csv`.
- Huyền: `labels_image_v1_huyen.csv`.

Để tiếp tục buổi sau, nạp lại bốn đầu vào, chọn đúng tên rồi nạp **file của chính
mình** vào **Previously saved labels CSV**. Trang chuyển tới cặp chưa chấm đầu tiên.
Mỗi lượt đầy đủ cần 4.000 cặp; giữ bản xuất mới nhất và sao lưu các bản trước đó.
Không đổi Annotator trong cùng một lượt chấm.

## Sau khi cả hai hoàn tất

Đặt hai file nhãn vào `data/benchmark/`, rồi chạy từ gốc repository:

```powershell
rtk proxy pwsh -NoProfile -File scripts/prepare_image_qrels_v1.ps1
```

Script kiểm tra 4.000 nhãn/người, ID thuộc tập ứng viên, không có cặp trùng,
đúng người chấm, điểm 0/1/2, bằng chứng và thời gian UTC hợp lệ. Điểm trùng nhau
thành `Agreed`; khác nhau thành `Unresolved` và để trống điểm. Script từ chối ghi
đè output đã tồn tại; nếu cần tạo lại, dùng `-OutputPath` tới file mới.
Lệnh trên dùng PowerShell 7 (`pwsh`); nếu chỉ có Windows PowerShell, có thể thay
`pwsh` bằng `powershell` trong môi trường hỗ trợ chạy script của repository.

Để adjudicate, mở [adjudicator.html](../../data/benchmark/adjudicator.html),
nạp hai file nhãn ảnh, queries ảnh, candidates và cả hai thư mục ảnh. Bấm
**Mở qrels / image_qrels_v1 CSV** và chọn trực tiếp image_qrels_v1.csv hoặc
image_qrels_v1.work.csv có đủ dữ liệu, rồi cấp quyền đọc/ghi. Không cần đổi tên
thành qrels.csv. File chỉ có header không đủ để đối soát.

Mỗi lần lưu quyết định, giao diện cập nhật đúng file đã chọn với trạng thái
Adjudicated, điểm cuối, ghi chú, người xác nhận và thời gian UTC. Hai file nhãn
nguồn giữ nguyên. Không ghi đè data/benchmark/qrels.csv: đó là nhãn text đã khóa.

Hai người cùng rà bất đồng và ghi lý do chốt điểm. Giữ nguyên hai file nhãn độc lập.
Query không có positive phải được rà lại và ghi nhận theo protocol, không tự thêm
positive. Với Issue #89, qrels cuối và split theo `query_group_id` được khóa trong
`image_benchmark_v1.yaml`; không tối ưu theo test split.

## Trạng thái ngày 08/11/2026

Hai lượt độc lập hoàn tất đủ 4.000 cặp/query mỗi lượt. Qrels cuối có 3.902 cặp
`Agreed`, 98 cặp `Adjudicated`, không còn `Unresolved`. Bộ 20 query có 20 group;
split cố định theo seed `8901` gồm 8 validation và 12 test. Hash khóa query, qrels
và split được ghi trong `image_benchmark_v1.yaml`.

Owner retrieval đã xác nhận preflight local cho CLIP và SigLIP 2 trên đúng 200
candidate IDs/checksum, cùng `filters={}`. Index version, report và giới hạn được
ghi trong manifest và [hướng dẫn preflight](../guides/image-index-preflight-89.md).
Đây chưa phải benchmark end-to-end: input, weights và Qdrant storage còn trên máy
owner; chưa chạy 20 query benchmark hoặc tính metric. Không dùng các smoke query
K=10 làm kết quả benchmark.
