# SRS - Hệ thống 3D Asset Semantic Search

- Phiên bản tài liệu: 0.1 - dự thảo tuần 1.
- Trạng thái: chờ nhóm review; mô tả yêu cầu, không xác nhận chức năng đã triển khai.
- Phạm vi đầu việc: SRS và use cases; FastAPI skeleton, DB schema và API contract là các đầu việc riêng.
- Nguồn nội dung: kế hoạch AI-04 phiên bản 1.0 ngày 08/10/2026, file AI04_Ke_hoach_nhom_5_thanh_vien.pdf.
- Phạm vi bàn giao: Issue #1, tài liệu docs/srs.md.
- Cách trình bày: các chức năng trong kế hoạch được diễn đạt thành yêu cầu và luồng use case. Các ngưỡng, chính sách hoặc quyết định chưa có trong PDF không được tự bổ sung thành yêu cầu đã chốt.

## 1. Mục đích và phạm vi

Xây dựng ứng dụng web giúp người dùng tìm asset 3D bằng mô tả văn bản hoặc ảnh tham chiếu. Hệ thống truy xuất dựa trên ảnh preview và metadata, trả kết quả xếp hạng, hỗ trợ lọc, xem chi tiết và gửi phản hồi độ phù hợp. Nhóm có pipeline nhập dữ liệu theo batch và benchmark tái lập để đánh giá chất lượng, hiệu năng và lựa chọn cấu hình.

MVP gồm text search, image search, filters, chi tiết asset, giải thích kết quả, feedback, ingestion/status và evaluation/versioning. Tìm kiếm công khai không bắt buộc đăng nhập; chức năng nhập dữ liệu được giới hạn cho quản trị.

Ngoài MVP: sinh mesh 3D, huấn luyện foundation model, phân tích hình học trực tiếp. Viewer GLB tương tác, nhiều góc render và caption tự động là mở rộng; chi tiết asset trong MVP chỉ cần preview và metadata.

## 2. Thuật ngữ và tác nhân

| Thuật ngữ | Ý nghĩa |
|---|---|
| Asset | Một đối tượng 3D có ID ổn định, metadata và ảnh preview |
| Semantic search | Tìm theo ý nghĩa/tương đồng của truy vấn với dữ liệu đã lập chỉ mục |
| Ingestion | Đọc nguồn, chuẩn hóa, kiểm tra ảnh, tạo embedding và lập chỉ mục |
| Search event | Bản ghi một lần tìm kiếm, gắn truy vấn, filters và phiên bản cấu hình |
| Top K | Tối đa K asset duy nhất theo thứ hạng; có thể ít hơn nếu không đủ kết quả |
| p50 / p95 | Phân vị 50% / 95% của thời gian phản hồi đo được |

| Tác nhân | Nhu cầu và quyền |
|---|---|
| Người tìm kiếm | Nhập text/ảnh, lọc, xem chi tiết và gửi feedback |
| Quản trị viên | Chạy batch được kiểm soát, xem trạng thái/lỗi và retry |
| Thành viên đánh giá | Chạy benchmark theo dataset, nhãn và cấu hình cố định |

## 3. Bối cảnh và dữ liệu

Định hướng của kế hoạch: React + TypeScript, FastAPI, PostgreSQL, Qdrant và lưu trữ file local; môi trường tái lập bằng Docker Compose. PostgreSQL là nguồn metadata nghiệp vụ; payload Qdrant cần đồng bộ khi cập nhật. Các định hướng này không thay thế API contract hoặc ADR.

Dataset chính là Objaverse subset: bắt đầu với manifest 200 asset; mục tiêu mở rộng 1.000-3.000 asset đã kiểm tra trong một miền được nhóm chọn. ABO là phương án dữ liệu thay thế được kế hoạch nêu. Mỗi asset phải có nguồn/license rõ, preview dùng được và metadata hữu ích trước khi được công bố searchable.

Metadata tối thiểu: asset_id, source, source_id, source_url, author, license, name, description, tags, category, thumbnail_path, model_path nếu có, formats, face_count nếu biết, checksum, ingestion_status, model_version và index_version. Thuộc tính thiếu để null; không suy đoán license, số mặt, vật liệu hoặc rigging từ ảnh.

