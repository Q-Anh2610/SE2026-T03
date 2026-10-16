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

## Áp dụng quy trình

Repo đã có `main`, `develop` và workflow kiểm tra nhánh. Dùng bản clone có remote `origin` đúng repo; không chạy `git init` để thay thế bản clone hoặc tạo lại nhánh chung.

1. Fetch `origin` và kiểm tra `origin/develop`.
2. Tạo/nhận Issue thật. Khi working tree sạch, chạy `bash scripts/new-task-branch.sh <type> <issue> <task>` với giá trị thật.
3. Thực hiện thay đổi và kiểm thử phù hợp theo [hướng dẫn đóng góp](../CONTRIBUTING.md).
4. Push nhánh nhiệm vụ cùng tên và mở PR về `develop` bằng [mẫu chung](../.github/PULL_REQUEST_TEMPLATE.md).
5. Cập nhật checklist theo bằng chứng. Một thành viên khác review; required checks hiện có đạt và các trao đổi chặn được xử lý trước merge.
6. Người có quyền và được giao thực hiện merge. Chủ repo cấu hình bảo vệ nhánh; nội dung tài liệu không phải bằng chứng protections đã bật.

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
Workflow `branch-policy` chỉ kiểm tra tên nhánh và nhánh đích PR, không thay cho lint/build/test ứng dụng. Kiểm tra trạng thái từng lần chạy trên PR; các bài test chỉ chạy local phải được ghi rõ là local, không gọi là CI frontend xanh.
File workflow một mình không chặn push trực tiếp: phải bật bảo vệ nhánh.

Vũ Nguyễn Quỳnh Anh và Đoàn Thị Minh Khuê phụ trách điều phối; chưa có GitHub username tương ứng nên chưa cấu hình quyền riêng cho hai người này.
Với repo cá nhân, tổ chức việc merge release theo quy ước nhóm; nếu cần cưỡng chế quyền theo thành viên, chủ repo cấu hình ruleset/quyền phù hợp hoặc dùng repo tổ chức.

## Checklist trước review và merge

Dùng [PR template](../.github/PULL_REQUEST_TEMPLATE.md) và tuân thủ [AGENTS.md mục 8.4](../AGENTS.md#84-checklist-issue-và-pull-request). Tác giả cập nhật bằng chứng triển khai/kiểm chứng và checklist Issue; để trống phần chưa được reviewer hoặc GitHub xác nhận. Các điều kiện approval, required checks và quyền merge ở trên vẫn giữ nguyên. Không tích mục merge trước khi PR thực sự được merge.

## Release và dọn nhánh

Vũ Nguyễn Quỳnh Anh và Đoàn Thị Minh Khuê kiểm tra demo, CI và review rồi mở PR `develop → main`:

```bash
gh pr create --base main --head develop --title "Release: bản demo" --body "Mô tả các Issue đã hoàn thành và kết quả kiểm thử/demo."
```

Merge PR release bằng **Create a merge commit** để giữ lịch sử chung giữa `main` và `develop`.
Xóa nhánh nhiệm vụ sau khi merge; giữ `main` và `develop`.
Không squash/rebase PR release. PR nhiệm vụ mặc định squash theo quy trình nhóm.
