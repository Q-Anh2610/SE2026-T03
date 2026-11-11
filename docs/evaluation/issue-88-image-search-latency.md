# Issue #88: W4 image-search latency

## Protocol

- Input: 20 ảnh từ `data/benchmark/image_queries_v1.csv`, theo thứ tự CSV.
- Endpoint: `POST /api/v1/search/image`, gửi ảnh bằng `multipart/form-data`.
- Warm-up: 5 request tổng cộng, không đưa vào percentile.
- Đo: 10 request cho mỗi ảnh, tổng cộng 200 mẫu.
- Metric: `client_round_trip_ms`, đo bằng `time.perf_counter_ns()` từ ngay trước khi gửi request đến khi đọc hết response body.
- Request parameters: `filters={}`, `page=1`, `limit=10`.
- Percentile: nearest-rank trên toàn bộ 200 mẫu.

## Result

- HTTP status: 200 cho cả 200 mẫu.
- p50: 247.7765 ms.
- p95: 367.5851 ms.
- Raw samples và môi trường: [issue88-image-latency-2026-11-11.json](../../evaluation/results/issue88-image-latency-2026-11-11.json).

## API versions

- Model: `openai/clip-vit-base-patch32@3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`
- Index: `issue89-clip-preflight-76d5d2c095b6`
- Config: `image-exact-all-filtered-rgb-v1-k200`
- Dataset snapshot: `home-interior-clear-200-v3-sha256:9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`

## Reproduce

From the repository root, with the local API running and configured to use the isolated Issue #88 database:

```powershell
backend\.venv\Scripts\python.exe -c "from evaluation.image_latency import load_image_queries, collect_samples, write_report; result = collect_samples(load_image_queries()); path = write_report(result, 'evaluation/results/issue88-image-latency-2026-11-11.json'); print('warmups:', result['warmup_count']); print('samples:', len(result['samples'])); print('report:', path)"

```

## Limitations

`client_round_trip_ms` là thời gian HTTP round-trip phía client, không phải latency xử lý riêng bên server. Số đo bao gồm việc gửi request, xử lý phía server và nhận response; không bao gồm đọc file ảnh và dựng request body. Đây là kết quả của một lần chạy local trên 20 query, không phải cam kết latency tổng quát. Benchmark được chạy thủ công, không chạy trong CI.