Baseline ban đầu là CLIP. SigLIP 2 và E5 + RRF là cấu hình thử nghiệm được lựa chọn theo benchmark. Không so/cộng trực tiếp vector từ các không gian không tương thích; không trộn embedding các phiên bản trong cùng index phục vụ tìm kiếm.

## 4. Yêu cầu chức năng

Các yêu cầu dưới đây diễn đạt các chức năng trong PDF thành tiêu chí kiểm chứng. Không bổ sung giới hạn số hoặc chính sách ngoài kế hoạch.

| ID | Yêu cầu | Tiêu chí nghiệm thu |
|---|---|---|
| FR-01 | Tìm asset bằng văn bản cùng filters và K | Truy vấn hợp lệ trả tối đa K asset duy nhất, có thứ hạng; truy vấn rỗng bị từ chối |
| FR-02 | Tìm bằng ảnh upload cùng filters và K | Ảnh hợp lệ được mã hóa để tìm trong preview index; ảnh hỏng/sai định dạng/quá giới hạn bị từ chối có thông báo |
| FR-03 | Lọc category, license, formats và khoảng face_count có dữ liệu | Kết quả đáp ứng filters trên thuộc tính có dữ liệu; không suy đoán giá trị thiếu |
| FR-04 | Hiển thị kết quả và trạng thái UI | Có loading, empty và error riêng; mỗi kết quả có ID, tên, thumbnail, thứ hạng và dữ liệu đủ để mở chi tiết |
| FR-05 | Xem chi tiết asset | Hiển thị preview, metadata, tags, nguồn, tác giả/license, định dạng và face_count nếu có; giá trị thiếu được ghi chưa có thông tin; ID không tồn tại có lỗi rõ |
| FR-06 | Giải thích kết quả theo tín hiệu thực tế | Nêu nguồn truy xuất preview/metadata, thuộc tính và filters liên quan; score không được gọi là xác suất đúng |
| FR-07 | Gửi feedback phù hợp/không phù hợp | Lưu search_event_id, asset_id, relevance và thời điểm; liên kết được với truy vấn và model/index/config version; không báo thành công nếu lưu thất bại |
| FR-08 | Nhập dữ liệu theo batch và chống trùng | Ghi trạng thái/lỗi từng asset, retry có giới hạn; chạy lại cùng manifest không tạo asset trùng; lỗi một asset không làm mất toàn batch |
| FR-09 | Xem trạng thái ingestion cho quản trị | Hiển thị trạng thái xử lý và lỗi ingestion; có trang quản trị tác vụ kết nối API theo lịch triển khai |
| FR-10 | Quản lý khả năng tìm kiếm và phiên bản | Lưu model/revision, dataset snapshot và index version; thay model tạo index mới, không trộn embedding cũ/mới; metadata và payload cần đồng bộ |
| FR-11 | Benchmark và đối chiếu baseline | Có nhãn liên quan, script đo, cấu hình cố định và báo cáo so sánh keyword/CLIP/cấu hình thử nghiệm; đo Recall@5/10, nDCG@10, p50/p95; có thể thêm Hit@K cho cùng ID |

### Quy tắc từ kế hoạch

- BR-01: Lọc trên thuộc tính có dữ liệu; trường thiếu để null, không bịa số mặt hoặc license.
- BR-02: Các luồng tìm kiếm dùng cùng filters; kết quả top K là asset duy nhất.
- BR-03: Phản hồi phù hợp/không phù hợp phải gắn truy vấn và phiên bản tìm kiếm.
- BR-04: Chỉ so sánh embedding của encoder tương thích trong cùng model; không so trực tiếp hoặc cộng vector E5 với vector CLIP/SigLIP 2.
- BR-05: Điểm tương đồng không phải xác suất đúng; explanation chỉ nêu tín hiệu và metadata thực tế.
- BR-06: Tìm kiếm công khai không bắt buộc đăng nhập; nhập dữ liệu giới hạn cho quản trị.

PDF chưa quy định AND/OR của filter, cách xử lý null khi lọc hoặc cập nhật feedback nhiều lần; tài liệu này không tự chốt các chính sách đó.

## 5. Yêu cầu phi chức năng

