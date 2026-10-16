# Hướng dẫn đóng góp

1. Tạo/nhận một Issue có phạm vi hoàn thành trong 1–3 ngày.
2. Tạo nhánh từ `origin/develop`:

   ```bash
   bash scripts/new-task-branch.sh feat 12 login-form
   ```

3. Thực hiện thay đổi và kiểm thử phù hợp; commit có mô tả rõ ràng.
4. Push nhánh nhiệm vụ và mở PR:

   ```bash
   git push -u origin feat/12-login-form
   gh pr create --base develop --head feat/12-login-form
   ```

5. Ghi `Refs #12` trong PR. GitHub có thể chưa tự đóng Issue khi PR merge vào `develop` vì nhánh mặc định là `main`; đóng Issue sau khi nhóm xác nhận hoàn thành hoặc liên kết trong PR release.
6. Nhờ một thành viên khác review; CI xanh, ít nhất 1 approval và xử lý hết trao đổi trước khi merge.
7. Xóa nhánh nhiệm vụ sau merge. Tạo nhánh mới cho Issue tiếp theo.

Không push trực tiếp vào `main` hoặc `develop`. Xem [quy trình đầy đủ](docs/BRANCHING.md).

## Checklist Issue và PR

Mọi PR sử dụng [mẫu chung](.github/PULL_REQUEST_TEMPLATE.md). Quy định nguồn nằm tại [AGENTS.md, mục 8.4](AGENTS.md#84-checklist-issue-và-pull-request), áp dụng cho thành viên, Codex và Claude.

Giữ tách biệt các ô triển khai/kiểm chứng với review/tích hợp. Tích theo bằng chứng thực tế; việc không áp dụng ghi N/A và lý do cạnh ô chưa tích. Bổ sung lệnh, kết quả và giới hạn kiểm tra để reviewer đối chiếu. Khi bàn giao, cập nhật checklist của Issue cùng liên kết PR; giữ nguyên các tiêu chí đã thống nhất.

Khi rà soát/cập nhật PR đang mở trong phạm vi được giao, áp dụng lại cấu trúc template cho chính PR đó; giữ nguyên tiêu chí và bằng chứng, không tự sửa các PR ngoài phạm vi hoặc PR đã đóng/merge.

Các mục chờ reviewer, chốt contract hoặc merge tiếp tục để trống. Thực hiện theo [quy trình nhánh](docs/BRANCHING.md); checklist không phải approval và không tự cho phép merge.

GitHub chỉ tự nạp PR template khi file đã có trên default branch của repo (hiện là `main`), theo [GitHub Docs](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository). Trước khi template được đưa từ `develop` lên `main` qua PR release, tác giả lấy mẫu từ nhánh đã cập nhật, điền nội dung vào một file tạm rồi dùng `gh pr create --body-file <file-da-dien>` hoặc dán vào mô tả PR. Không push trực tiếp `main` để bật template.
