"""python -m tests.harness.vt009.load is not required: run this file directly."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
from threading import Barrier
from time import perf_counter

# Executable from repository root without installing a new package.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))  # backend
sys.path.insert(0, str(HERE))
from support import AUTH_ADMIN, environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    parser.add_argument("--waves", type=int, default=3)
    args = parser.parse_args()
    args.temp_root.mkdir(parents=True, exist_ok=True)
    rows = []
    with TemporaryDirectory(dir=args.temp_root) as directory:
        with environment(Path(directory)) as (boundary, http, _):
            response = http.put("/harness/config", json={"candidate_limit": 10}, headers=AUTH_ADMIN)
            assert response.status_code == 200
            for _ in range(5):
                assert http.post("/harness/search", json={"query": "chair"}).status_code == 200
            for wave in range(args.waves):
                barrier = Barrier(201, timeout=60)
                def request(index):
                    barrier.wait()
                    start = perf_counter()
                    error, status, correct = None, None, False
                    try:
                        response = http.post("/harness/search", json={"query": "chair"})
                        status = response.status_code
                        body = response.json()
                        correct = (status == 200 and
                            [h["asset_id"] for h in body.get("hits", [])] == [f"a{i:03}" for i in range(10)] and
                            body["versions"]["config_version"].endswith("-k10"))
                    except Exception as exc:
                        error = type(exc).__name__
                    return {"wave": wave + 1, "task": index, "seconds": perf_counter()-start,
                            "status": status, "business_correct": correct, "error": error}
                with ThreadPoolExecutor(max_workers=200) as executor:
                    futures = [executor.submit(request, i) for i in range(200)]
                    barrier.wait()
                    rows.extend(f.result(timeout=60) for f in futures)
    values = sorted(r["seconds"] for r in rows)
    percentile = lambda p: values[math.ceil(p * len(values)) - 1]
    summary = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "baseline": "63122a3a05a920a847793253a4527a871d5aa6e8",
        "python": sys.version, "platform": platform.platform(),
        "processor": platform.processor(), "logical_cpus": os.cpu_count(),
        "packages": {name: importlib.metadata.version(name) for name in
                     ("fastapi", "starlette", "pydantic", "qdrant-client", "pytest")},
        "concurrency": 200, "waves": args.waves, "requests": len(rows),
        "warmups_excluded": 5, "fixture_points": 205, "vector_dimension": 3,
        "encoder": "constant synthetic normalized vector; NOT real CLIP",
        "transport": "FastAPI TestClient ASGI in-process, no TCP/PostgreSQL/UI",
        "timing": "after release barrier to response parsed/checked; includes adapter lock queue",
        "percentile_method": "nearest rank ceil(p*n), all tasks including errors",
        "p50_seconds": percentile(.50), "p95_seconds": percentile(.95),
        "max_seconds": max(values), "business_errors": sum(not r["business_correct"] for r in rows),
        "per_wave_p95_seconds": [sorted(r["seconds"] for r in rows if r["wave"] == w)[189]
                                  for w in range(1, args.waves+1)],
        "target_seconds": 5.0,
        "harness_target_met": percentile(.95) <= 5 and all(r["business_correct"] for r in rows),
        "production_conclusion": "Not established: requires real encoder, dataset, HTTP, DB, hardware and sustained workload",
        "raw": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k != "raw"}, indent=2))


if __name__ == "__main__":
    main()