| ID | Yêu cầu dựa trên kế hoạch | Cách kiểm chứng |
|---|---|---|
| NFR-01 | Đo latency p50/p95, tách text/ảnh và ghi máy, cấu hình đo; tối ưu theo máy demo | Báo cáo benchmark và raw results. PDF chưa có ngưỡng giây cụ thể, nên chưa thể kết luận đạt một ngưỡng hiệu năng |
| NFR-02 | Quy mô dữ liệu: 200 asset thử nghiệm, mở rộng 1.000-3.000 asset đã kiểm tra; lưu metadata, thumbnail, vector và model mẫu phù hợp subset | Kiểm tra manifest và đo dung lượng lưu trữ thực tế. PDF chưa quy định ngân sách GB/GiB; số asset không đồng nghĩa dung lượng byte |
| NFR-03 | Môi trường chạy tái lập bằng Docker Compose và hướng dẫn dựng hệ thống | Thành viên khác dựng được hệ thống theo hướng dẫn ở mốc tuần 7 |
| NFR-04 | Tái lập model/index và thí nghiệm: lưu model ID/revision, processor/tokenizer revision, dimension, chuẩn hóa, dataset snapshot, ngày tạo, index version; ghi máy, seed nếu có, versions/configs và raw results | Đối chiếu manifest, cấu hình, script và báo cáo khi chạy lại |
| NFR-05 | Pipeline chịu lỗi dữ liệu: ghi lỗi từng asset, retry ảnh/URL hỏng và chạy lại không tạo bản ghi trùng | Batch tests cho ảnh hỏng, thiếu trường và nhập lại |
| NFR-06 | Kiểm tra đầu vào ảnh theo kích thước/định dạng; chức năng nhập dữ liệu giới hạn cho quản trị | Kiểm tra validation và quyền nhập dữ liệu. PDF chưa quy định kích thước tối đa hay danh sách định dạng cụ thể |
| NFR-07 | Giao diện có trạng thái loading/empty/error; hoàn thiện responsive/accessibility theo lịch tuần 7 | Review UI và kiểm thử các luồng tìm kiếm |
| NFR-08 | Đánh giá chất lượng minh bạch trên cùng tập; tách text/ảnh và tiếng Việt/tiếng Anh; không đặt sẵn số chất lượng chưa đo | Báo cáo keyword, CLIP, SigLIP 2 và fusion trên cùng dữ liệu/truy vấn/máy |

### Quy định đánh giá trong PDF

- Đề xuất 60-80 truy vấn text và 20-40 ảnh khác góc hoặc ngoài index.
- Hai người đánh giá độc lập; giải quyết bất đồng; nhãn relevance 0/1/2 dùng cho benchmark, phân biệt với feedback phù hợp/không phù hợp của người dùng.
- Chia khoảng 40% validation, 60% test; giữ truy vấn gần trùng cùng nhóm và khóa test trước tối ưu.
- Đo Recall@5/10, nDCG@10 và latency p50/p95; có thể thêm Hit@K cho tìm cùng ID. Nếu nhãn chưa đầy đủ, ghi Recall theo tập nhãn đã biết.
- Top 50 mỗi luồng rồi trả top 10 là cấu hình thử trong kế hoạch, cần chỉnh trên validation; không phải giới hạn K cố định của sản phẩm.

Không bổ sung ngưỡng p50/p95, giới hạn upload, ngân sách dung lượng hay số request benchmark khi PDF chưa quy định. Các giá trị này được bổ sung sau khi nhóm có quyết định và dữ liệu đo.

## 6. Use cases

Các luồng dưới đây diễn giải chức năng và trạng thái xử lý trong PDF theo cấu trúc use case để phục vụ Issue #1. Đây không phải trích nguyên văn; không chốt endpoint, mã lỗi, định danh phiên hoặc chính sách lưu ảnh ngoài kế hoạch.

### UC-01 - Tìm kiếm asset bằng văn bản

- Tác nhân: người tìm kiếm.
- Mục tiêu: tìm asset phù hợp mô tả, ví dụ "ghế gỗ phong cách tối giản".
- Liên kết: FR-01, FR-03, FR-04, FR-06, FR-10; NFR-01, NFR-08.
- Tiền điều kiện: hệ thống có index đang phục vụ với asset searchable; không yêu cầu đăng nhập.
- Kích hoạt: người dùng gửi mô tả text, K và filters hiện hành.

