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
