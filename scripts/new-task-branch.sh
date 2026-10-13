#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 3 ]]; then
  echo 'Cách dùng: bash scripts/new-task-branch.sh <feat|fix|test|chore|docs> <issue> <task>' >&2
  exit 1
fi
type=$1
issue=$2
task=$3
[[ "$type" =~ ^(feat|fix|test|chore|docs)$ ]] || { echo 'Loại nhánh không hợp lệ.' >&2; exit 1; }
[[ "$issue" =~ ^[1-9][0-9]*$ ]] || { echo 'Issue phải là số nguyên dương.' >&2; exit 1; }
[[ "$task" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || { echo 'Task chỉ dùng chữ thường, số và dấu gạch ngang.' >&2; exit 1; }
git rev-parse --show-toplevel >/dev/null
if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Hãy commit hoặc stash thay đổi trước khi tạo nhánh.' >&2
  exit 1
fi
git fetch origin
branch="$type/$issue-$task"
if git show-ref --verify --quiet "refs/remotes/origin/$branch"; then
  echo 'Nhánh nhiệm vụ đã tồn tại trên remote; hãy dùng nhánh đó hoặc chọn task khác.' >&2
  exit 1
fi
git switch --no-track -c "$branch" origin/develop
echo "Đã tạo $branch từ origin/develop. Mở PR về develop sau khi hoàn thành."
