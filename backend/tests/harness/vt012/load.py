"""120 concurrent logical operations against one serialized local Qdrant fixture.

Fault/latency injection is synthetic. This is not a production capacity benchmark.
Run from repository root: python backend/tests/harness/vt012/load.py --output ...
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from importlib import metadata
import json
from math import ceil
from pathlib import Path
import platform
import sys
from threading import Barrier, Lock
from time import perf_counter, sleep


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qdrant_client import QdrantClient

from app.search.qdrant_store import QdrantStore
from support import config, embedding, timeout_error


class ServiceFixture:
    """One shared local data store; lock protects Qdrant local's mutable state."""

    def __init__(self, latency_seconds, concurrency):
        self.real = QdrantClient(location=":memory:")
        self.lock = Lock()
        self.attempts = {}
        self.latency_seconds = latency_seconds
        self.first_attempt_barrier = Barrier(concurrency)

    def collection_exists(self, name):
        with self.lock:
            return self.real.collection_exists(name)

    def create_collection(self, **kwargs):
        with self.lock:
            return self.real.create_collection(**kwargs)

    def get_collection(self, name):
        with self.lock:
            return self.real.get_collection(name)

    def upsert(self, **kwargs):
        asset_id = kwargs["points"][0].payload["asset_id"]
        number = int(asset_id.split("-")[1])
        with self.lock:
            attempt = self.attempts.get(asset_id, 0) + 1
            self.attempts[asset_id] = attempt
        if attempt == 1:
            # Tất cả 120 lời gọi phải đang ở trong upsert trước khi xử lý I/O.
            self.first_attempt_barrier.wait(timeout=30)
        sleep(self.latency_seconds)
        with self.lock:
            # 10% first attempts partially write; another 10% write all then timeout.
            inject = attempt == 1 and number % 5 == 0
            if inject and number % 10 == 0:
                self.real.upsert(**{**kwargs, "points": kwargs["points"][:1]})
            else:
                result = self.real.upsert(**kwargs)
            if inject:
                raise timeout_error()
            return result


def run_round(concurrency, latency_seconds):
    service = ServiceFixture(latency_seconds, concurrency)
    seed = QdrantStore(service, collection_name="vt012_load", config=config(), retry_delay=0.01)
    seed.ensure_collection()
    barrier = Barrier(concurrency)
    state_lock = Lock()
    active = 0
    max_active = 0

    def task(index):
        nonlocal active, max_active
        barrier.wait(timeout=30)
        started = perf_counter()
        with state_lock:
            active += 1
            max_active = max(max_active, active)
        try:
            store = QdrantStore(service, collection_name="vt012_load", config=config(), retry_delay=0.01)
            result = store.upsert([embedding(f"task-{index}-a"), embedding(f"task-{index}-b")])
            error = None
            if result != 2:
                error = "unexpected point count returned"
        except Exception as exc:
            error = type(exc).__name__
        finally:
            with state_lock:
                active -= 1
        return {"task": index, "seconds": perf_counter() - started, "error": error}

    started = perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            samples = list(pool.map(task, range(concurrency)))
        points, _ = service.real.scroll("vt012_load", limit=concurrency * 2 + 1)
        actual = {point.payload["asset_id"] for point in points}
        expected = {f"task-{i}-{suffix}" for i in range(concurrency) for suffix in ("a", "b")}
        all_seconds = sorted(item["seconds"] for item in samples)
        return {
            "concurrency": concurrency, "observed_max_active": max_active,
            "elapsed_seconds": perf_counter() - started,
            "p50_seconds": all_seconds[ceil(0.50 * len(samples)) - 1],
            "p95_seconds": all_seconds[ceil(0.95 * len(samples)) - 1],
            "max_seconds": max(all_seconds),
            "errors": sum(item["error"] is not None for item in samples),
            "upsert_attempts": sum(service.attempts.values()),
            "point_count": len(points), "expected_point_count": len(expected),
            "exact_asset_set": actual == expected,
            "unique_point_ids": len({str(point.id) for point in points}) == len(expected),
            "samples": samples,
        }
    finally:
        service.real.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=120)
    args = parser.parse_args()
    if args.rounds < 1 or args.concurrency < 1:
        parser.error("rounds/concurrency must be positive")
    rounds = [run_round(args.concurrency, 0.020) for _ in range(args.rounds)]
    report = {
        "scope": "synthetic local Qdrant fixture; not production Qdrant server / model / PostgreSQL / UI",
        "environment": {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(), "qdrant_client": metadata.version("qdrant-client")},
        "data": "self-created 3D vectors, two asset points per logical operation",
        "configuration": {"rounds": args.rounds, "concurrency": args.concurrency, "per_attempt_injected_latency_seconds": 0.020, "first_attempt_failure_percent": 20, "retry_delay_seconds": 0.010, "max_attempts": 3, "percentile": "nearest-rank; all completed tasks including errors; starts after barrier before store call"},
        "rounds": rounds,
        "harness_target_met": all(r["errors"] == 0 and r["p95_seconds"] <= 3.5 and r["exact_asset_set"] and r["unique_point_ids"] and r["observed_max_active"] == args.concurrency for r in rounds),
        "production_target_status": "not measured",
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "rounds": [{k: v for k, v in r.items() if k != "samples"} for r in rounds]}, ensure_ascii=False, indent=2))
    return 0 if report["harness_target_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
