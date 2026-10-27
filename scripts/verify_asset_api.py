"""Kiểm chứng Uvicorn/PostgreSQL và tùy chọn UI; chỉ dùng TEST_DATABASE_URL test_*."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.seed import seed_assets
from app.ingestion.db_writer import DatabaseWriter
from app.ingestion.pipeline import run_batch
from app.models import Asset
from scripts.asset_api_test_support import isolated_asset_database


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_health(url, process):
    for _ in range(60):
        if process.poll() is not None:
            raise RuntimeError("Uvicorn không khởi động được.")
        try:
            with urlopen(url + "/healthz", timeout=2) as response:
                if json.load(response) == {"status": "ok"}:
                    return
        except (URLError, TimeoutError, OSError):
            time.sleep(0.5)
    raise RuntimeError("Uvicorn chưa sẵn sàng sau thời gian chờ.")


def get_json(url):
    with urlopen(url, timeout=15) as response:
        return json.load(response)


def live_ingestion(database, directory, limit):
    writer = DatabaseWriter()
    writer.engine = database.engine
    manifest = ROOT / "data" / "manifests" / "objaverse_200.json"
    first_path = directory / "ingestion-first.json"
    first = run_batch(manifest, directory / "previews", first_path,
                      limit=limit, max_attempts=1, persist_asset=writer)
    if first["summary"]["failed"]:
        raise RuntimeError("Batch preview live có lỗi; chưa xác nhận ingestion thật.")
    second = run_batch(manifest, directory / "previews", directory / "ingestion-second.json",
                       limit=limit, max_attempts=1, persist_asset=writer, previous_report_path=first_path)
    if second["summary"]["failed"] or second["summary"]["skipped"] != limit:
        raise RuntimeError("Chạy lại batch live chưa đạt điều kiện tái sử dụng preview.")
    return {"limit": limit, "manifest_sha256": first["manifest_sha256"],
            "first": first["summary"], "second": second["summary"],
            "asset_ids": [item["asset_id"] for item in first["results"]]}


def verify(args):
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        raise ValueError("Cần TEST_DATABASE_URL tới PostgreSQL test_* riêng; không dùng DATABASE_URL phát triển.")
    result = {"verified_at_utc": datetime.now(timezone.utc).isoformat(),
              "python": sys.version.split()[0], "checks": {},
              "data": "fixture DB; không phải benchmark semantic"}
    with isolated_asset_database(value) as database, TemporaryDirectory(prefix="asset-api-verify-") as temporary:
        database.migrate()
        result["checks"]["migration_and_schema"] = "passed"
        with Session(database.engine) as session, session.begin():
            first = seed_assets(session)
        with Session(database.engine) as session, session.begin():
            second = seed_assets(session)
        if (first, second) != (7, 0):
            raise RuntimeError("Seed chưa đạt điều kiện idempotent.")
        result["checks"]["seed_first_second"] = [first, second]
        # Fixture riêng cho UI: 3 bản ghi, đủ kiểm tra filters/page/limit/quay lại.
        with Session(database.engine) as session, session.begin():
            session.add_all([Asset(asset_id=f"verify-{i}", source="fixture", source_id=f"verify-{i}",
                                   name=f"API integration asset {i}", category="issue49-fixture",
                                   license="fixture-only", formats=["glb"]) for i in (1, 2, 3)])
        if args.live_ingestion:
            result["live_ingestion"] = live_ingestion(database, Path(temporary), args.live_ingestion)
        port, ui_port = free_port(), free_port()
        api_url = f"http://127.0.0.1:{port}"
        environment = {**os.environ, "DATABASE_URL": database.url.render_as_string(hide_password=False),
                       "APP_ENV": "test", "APP_DEBUG": "false", "APP_ASSET_LIST_SOURCE": "database",
                       "APP_CORS_ORIGINS": json.dumps([f"http://127.0.0.1:{ui_port}"])}
        log_path = Path(temporary) / "uvicorn.log"
        with log_path.open("w", encoding="utf-8") as log:
            server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                                      cwd=ROOT / "backend", env=environment, stdout=log, stderr=log)
            try:
                wait_for_health(api_url, server)
                listing = get_json(api_url + "/api/v1/assets?category=issue49-fixture&limit=2&page=2")
                detail = get_json(api_url + "/api/v1/assets/verify-3")
                if listing["mock"] or detail["mock"] or listing["items"] != [detail["asset"]]:
                    raise RuntimeError("Response list/detail PostgreSQL chưa khớp.")
                if listing["pagination"] != {"page": 2, "limit": 2, "total": 3, "pages": 2, "has_next": False}:
                    raise RuntimeError("Phân trang chưa đúng.")
                for path, status, code in (("/assets?limit=0", 400, "INVALID_REQUEST"),
                                           ("/assets/missing-issue49", 404, "ASSET_NOT_FOUND")):
                    try:
                        get_json(api_url + "/api/v1" + path)
                        raise RuntimeError("API chưa trả lỗi mong đợi.")
                    except HTTPError as exc:
                        body = json.load(exc)
                        if exc.code != status or body["error"]["code"] != code or "details" not in body["error"]:
                            raise RuntimeError("Response lỗi không đúng contract.") from None
                if "live_ingestion" in result:
                    for identifier in result["live_ingestion"]["asset_ids"]:
                        asset = get_json(api_url + "/api/v1/assets/" + identifier)
                        if asset["mock"] or asset["asset"]["asset_id"] != identifier:
                            raise RuntimeError("Asset ingestion live chưa đọc được qua API.")
                    with Session(database.engine) as session:
                        count = session.scalar(select(func.count()).select_from(Asset))
                    if count != 10 + args.live_ingestion:
                        raise RuntimeError("Số bản ghi DB không khớp sau chạy lại ingestion.")
                    result["data"] = "fixture DB + subset Objaverse live; xem live_ingestion, không phải 200-asset benchmark"
                result["checks"]["uvicorn_postgresql_list_detail_filters_pagination_400_404"] = "passed"
                if args.ui:
                    ui_env = {**os.environ, "ASSET_API_TEST_URL": api_url,
                              "ASSET_API_UI_PORT": str(ui_port)}
                    npm = "npm.cmd" if os.name == "nt" else "npm"
                    subprocess.run([npm, "run", "test:database"], cwd=ROOT / "frontend",
                                   env=ui_env, check=True, timeout=180)
                    result["checks"]["frontend_postgresql_desktop_mobile"] = "passed"
                else:
                    result["checks"]["frontend_postgresql_desktop_mobile"] = "not_run; use --ui"
            finally:
                server.terminate()
                server.wait(timeout=15)
    result["checks"]["temporary_schema_cleanup"] = "passed"
    result["status"] = "passed"
    return result


def main():
    # Console Windows có thể dùng cp1252; báo cáo trên đĩa vẫn giữ UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui", action="store_true", help="Chạy Playwright desktop/mobile với API DB thật.")
    parser.add_argument("--live-ingestion", type=int, choices=range(1, 6), metavar="1..5",
                        help="Tùy chọn tải subset preview thật, tối đa 5 asset; không chạy trong CI.")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = args.report or ROOT / "data" / "processed" / ("asset-api-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
    if report.exists():
        parser.error("Báo cáo đã tồn tại; chọn tên mới để không ghi đè bằng chứng.")
    try:
        result = verify(args)
    except Exception as exc:
        # Không in traceback hoặc URL kết nối. Tên loại lỗi đủ để ghi nhận blocker.
        result = {"status": "failed", "error_type": type(exc).__name__,
                  "message": "Kiểm chứng chưa hoàn tất; kiểm tra DB test, dependencies và dịch vụ local."}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Asset API verification: {result['status']}. Report: {report}")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