Luồng chính:
1. Người dùng nhập mô tả và nhấn tìm kiếm.
2. UI hiển thị loading; API trim và kiểm tra text, K, filters.
3. Hệ thống mã hóa truy vấn bằng encoder tương thích index; chạy metadata retrieval/fusion nếu cấu hình đó được bật.
4. Retrieval áp dụng filters, gom theo asset_id và xếp hạng tối đa K asset.
5. Hệ thống ghi search event với truy vấn, filters, cấu hình và model/index/dataset version.
6. Hệ thống trả event ID, kết quả, thứ hạng và explanation; UI hiển thị kết quả để người dùng mở chi tiết/gửi feedback.

Luồng thay thế và ngoại lệ:
- A1: Không có kết quả -> hiển thị empty và gợi ý đổi mô tả hoặc bỏ bớt filters.
- A2: Có ít hơn K asset đáp ứng -> trả số có sẵn, không thêm kết quả vi phạm filter hoặc trùng ID.
- E1: Đầu vào không hợp lệ -> hệ thống thông báo lỗi để người dùng chỉnh và gửi lại; giới hạn cụ thể chưa được PDF quy định.
- E2: Encoder/index/DB không sẵn sàng hoặc timeout -> báo lỗi có thể thử lại, không giả kết quả thành công.

Hậu điều kiện thành công: có search event hợp lệ và danh sách kết quả gắn đúng phiên bản. Khi lỗi, không có kết quả mới được tuyên bố thành công.

Nghiệm thu: text hợp lệ trả <= K ID duy nhất, đúng filters; whitespace bị từ chối; empty và lỗi dịch vụ được phân biệt; event/phiên bản liên kết được với kết quả.

### UC-02 - Tìm kiếm asset bằng ảnh preview

- Tác nhân: người tìm kiếm.
- Mục tiêu: tìm asset có preview tương tự ảnh tham chiếu.
- Liên kết: FR-02, FR-03, FR-04, FR-06, FR-10; NFR-01, NFR-06.
- Tiền điều kiện: preview index hoạt động, model truy vấn tương thích index.
- Kích hoạt: người dùng chọn file ảnh và nhấn tìm kiếm.

Luồng chính:
1. Người dùng chọn ảnh; UI hiển thị preview để kiểm tra trước khi gửi.
2. Người dùng gửi ảnh cùng K và filters; UI hiển thị loading.
3. API kiểm tra đầu vào ảnh theo kích thước/định dạng; giới hạn cụ thể chưa được PDF quy định.
4. Hệ thống xử lý ảnh bằng processor của checkpoint và tạo image embedding.
5. Hệ thống tìm trong preview index với filters, loại trùng asset và trả tối đa K kết quả.
6. Hệ thống ghi nhận truy vấn ảnh và phiên bản tìm kiếm để liên kết với feedback; cách lưu ảnh không được PDF quy định.
7. UI hiển thị kết quả, explanation, liên kết chi tiết và feedback.

Luồng thay thế và ngoại lệ:
- A1: Người dùng thay ảnh trước khi gửi -> cập nhật preview, sử dụng ảnh mới.
- A2: Không có kết quả -> empty; không khẳng định hệ thống nhận diện được vật thể.
- E1: Ảnh hỏng hoặc không đáp ứng kiểm tra kích thước/định dạng -> thông báo lỗi để người dùng chọn ảnh khác.
- E2: Encoder/index/DB lỗi hoặc timeout -> báo lỗi và cho thử lại.

Hậu điều kiện thành công: truy vấn ảnh trả kết quả gắn phiên bản tìm kiếm, có thông tin để liên kết feedback.

Nghiệm thu: ảnh hợp lệ trả ID duy nhất đúng filters; đầu vào không hợp lệ và lỗi truy xuất có thông báo; đo p50/p95 cho luồng ảnh và ghi cách đo.

### UC-03 - Lọc thuộc tính asset

- Tác nhân: người tìm kiếm.
- Mục tiêu: thu hẹp kết quả theo metadata xác thực.
- Liên kết: FR-03, FR-04; BR-01, BR-02.
- Tiền điều kiện: có truy vấn text/ảnh hợp lệ; hệ thống có định nghĩa thuộc tính và giá trị filter được hỗ trợ.
- Kích hoạt: người dùng chọn hoặc xóa filter rồi áp dụng.

Luồng chính:
1. UI cung cấp category, license, formats và khoảng face_count có dữ liệu.
2. Người dùng chọn điều kiện và áp dụng.
3. API kiểm tra giá trị filter và cận số mặt.
4. Hệ thống chạy lại truy vấn trên index với tất cả filters; không chỉ lọc những thẻ đã tải trên UI.
5. Hệ thống ghi event mới cho truy vấn/filters hiện hành và trả top K duy nhất.
6. UI hiển thị kết quả cùng các filter đang áp dụng.

Luồng thay thế và ngoại lệ:
- A1: Xóa một/toàn bộ filter -> chạy lại truy vấn với điều kiện còn lại.
- A2: Không có asset đáp ứng -> empty, cho bỏ bớt điều kiện.
- A3: Asset thiếu face_count hoặc thuộc tính khác -> giữ giá trị null, không tạo dữ liệu giả; cách xử lý null trong filter chưa được kế hoạch chốt.
- E1: Filter không hợp lệ -> thông báo lỗi để người dùng chỉnh; quy tắc validation chi tiết được xác định khi xây contract.
- E2: Dịch vụ lỗi -> UI báo lỗi, không trình bày kết quả cũ như kết quả của filters mới.

Hậu điều kiện thành công: mọi kết quả thỏa quy tắc lọc và gắn event mới; query text/ảnh vẫn là query người dùng đang sử dụng.

Nghiệm thu: filters hoạt động trên thuộc tính có dữ liệu; các luồng retrieval dùng cùng filters; kết quả không trùng asset; trường thiếu không bị bịa thành giá trị có thật.

### UC-04 - Gửi phản hồi độ phù hợp

- Tác nhân: người tìm kiếm.
- Mục tiêu: đánh dấu kết quả phù hợp/không phù hợp để nhóm phân tích.
- Liên kết: FR-07; BR-03.
- Tiền điều kiện: người dùng đã thực hiện tìm kiếm và có kết quả để đánh giá; truy vấn và phiên bản được ghi nhận.
- Kích hoạt: người dùng chọn phù hợp hoặc không phù hợp trên một kết quả.

Luồng chính:
1. UI gửi search_event_id, asset_id và relevance theo lựa chọn.
2. API kiểm tra đầu vào, event tồn tại và asset thuộc kết quả event.
3. Hệ thống lưu feedback gắn với asset, truy vấn và phiên bản tìm kiếm.
4. API xác nhận lưu thành công.
5. UI mới hiển thị lựa chọn đã ghi nhận.

Luồng thay thế và ngoại lệ:
- A1: Người dùng không gửi feedback -> vẫn tiếp tục xem và tìm asset.
- Việc đổi lựa chọn/gửi lại feedback chưa được PDF quy định; tài liệu không tự chốt cơ chế cập nhật hoặc nhận diện phiên.
- E1: Event/asset không hợp lệ, asset không thuộc event hoặc relevance không hỗ trợ -> từ chối có lỗi rõ.
- E2: DB hoặc mạng lỗi -> UI báo chưa lưu được, cho thử lại; không đánh dấu đã lưu.

Hậu điều kiện thành công: feedback liên kết đúng asset, truy vấn và phiên bản tìm kiếm.

Nghiệm thu: lưu được cả hai lựa chọn phù hợp/không phù hợp và liên kết đúng truy vấn/phiên bản; lỗi lưu có thông báo để người dùng nhận biết.

## 7. Ma trận truy vết và kiểm chứng bổ sung

