import csv
import json
import mimetypes
import uuid
import time
import hashlib
import platform
import sys
import math
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QUERY_FILE = REPO_ROOT / "data" / "benchmark" / "image_queries_v1.csv"


def load_image_queries() -> list[dict[str, str]]:
    queries: list[dict[str, str]] = []

    with QUERY_FILE.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        required_columns = {"query_id", "query_image_path"}
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            raise ValueError("CSV thiếu cột query_id hoặc query_image_path.")

        for row in reader:
            query_id = (row["query_id"] or "").strip()
            image_path = (row["query_image_path"] or "").strip()

            if not query_id or not image_path:
                raise ValueError("CSV có dòng thiếu query_id hoặc query_image_path.")

            resolved_image_path = (REPO_ROOT / image_path).resolve()
            if not resolved_image_path.is_file():
                raise FileNotFoundError(
                    f"Không tìm thấy ảnh cho {query_id}: {resolved_image_path}"
                )

            queries.append({
                "query_id": query_id,
                "query_image_path": str(resolved_image_path),
            })

    if len(queries) != 20:
        raise ValueError(f"Benchmark cần đúng 20 query, nhưng CSV có {len(queries)}.")

    return queries

IMAGE_SEARCH_URL = "http://127.0.0.1:8000/api/v1/search/image"


def post_image_search(
    image_path: str | Path,
    endpoint: str = IMAGE_SEARCH_URL,
) -> tuple[int, dict, float]:
    path = Path(image_path)
    boundary = f"----issue88-{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    parts: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        parts.extend([
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{name}"'.encode(),
            b"",
            value.encode(),
        ])

    image_bytes = path.read_bytes()
    parts.extend([
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{path.name}"'.encode(),
        f"Content-Type: {mime_type}".encode(),
        b"",
        image_bytes,
    ])
    add_field("filters", "{}")
    add_field("page", "1")
    add_field("limit", "10")
    parts.extend([f"--{boundary}--".encode(), b""])

    request = Request(
        endpoint,
        data=b"\r\n".join(parts),
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    started_ns = time.perf_counter_ns()

    with urlopen(request, timeout=60) as response:
        response_bytes = response.read()
        status = response.status
        elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000

    payload = json.loads(response_bytes.decode("utf-8"))
    return status, payload, elapsed_ms
def collect_samples(
    queries: list[dict[str, str]],
    *,
    warmup_count: int = 5,
    repetitions: int = 10,
    endpoint: str = IMAGE_SEARCH_URL,
) -> dict:
    if not queries:
        raise ValueError("Danh sách query không được để trống.")
    if warmup_count < 0 or repetitions < 1:
        raise ValueError("warmup_count phải >= 0 và repetitions phải >= 1.")

    warmup_query_ids: list[str] = []

    for index in range(warmup_count):
        query = queries[index % len(queries)]
        status, payload, _ = post_image_search(
            query["query_image_path"], endpoint
        )
        if status != 200 or payload.get("mock") is not False:
            raise RuntimeError(
                f"Warm-up thất bại cho {query['query_id']}: "
                f"status={status}, mock={payload.get('mock')}"
            )
        warmup_query_ids.append(query["query_id"])

    samples: list[dict] = []

    for query in queries:
        for repetition in range(1, repetitions + 1):
            status, payload, elapsed_ms = post_image_search(
                query["query_image_path"], endpoint
            )
            if status != 200 or payload.get("mock") is not False:
                raise RuntimeError(
                    f"Đo thất bại cho {query['query_id']}: "
                    f"status={status}, mock={payload.get('mock')}"
                )

            samples.append({
                "query_id": query["query_id"],
                "repetition": repetition,
                "client_round_trip_ms": elapsed_ms,
                "http_status": status,
                "search_event_id": payload.get("search_event_id"),
                "versions": payload.get("versions", {}),
            })

    return {
        "warmup_count": warmup_count,
        "warmup_query_ids": warmup_query_ids,
        "repetitions_per_query": repetitions,
        "samples": samples,
    }
def write_report(
    result: dict,
    output_path: str | Path,
    *,
    endpoint: str = IMAGE_SEARCH_URL,
) -> Path:
    queries = load_image_queries()
    latencies = sorted(
        float(sample["client_round_trip_ms"])
        for sample in result["samples"]
    )
    if not latencies:
        raise ValueError("Không có mẫu đo để tính percentile.")

    def nearest_rank(percentile: float) -> float:
        rank = math.ceil(percentile * len(latencies))
        return latencies[rank - 1]

    def sha256_file(path: str | Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "metric": "client_round_trip_ms",
            "timer": "time.perf_counter_ns()",
            "measurement_scope": (
                "Từ ngay trước khi gửi HTTP request đến khi đọc hết response body"
            ),
            "endpoint": endpoint,
            "method": "POST",
            "content_type": "multipart/form-data",
            "warmup_count": result["warmup_count"],
            "warmup_query_ids": result["warmup_query_ids"],
            "repetitions_per_query": result["repetitions_per_query"],
            "query_order": "CSV order",
            "filters": {},
            "page": 1,
            "limit": 10,
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "input": {
            "query_csv": str(QUERY_FILE.relative_to(REPO_ROOT)),
            "query_csv_sha256": sha256_file(QUERY_FILE),
            "queries": [
                {
                    "query_id": query["query_id"],
                    "query_image_path": str(
                        Path(query["query_image_path"]).relative_to(REPO_ROOT)
                    ),
                    "query_image_sha256": sha256_file(query["query_image_path"]),
                }
                for query in queries
            ],
        },
        "versions": (
            result["samples"][0]["versions"] if result["samples"] else {}
        ),
        "summary": {
            "method": "nearest-rank",
            "sample_count": len(latencies),
            "p50_ms": nearest_rank(0.50),
            "p95_ms": nearest_rank(0.95),
        },
        "samples": result["samples"],
    }

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination