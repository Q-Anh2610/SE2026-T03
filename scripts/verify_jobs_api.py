"""Smoke #115: Uvicorn/HTTP + PostgreSQL + ingestion preview thật trên DB test riêng."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import socket
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


@contextmanager
def http_server(app, *, startup_timeout=30, shutdown_timeout=15):
    import uvicorn

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + startup_timeout
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(.05)
            if not server.started:
                raise RuntimeError("Uvicorn chưa sẵn sàng.")
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            thread.join(timeout=shutdown_timeout)
            if thread.is_alive():
                raise RuntimeError("Uvicorn chưa dừng.")


def verify(args):
    import httpx
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from app.core.config import Settings
    from app.ingestion.db_writer import DatabaseWriter
    from app.main import create_app
    from app.models import Asset
    from app.services.job_runner import execute_job, ingestion_operation
    from scripts.asset_api_test_support import isolated_asset_database

    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        raise ValueError("Cần TEST_DATABASE_URL tới PostgreSQL test_* riêng.")
    report = {"issue": 115, "verified_at_utc": datetime.now(timezone.utc).isoformat(),
              "python": sys.version.split()[0], "jobs": [],
              "limits": "Ingestion preview thật trên subset nhỏ; chưa chạy indexing CLIP thật hoặc Admin UI; chờ owner xác nhận contract."}
    key = secrets.token_urlsafe(32)
    with isolated_asset_database(value) as db, TemporaryDirectory(prefix="issue115-") as temporary:
        db.migrate()
        settings = Settings(_env_file=None, env="test", mock_api_enabled=False, admin_api_key=key,
                            text_search_source="mock", image_search_source="mock", feedback_source="mock")
        app = create_app(settings)
        app.state.db_engine = db.engine
        writer = DatabaseWriter()
        writer.engine = db.engine
        directory = Path(temporary)
        with http_server(app) as origin, httpx.Client(base_url=origin, timeout=30) as api:
            headers = {"X-Admin-Key": key}
            assert api.get("/api/v1/admin/jobs").status_code == 403
            assert api.get("/api/v1/admin/jobs", headers=headers).json()["items"] == []
            observed_running = []
            for attempt in (1, 2):
                def operation():
                    live = api.get("/api/v1/admin/jobs?status=running", headers=headers).json()["items"]
                    observed_running.extend(live)
                    return ingestion_operation(manifest_path=args.manifest, output_dir=directory / "previews",
                        report_path=directory / f"batch-{attempt}.json", max_attempts=1,
                        limit=args.live_ingestion, persist_asset=writer,
                        previous_report_path=directory / "batch-1.json" if attempt == 2 else None)
                identifier, success = execute_job(db.engine, kind="ingestion", runner="ingestion.run_batch", operation=operation)
                response = api.get(f"/api/v1/admin/jobs/{identifier}", headers=headers)
                assert response.status_code == 200
                report["jobs"].append(response.json()["job"])
                if not success:
                    raise RuntimeError("Ingestion thật thất bại; không xác nhận smoke thành công.")
            assert len(observed_running) == 2
            assert all(row["status"] == "running" and row["progress"]["percent"] is None for row in observed_running)
            assert report["jobs"][0]["result"]["succeeded"] == args.live_ingestion
            assert report["jobs"][1]["result"]["skipped"] == args.live_ingestion
            with Session(db.engine) as reader:
                assert reader.scalar(select(func.count()).select_from(Asset)) == args.live_ingestion
            # Lỗi thật (manifest không tồn tại), không gọi downloader hoặc tạo dữ liệu giả.
            failed_id, success = execute_job(db.engine, kind="ingestion", runner="ingestion.run_batch",
                operation=lambda: ingestion_operation(manifest_path=directory / "missing.json",
                    output_dir=directory / "previews", report_path=directory / "failed.json"))
            assert not success
            failed = api.get(f"/api/v1/admin/jobs/{failed_id}", headers=headers).json()["job"]
            assert failed["error"]["code"] == "RUNNER_FAILED"
            report["jobs"].append(failed)
            filtered = api.get("/api/v1/admin/jobs?status=succeeded&kind=ingestion&limit=1", headers=headers).json()
            assert filtered["pagination"]["total"] == 2 and filtered["pagination"]["has_next"]
            assert api.get("/api/v1/admin/jobs?limit=0", headers=headers).status_code == 400
            report["running_observed"] = len(observed_running)
            report["checks"] = "HTTP auth/validation/list/detail/filter/pagination, real ingestion, rerun, failure: passed"
        # Khởi tạo app mới đọc cùng lịch sử PostgreSQL, không dùng store trong RAM.
        restarted = create_app(settings)
        restarted.state.db_engine = db.engine
        with http_server(restarted) as origin, httpx.Client(base_url=origin, timeout=30) as api:
            assert api.get("/api/v1/admin/jobs", headers={"X-Admin-Key": key}).json()["pagination"]["total"] == 3
            report["restart_persistence"] = "passed"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Jobs API live ingestion smoke passed; report: " + str(args.output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/manifests/objaverse_200.json")
    parser.add_argument("--live-ingestion", type=int, choices=range(1, 4), required=True,
                        help="Đồng ý tải 1–3 preview thật từ manifest.")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/issue115/jobs-api-report.json")
    args = parser.parse_args()
    verify(args)


if __name__ == "__main__":
    main()