| Phạm vi | Yêu cầu | Kiểm chứng |
|---|---|---|
| Text | FR-01, FR-04, FR-06, FR-10 | UC-01, test top K/empty/validation/event |
| Image | FR-02, FR-04, FR-10 | UC-02, ảnh hợp lệ/hỏng và validation kích thước/định dạng |
| Filters | FR-03 | UC-03, test tổ hợp/null/fusion |
| Feedback | FR-07 | UC-04, lưu feedback và đối chiếu truy vấn/phiên bản |
| Detail | FR-05 | Mở ID hợp lệ: preview/nguồn/license; null hiển thị rõ; ID không tồn tại có lỗi |
| Ingestion/status | FR-08, FR-09, FR-10 | Nhập lại không trùng; lỗi một asset vẫn có summary; metadata/payload đồng bộ; nhập dữ liệu giới hạn cho quản trị |
| Evaluation | FR-11, NFR-01, NFR-04, NFR-08 | Runner, nhãn/split cố định, raw metrics và manifest phiên bản |
| Storage/rebuild | NFR-02, NFR-03 | Đo dung lượng theo nhóm dữ liệu; dựng/rebuild trên máy khác |

## 8. Những nội dung kế hoạch còn để mở

Mục này giúp người đọc phân biệt yêu cầu đã có trong PDF với lựa chọn sẽ được nhóm quyết định khi triển khai. Đây không phải danh sách issue mới và không yêu cầu hoàn thành thêm module trong Issue #1.  
Thông tin tổng hợp từ kế hoạch; các thông số chưa được tài liệu quy định.

| Nội dung | PDF đã nêu | Điều còn để mở | Người phối hợp theo phân công |
|---|---|---|---|
| Miền dữ liệu | Chọn một miền như nội thất/game props, thử 200 asset | Chọn miền cụ thể theo khảo sát dữ liệu | Huyền + Chi |
| Model cuối | CLIP baseline; thử SigLIP 2, E5 + RRF nếu cải thiện | Chọn cấu hình theo chất lượng và tốc độ đo được | Chi + Khuê |
| Cấu hình retrieval | Top 50 mỗi luồng, trả top 10 là cấu hình thử | Điều chỉnh trên validation | Chi + Khuê |
| Latency và dung lượng | Đo p50/p95; quy mô 200 rồi 1.000-3.000 asset | Chưa có ngưỡng giây, dung lượng GB/GiB hoặc cấu hình máy cố định | Quỳnh Anh + Chi + Khuê |
| Giới hạn ảnh upload | Tuần 4 có kiểm tra kích thước/định dạng | Chưa có kích thước tối đa hoặc danh sách định dạng cụ thể | Quỳnh Anh + Duy |
| API/schema chung | Tuần 1 thống nhất asset schema và API contract | Chi tiết request/response được làm trong đầu việc riêng | Quỳnh Anh phối hợp Huyền, Chi, Duy và Khuê theo module |
| Mở rộng | Viewer GLB, nhiều góc hoặc caption tự động ngoài MVP; tuần 9-10 chọn một mở rộng nếu có thời gian | Không cam kết triển khai trong MVP | Cả nhóm |

Ví dụ: PDF yêu cầu đo latency p50/p95 nhưng chưa nói p95 phải dưới bao nhiêu giây. SRS ghi đúng yêu cầu đo và trạng thái chưa có ngưỡng, không tự thêm con số.

## 9. Tiêu chí hoàn thành đầu việc tài liệu

- [ ] Phạm vi/MVP/mở rộng rõ, phù hợp PDF kế hoạch nhóm.
- [ ] FR có ID và tiêu chí nghiệm thu; NFR ghi rõ những ngưỡng chưa được PDF quy định.
- [ ] UC-01 đến UC-04 đủ tác nhân, tiền điều kiện, kích hoạt, luồng chính, ngoại lệ và hậu điều kiện.
- [ ] Có liên kết yêu cầu/use case/kiểm chứng; detail và ingestion status không bị bỏ sót.
- [ ] Nhóm review tài liệu; nội dung còn để mở được ghi đúng trạng thái, không bắt buộc hoàn thành các đầu việc triển khai để bàn giao SRS.
- [ ] Lưu tại docs/srs.md; kiểm tra Markdown và diff; push nhánh nhiệm vụ, PR về develop theo quy trình nhóm.

Tài liệu có thể hoàn thành review tuần 1 trong khi chức năng tương ứng được triển khai ở các tuần sau. Không đánh dấu toàn bộ milestone tuần 1 hoàn thành chỉ vì đã có SRS.
