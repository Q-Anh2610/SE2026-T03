# Quy trình benchmark và gán nhãn

Tài liệu này chốt quy trình thu thập query và relevance cho benchmark semantic search. Đây là đặc tả trước thu thập, không phải dữ liệu benchmark hay báo cáo kết quả.

## Quy mô và thành phần

Mục tiêu là **100 truy vấn**: **70 truy vấn text** và **30 truy vấn ảnh**. Con số này nằm trong khoảng ROADMAP (80–120 tổng, 60–80 text, 20–40 ảnh), chia đủ để báo cáo riêng hai modality nhưng vẫn khả thi cho hai người gán nhãn. Nếu nguồn asset không đủ cho một loại truy vấn, có thể điều chỉnh trong các khoảng ROADMAP; ghi số thực tế và lý do trước khi đánh giá, không thay đổi sau khi xem kết quả test.

Trong 30 truy vấn ảnh, đặt mục tiêu 15 `same_id` và 15 `similarity`. Mỗi truy vấn phải trỏ tới ảnh nguồn có provenance rõ. **Không dùng ảnh preview/index của chính asset làm query cho toàn bộ tập ảnh**: ưu tiên ảnh khác góc/render hoặc ảnh độc lập cùng asset cho `same_id`, và ảnh tham chiếu độc lập cho `similarity`. Ghi nguồn ảnh để kiểm tra việc này.

## Ngôn ngữ truy vấn

Chốt benchmark chính là **tiếng Anh** để phù hợp với metadata/caption nguồn dự kiến của tập asset. Mỗi query text có `language=en`. Không dịch máy cùng một query để tính thành query độc lập. Nếu thu thập được truy vấn tiếng Việt trong một đợt riêng, lưu `language=vi`, báo cáo metric riêng theo ngôn ngữ và không gộp với kết quả tiếng Anh. Không kết luận chất lượng đa ngôn ngữ nếu chưa có tập tiếng Việt được gán nhãn và đánh giá riêng. Quyết định ngôn ngữ này đáp ứng Gate W1; thay đổi cần ghi lý do và cập nhật tài liệu trước thu thập.

## Định nghĩa relevance

Gán relevance cho từng cặp `(query_id, asset_id)` theo bằng chứng nhìn thấy trong asset và metadata đã được duyệt. Không suy luận thuộc tính không có bằng chứng.

| Điểm | Tiêu chí kiểm chứng được |
|---|---|
| `0` | Asset không thỏa điều kiện/ý định thể hiện trong query, hoặc chỉ trùng từ khóa/chủ đề mà không phù hợp đối tượng được yêu cầu. Với query ảnh `same_id`, asset có ID khác luôn là 0. |
| `1` | Asset cùng lớp/nhóm hình dáng hoặc chức năng chính nhưng thiếu ít nhất một thuộc tính phân biệt được nêu rõ trong query; hoặc tương tự về hình thức nhưng không phải đối tượng đích. Với `similarity`, dùng mức này cho asset có hình khối/kiểu dáng liên quan nhưng khác loại hoặc khác đặc điểm chính. |
| `2` | Asset trực tiếp đáp ứng đối tượng và các thuộc tính phân biệt kiểm tra được của query; với `same_id`, asset ID trùng chính xác query asset ID. Với `similarity`, asset cùng loại và gần về hình dáng/chức năng theo tiêu chí mô tả query nhưng có thể khác asset ID. |

Text query được phép có **nhiều asset relevance 1 hoặc 2**. Không chọn duy nhất một “đáp án đúng”; ghi mọi asset đã được rà soát có liên quan và ghi rõ phạm vi đã xét. Asset không có trong qrels không tự động được xem là relevance 0, vì có thể chưa được đánh giá.

Truy vấn `same_id` dùng ảnh khác ảnh index khi có thể và có ground truth là ID asset nguồn; chỉ đúng ID được 2, ID khác là 0. Truy vấn `similarity` không có nhãn cùng ID làm đáp án mặc định: chấm theo tiêu chí relevance tổng quát ở trên và cho phép nhiều asset liên quan.

## Gán nhãn và bất đồng

1. Người phụ trách thu thập lập danh sách query và tập ứng viên asset cần đánh giá, lưu provenance, sau đó ẩn nhãn của người còn lại.
2. **Hai người gán độc lập: Đoàn Thị Minh Khuê và Trịnh Thị Thu Huyền.** Mỗi người ghi relevance và một ghi chú ngắn dẫn chiếu bằng chứng (ví dụ thuộc tính trong query, metadata hoặc đặc điểm nhìn thấy). Không trao đổi điểm trong lượt độc lập.
3. So sánh từng cặp query–asset. Điểm giống nhau được chốt. Mọi khác biệt, gồm cả `0` so với `2`, được hai người cùng rà lại theo tiêu chí; ghi điểm cuối và lý do vào file adjudication. Nếu không thống nhất được, đánh dấu `unresolved`, loại cặp đó khỏi metric chính và báo số lượng/ảnh hưởng trong báo cáo; không tự lấy trung bình điểm.
4. Giữ nguyên hai bản gán độc lập và bản adjudication để truy vết; không ghi đè nhãn gốc. Người ghi adjudication và ngày ghi phải được lưu.

