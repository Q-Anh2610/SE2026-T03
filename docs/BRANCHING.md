# Quy trình nhánh

| Nhánh | Người dùng và quy tắc |
| --- | --- |
| `main` | Bản demo/nộp ổn định. Vũ Nguyễn Quỳnh Anh và Đoàn Thị Minh Khuê điều phối release. Chỉ nhận PR từ `develop`; không push trực tiếp. |
| `develop` | Bản tích hợp chung. Cả 5 thành viên gửi PR từ nhánh nhiệm vụ. CI phải xanh và ít nhất một người khác approve. |
| `feat/<issue>-<task>` | Tính năng mới; tạo từ `develop`, PR về `develop`. |
| `fix/<issue>-<task>` | Sửa lỗi; cùng luồng PR. |
| `test/<issue>-<task>` | Kiểm thử; cùng luồng PR. |
| `chore/<issue>-<task>` | Cấu hình, công cụ; cùng luồng PR. |
| `docs/<issue>-<task>` | Tài liệu; cùng luồng PR. |

`<issue>` là số Issue dương; `<task>` là mô tả chữ thường, số và dấu gạch ngang.
Ví dụ: `feat/12-login-form`, `fix/18-empty-cart`, `docs/21-api-guide`.
Không tạo nhánh có tên chỉ là `feat`, `fix`, `test`, `chore`, `docs` hoặc 5 nhánh cá nhân tồn tại suốt kỳ.
Mỗi nhánh kéo dài 1–3 ngày. Tính năng dài chia thành các Issue nhỏ, có thể review và kiểm thử độc lập; dùng Draft PR khi chưa hoàn tất.

## Đưa quy trình vào repo

Các file hiện được chuẩn bị trong workspace; chưa được đưa lên GitHub.
Trong một bản clone Git hợp lệ, có working tree sạch:

1. Repo GitHub đã có `main` và `develop`. Dùng bản clone có remote `origin` đúng repo; đăng nhập `gh auth login` bằng tài khoản có quyền ghi repo nếu dùng GitHub CLI.
2. Chạy `git fetch origin` và kiểm tra `git branch -r` có `origin/develop`; không cần tạo lại nhánh chung.
3. Tạo Issue cho việc thiết lập quy trình; lấy số Issue thật. Số `1` ở bước dưới chỉ là ví dụ, phải thay bằng ID của Issue đó.
4. Chạy `bash /duong-dan/ban-file-da-chuan-bi/scripts/new-task-branch.sh chore 1 branching-workflow`.
5. Sau khi tạo nhánh, sao chép các file đã chuẩn bị vào bản clone. Commit `README.md`, `CONTRIBUTING.md`, `docs/BRANCHING.md`, `.github/`, `scripts/`; push nhánh nhiệm vụ và mở PR về `develop`.
6. Người khác review, CI xanh rồi merge PR. Vũ Nguyễn Quỳnh Anh và Đoàn Thị Minh Khuê mở PR `develop → main` để đưa quy trình vào bản ổn định.
7. Chủ repo bật bảo vệ hai nhánh theo hướng dẫn dưới đây.

Không chạy `git init` để thay thế bản clone, không commit hoặc push trực tiếp vào `main`.

## Bảo vệ nhánh trên GitHub

Chủ repo vào **Settings → Branches → Add branch protection rule**, tạo quy tắc riêng cho `main` và `develop`:

- Require a pull request before merging; ít nhất **1 approval** từ người khác.
- Dismiss stale pull request approvals when new commits are pushed.
- Require approval of the most recent reviewable push.
- Require status checks to pass; chọn **branch-policy** sau khi workflow đã chạy lần đầu.
- Require branches to be up to date before merging.
- Require conversation resolution before merging.
- Do not allow bypassing the above settings, áp dụng cả quản trị viên.
- Không cho force push và xóa hai nhánh này.

Bảo vệ nhánh cần quyền admin/owner. Xem [GitHub branch protection](https://docs.github.com/en/rest/branches/branch-protection#update-branch-protection).
Workflow kiểm tra PR vào `main` phải đến từ `develop` của chính repo; PR vào `develop` phải đúng tên nhánh nhiệm vụ.
CI hiện kiểm tra quy trình nhánh vì repo chưa có mã ứng dụng; cần bổ sung build/lint/test và đặt chúng thành required checks khi có mã.
File workflow một mình không chặn push trực tiếp: phải bật bảo vệ nhánh.

Vũ Nguyễn Quỳnh Anh và Đoàn Thị Minh Khuê phụ trách điều phối; chưa có GitHub username tương ứng nên chưa cấu hình quyền riêng cho hai người này.
Với repo cá nhân, tổ chức việc merge release theo quy ước nhóm; nếu cần cưỡng chế quyền theo thành viên, chủ repo cấu hình ruleset/quyền phù hợp hoặc dùng repo tổ chức.

## Release và dọn nhánh

Vũ Nguyễn Quỳnh Anh và Đoàn Thị Minh Khuê kiểm tra demo, CI và review rồi mở PR `develop → main`:

```bash
gh pr create --base main --head develop --title "Release: bản demo" --body "Mô tả các Issue đã hoàn thành và kết quả kiểm thử/demo."
```

Merge PR release bằng **Create a merge commit** để giữ lịch sử chung giữa `main` và `develop`.
Xóa nhánh nhiệm vụ sau khi merge; giữ `main` và `develop`.
Không squash/rebase PR release. PR nhiệm vụ có thể squash nếu nhóm thống nhất.
