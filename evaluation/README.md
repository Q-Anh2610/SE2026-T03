# Evaluation CLI

CLI điều phối benchmark và gọi Search API của sản phẩm qua `ProductSearch` seam;
không có thuật toán retrieval riêng trong `evaluation/`. Adapter HTTP mặc định
gọi `POST /api/v1/search/text`.

## Cài đặt và chạy

CLI dùng thư viện chuẩn; pytest lấy từ môi trường phát triển backend. Từ gốc
repository trên Windows PowerShell, tạo môi trường Python 3.13 và cài dependencies
một lần (nếu `backend/.venv` đã có, bỏ qua lệnh tạo):

```powershell
py -3.13 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

Không chạy lại lệnh tạo venv nếu `backend/.venv` đã tồn tại.

Tất cả ví dụ dưới đây chạy từ gốc repository và gọi thẳng Python trong venv để
không phụ thuộc interpreter mặc định của terminal:

```powershell
backend\.venv\Scripts\python.exe -m evaluation --help
backend\.venv\Scripts\python.exe -m evaluation benchmark --config example.json --output evaluation/results/benchmark.json
backend\.venv\Scripts\python.exe -m evaluation metrics --input evaluation/results/benchmark.json --k 10
backend\.venv\Scripts\python.exe -m evaluation metrics --input evaluation/results/benchmark.json --k 10 --output evaluation/results/metrics.json
backend\.venv\Scripts\python.exe -m evaluation write-results --input evaluation/results/benchmark.json --output evaluation/results/copy.json
```

Với Linux/macOS, tạo venv bằng `python3.13 -m venv backend/.venv`, cài cùng
requirements và thay executable trong các ví dụ bằng `backend/.venv/bin/python`.

Để chạy benchmark, cần Search API của sản phẩm đang chạy tại URL cấu hình. Có
thể bật backend theo [backend README](../backend/README.md); lệnh Uvicorn cần chạy
trong terminal riêng từ `backend/`:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Config và dataset

Config mẫu [example.json](configs/example.json) được chọn bằng `--config example.json`;
CLI tìm tên config trong `evaluation/configs/`. Có thể truyền đường dẫn config
JSON đầy đủ. Các trường gồm `version`, `dataset_path`, `search_api_url`, `limit`,
`filters`, `seed` và `timeout_seconds`. `dataset_path` tương đối với gốc repo;
`search_api_url` là endpoint text search sản phẩm. Ví dụ config mẫu gọi
`http://127.0.0.1:8000/api/v1/search/text` và dùng
`data/benchmark/queries.jsonl`.

Dataset là JSONL, mỗi dòng một query và tập asset liên quan đã gán nhãn:

```json
{"query_id":"q-001","query":"wooden chair","relevant_asset_ids":["asset-123"]}
```

`benchmark` ghi JSON vào `evaluation/results/` theo mặc định; có thể chỉ định
đường dẫn bằng `--output`. Lỗi config/dataset/API in thông báo ngắn và trả mã
thoát khác 0. Config và dataset mẫu không tạo nhãn chuẩn giả; người dùng cần
cung cấp dữ liệu benchmark thật trước khi chạy.

## Lệnh

- `benchmark`: chạy queries qua adapter sản phẩm, ghi JSON vào `results/`.
- `metrics`: tính macro Recall@k và điểm từng query; metric mở rộng thuộc W2.
- `write-results`: đọc và ghi lại object JSON kết quả.

## Kiểm thử

Từ gốc repo, sau khi cài `requirements-dev.txt`, chạy evaluation tests:

```powershell
backend\.venv\Scripts\python.exe -m pytest -c evaluation/pytest.ini evaluation/tests
```

Chạy backend tests riêng (từ thư mục `backend/`):

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Kết quả benchmark lưu config, seed, thời gian chạy, Python/platform/machine,
versions API trả về và các ID truy xuất theo thứ tự. Kết quả trong `results/`
nên nhỏ, có provenance; không lưu model, index hoặc bulk data ở đây. Query và
nhãn chuẩn thuộc `data/benchmark/`, báo cáo diễn giải thuộc `docs/evaluation/`.