## Nhóm query, split và khóa test

- Gán mọi query gần trùng vào cùng `query_group_id` trước khi chia split. Nhóm gồm paraphrase/dịch/biến thể cùng ý định, query lấy từ cùng asset nguồn, và query ảnh cùng một asset nguồn hoặc cùng một ảnh gốc. Không để cùng một nhóm xuất hiện ở cả validation và test.
- Chia theo **nhóm**, không theo từng dòng query: khoảng **40% validation / 60% test**. Với nhóm không thể chia để đạt đúng tỷ lệ, chọn phân bổ gần nhất và ghi số query thực tế theo split cùng lý do. Dùng seed cố định, ghi `split_version` và seed trong manifest; giữ nguyên sau khi test được khóa.
- Hoàn tất query, qrels adjudication và split trước khi tối ưu. Lưu bản test đã khóa (revision/hash trong manifest hoặc lịch sử kiểm soát phiên bản) và không sửa nhãn/query test sau khi xem kết quả. Nếu phát hiện lỗi nghiêm trọng, ghi nhận, tạo phiên bản benchmark mới và đánh giá lại các cấu hình đã chọn theo quy trình được ghi trước.
- Chỉ dùng validation để chọn model, trọng số, threshold và cấu hình. Test chỉ chạy để báo cáo đánh giá cuối; **không dùng test để chọn hoặc điều chỉnh** model/trọng số/threshold. Không xem test nhiều lần để dẫn dắt tối ưu.

## Định dạng file trong `data/benchmark/`

Lưu UTF-8 CSV, header cố định, một dòng cho mỗi bản ghi; dùng `query_id` liên kết các file. Asset ID phải là ID ổn định trong manifest, không phải đường dẫn cục bộ. Gợi ý các file:

### `queries.csv`

Trường: `query_id,query_type,query_group_id,split,language,query_text,query_image_path,image_source,source_asset_id,notes`

- `query_type`: `text`, `same_id`, hoặc `similarity`.
- `split`: `validation` hoặc `test`.
- Trường không áp dụng để trống; `query_image_path` là đường dẫn tương đối trong dataset local/manifest, không commit ảnh bulk.

```csv
query_id,query_type,query_group_id,split,language,query_text,query_image_path,image_source,source_asset_id,notes
q0001,text,g0001,validation,en,"a low-poly wooden chair with curved arms",,,,
```

Dòng trên chỉ minh họa cấu trúc; không phải query thu thập thật.

### `labels_independent.csv`

Trường: `query_id,asset_id,annotator,relevance,evidence_note,annotated_at_utc`

Mỗi người ghi một dòng cho mỗi cặp đã xem. `annotator` chỉ nhận `Doan Thi Minh Khue` hoặc `Trinh Thi Thu Huyen`; `relevance` là `0`, `1`, `2` (hoặc `unresolved` chỉ ở adjudication, không dùng trong file này).

```csv
query_id,asset_id,annotator,relevance,evidence_note,annotated_at_utc
q0001,asset_example_001,Doan Thi Minh Khue,2,"matches requested chair form and curved arms",2026-10-19T09:00:00Z
```

ID và nhãn trong dòng mẫu là giả định, không mô tả dữ liệu đã thu thập.

### `qrels.csv`

Trường: `query_id,asset_id,relevance,adjudication_status,adjudication_note,adjudicated_by,adjudicated_at_utc`

Đây là nhãn cuối dùng cho đánh giá. `adjudication_status` là `agreed`, `adjudicated`, hoặc `unresolved`; chỉ `agreed` và `adjudicated` đưa vào metric chính. Giữ `unresolved` để báo cáo minh bạch, không tính là 0.

```csv
query_id,asset_id,relevance,adjudication_status,adjudication_note,adjudicated_by,adjudicated_at_utc
q0001,asset_example_001,2,agreed,"both annotators confirmed requested attributes",,2026-10-19T09:10:00Z
```

### `manifest.yaml`

Ghi tối thiểu `benchmark_version`, `created_at`, `query_count`, `query_counts_by_type`, `language_policy`, `split_seed`, `split_version`, `locked_at`, `locked_revision` (hoặc hash), `annotators`, và nguồn/snapshot asset. Không điền số lượng thực tế hay hash trước khi thu thập/khóa.

## Metric và báo cáo

- **Recall@5, Recall@10** và **nDCG@10** trên qrels đã adjudicate; báo riêng theo modality, ngôn ngữ và split khi phù hợp. Recall chỉ diễn giải trên tập relevance đã được rà soát, không coi asset chưa gán nhãn là âm tính.
- **Hit@K** (ghi rõ K, tối thiểu K=5 và K=10) cho truy vấn `same_id`: có hit nếu đúng `source_asset_id` xuất hiện trong top K. Báo riêng khỏi `similarity`.
- **p50/p95 latency**: đo cùng search implementation/API của sản phẩm, ghi máy, cấu hình, số lần lặp, warm-up, cách tính end-to-end và modality; không báo số liệu cho tới khi đo thật.

Không ghi số liệu benchmark trong tài liệu quy trình này. Kết quả thực đo và cấu hình chạy thuộc báo cáo riêng trong `docs/evaluation/`.
