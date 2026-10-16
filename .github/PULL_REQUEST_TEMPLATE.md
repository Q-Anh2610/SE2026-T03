## Mục tiêu

<!-- Mô tả vấn đề và hành vi sau thay đổi. Thay ID bên dưới bằng Issue thật.
Khi chuẩn hóa PR đang mở, giữ nguyên phạm vi, tiêu chí nghiệm thu và bằng chứng đã có. -->
Refs #

## Thay đổi

<!-- Nêu phần chính; ghi ảnh hưởng API/schema/index/dependencies nếu có. -->

## Checklist triển khai và kiểm chứng

- [ ] Đã đối chiếu acceptance criteria của Issue và nêu rõ phần còn thiếu.
- [ ] Diff đúng phạm vi, không chứa secret, dữ liệu lớn hoặc output/cache sinh ra.
- [ ] Đã chạy các kiểm tra phù hợp và ghi lệnh, kết quả, giới hạn ở bảng dưới.
- [ ] Đã kiểm tra ảnh hưởng API/schema/index/dependencies và cập nhật tài liệu cần thiết.
- [ ] Đã cập nhật checklist Issue cùng liên kết PR, không đánh dấu việc chưa xác minh.

## Bằng chứng kiểm chứng

| Lệnh / kiểm tra | Kết quả | Bằng chứng hoặc giới hạn |
|---|---|---|
| | | |

<!-- Tích theo bằng chứng. Không áp dụng: giữ ô trống, ghi N/A và lý do.
Test local không phải CI xanh. Với UI, ghi kiểm tra mobile/desktop và các trạng thái bị ảnh hưởng.
Với tài liệu, kiểm tra diff/liên kết/import; không bịa lệnh build/test đã chạy. -->

## Lưu ý cho reviewer

<!-- Nêu contract/quyết định cần owner review, rủi ro, cách revert/migration nếu có. -->

## Checklist review và tích hợp

- [ ] Required checks hiện có đã đạt trên commit mới nhất của PR.
- [ ] Có ít nhất một thành viên khác approve.
- [ ] Các góp ý/trao đổi chặn đã được xử lý.
- [ ] PR đã được người có quyền và được giao merge theo quy trình nhóm.

<!-- Để trống mục chưa xảy ra. Không tự approve hoặc merge.
PR nhiệm vụ: head là nhánh nhiệm vụ, base develop, mặc định squash.
PR release: develop -> main, merge commit.
Nguồn luật: AGENTS.md mục 8.4; xem CONTRIBUTING.md và docs/BRANCHING.md. -->
