# Rà nghi trùng bằng preview — Issue #92

Ngày rà: 07/11/2026. Người rà: Codex (AI); không phải xác nhận kiểm duyệt của Huyền hoặc reviewer nhóm.

## Phạm vi và cách làm

- Snapshot: home-interior-354-v1.
- Đã xem 354 preview qua 10 bảng ảnh, sau đó so sánh phóng lớn 12 cặp và đối chiếu tên/định danh trong manifest nguồn.
- Gói handoff-interior354-88asuwg0 bị chặn quyền đọc trong môi trường agent. Bản ảnh dùng để rà nằm tại work/interior-expansion/snapshot-home-interior-354-local-20261104/previews trong repo local.
- Đã đối chiếu SHA-256 từng file với preview_sha256 trong curation: 354/354 khớp, không có file thiếu/sai hash. Vì vậy ảnh dùng để rà tương ứng snapshot cần kiểm tra.
- Manifest nguồn: data/manifests/home-interior-354-v1/assets_354.json. SHA-256: 93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614.
- Các số thứ tự trên ảnh so sánh là số của bảng rà, không phải number trong curation. Dùng asset_id trong CSV để đối chiếu.

## Kết quả

- 12 cặp được ghi trong duplicate-review.csv: 11 keep_both và 1 uncertain.
- Chưa có cặp đủ bằng chứng để đề xuất loại. Không thay đổi asset IDs, manifest, curation hay nội dung snapshot.
- keep_both là quyết định giữ dữ liệu hiện có theo bằng chứng preview/metadata; không chứng nhận mesh độc lập.

### Cặp cần xác minh tiếp

objaverse_943ae5d90d654498912d0d3d0114ba35 / objaverse_4da262198ca442deaf92607dc8388225 (hàng đầu pairs-1.jpg).

Hai ghế bọc da cam kèm đôn có nhiều nét tương đồng: nút lõm, tựa đầu, khung tay và chân sao. Góc chụp khác nhau. Manifest ghi tên Leather chair with footrest / The Armchair with footrest, tác giả RP_Babu / Vikash Tiwari. Những khác biệt nguồn chưa đủ chứng minh đây là hai mesh độc lập. Giữ trạng thái uncertain, không tự loại; nhờ owner đối chiếu nguồn/model. Trong lúc chờ, báo cặp này cho Khuê để tránh dùng làm hai trường hợp độc lập khi khóa benchmark.

### Biến thể cùng sản phẩm

objaverse_20bea6eec87d40ed843701511ebfdc32 / objaverse_26d7c6f17e9a4176871967064058c5e9 (hàng thứ hai pairs-1.jpg).

Cùng tác giả MADE.COM, cùng dòng Rubens 3 Seater Sofa; tên nguồn phân biệt Kelp Green Wool Mix và Flame Orange Velvet. Giữ hai asset như snapshot hiện có, ghi quan hệ biến thể. Nhờ Khuê xác định cách gom nhóm trước khi chia query/candidate hoặc split đánh giá; chưa có xác nhận từ Khuê.

## Giới hạn và việc còn lại

- Đây là rà bằng AI trên preview; không phải review độc lập của thành viên nhóm.
- 354 ảnh đã được xem ở dạng bảng; chỉ 12 cặp được xem phóng lớn. Không phải đối chiếu thủ công toàn bộ 62.481 cặp và không bảo đảm phát hiện hết near-duplicate khác góc, màu hoặc render.
- Không tải/so sánh mesh, không chứng nhận dedup hình học. Không tự kết luận hành vi sao chép hay vi phạm license từ nét tương đồng.
- Tên/author lấy từ metadata đã commit; chưa kiểm chứng trực tuyến trang nguồn.
- Chờ owner xử lý cặp uncertain và Khuê xem rủi ro biến thể khi khóa benchmark. Chưa tích mục review/approval hoặc đóng Issue.

## Lưu ý cho thống kê độ phủ

154 bản ghi không có category, nhưng có reviewed_category_vi. Không dùng riêng category rồi coi 154 bản ghi này là chưa được phân loại. Cần mapping có tài liệu giữa các nhãn kiểm duyệt; giữ riêng source_category. Không sửa snapshot chỉ để thống nhất tên trường.
