"""Issue #66: HTTP + CLIP/Qdrant + PostgreSQL + UI thật trên tài nguyên test riêng."""

import argparse
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from io import BytesIO
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import traceback
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from scripts.verify_text_search_api import verify


class VerificationFaults:
    """Chỉ gắn vào app do verifier tạo; không đưa route điều khiển vào sản phẩm.

    Không xóa/ghi index. DDL chỉ chạy trên engine của schema test do helper tạo.
    Các test tuần tự, không dùng controller này cho concurrent/load testing.
    """

    MODES = {"healthy", "missing_index", "incompatible_index", "db_read_failure", "db_write_failure"}

    def __init__(self):
        self.path = "/__verification/" + uuid4().hex
        self.mode = "healthy"

    def configure(self, app, db):
        assert db.schema.startswith("test_asset_api_") and (db.url.database or "").startswith("test_")
        self.app, self.db = app, db

        @app.post(self.path, include_in_schema=False)
        def set_mode(body: dict):
            from fastapi import HTTPException
            mode = body.get("mode")
            if mode not in self.MODES:
                raise HTTPException(400, "Unknown verification mode")
            self.change(mode)
            return {"mode": self.mode}

    def change(self, mode):
        if mode not in self.MODES:
            raise ValueError("Unknown verification mode")
        adapter = self.app.state.text_search_service
        assert adapter is not None, "Real runtime adapter required"
        with adapter.lock:
            store = adapter.service.store
            if not hasattr(self, "original_config"):
                self.original_config, self.original_collection = store.config, store.collection_name
            store.config, store.collection_name = self.original_config, self.original_collection
            with self.db.engine.begin() as connection:
                if self.mode == "db_read_failure":
                    connection.exec_driver_sql("ALTER TABLE issue66_assets_offline RENAME TO assets")
                if self.mode == "db_write_failure":
                    connection.exec_driver_sql("ALTER TABLE search_events DROP CONSTRAINT issue66_reject_event")
                self.mode = "healthy"
                if mode == "db_read_failure":
                    connection.exec_driver_sql("ALTER TABLE assets RENAME TO issue66_assets_offline")
                if mode == "db_write_failure":
                    connection.exec_driver_sql("ALTER TABLE search_events ADD CONSTRAINT issue66_reject_event CHECK (false) NOT VALID")
            if mode == "missing_index":
                store.collection_name = "__issue66_absent_collection_" + uuid4().hex
            elif mode == "incompatible_index":
                store.config = replace(store.config, model_revision="issue66-incompatible-revision")
            self.mode = mode


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def frontend_identity(directory, revision):
    """Xác minh source sản phẩm đúng SHA khai báo, kể cả bản export PR chưa merge."""
    archive = subprocess.check_output(["git", "archive", revision, "frontend"], cwd=ROOT)
    # Chỉ đọc archive Git trong bộ nhớ, không extract path ra filesystem.
    import tarfile
    files = {}
    with tarfile.open(fileobj=BytesIO(archive)) as bundle:
        for member in bundle.getmembers():
            if not member.isfile():
                continue
            relative = Path(member.name).relative_to("frontend")
            # Test/config của #66 có thể khác; xác minh toàn bộ src + public + build manifests.
            if relative.parts[0] not in {"src", "public"} and relative.name not in {"package.json", "package-lock.json", "vite.config.ts"}:
                continue
            if relative.name == "package.json":
                # #66 chỉ bổ sung npm script; deps/source được kiểm tra riêng.
                expected = json.loads(bundle.extractfile(member).read())
                actual = json.loads((directory / relative).read_text(encoding="utf-8"))
                for key in ("dependencies", "devDependencies"):
                    assert actual[key] == expected[key]
                continue
            expected = bundle.extractfile(member).read()
            actual = (directory / relative).read_bytes()
            assert actual == expected or actual.replace(b"\r\n", b"\n") == expected, str(relative)
            files[relative.as_posix()] = sha256(expected).hexdigest()
    assert files
    return sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def check_integration(app, db, manifest, metadata, origin, *, args, faults):
    import httpx
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from app.models import SearchEvent
    from app.schemas.text_search import TextSearchFilters

    observations = []
    row = next(r for r in metadata if r["category"] and r["formats"] and r["face_count"] is not None)
    filters = dict(category=row["category"], license=row["license"], format=row["formats"][0],
                   face_count_min=row["face_count"], face_count_max=row["face_count"])

    def count_events():
        with Session(db.engine) as session:
            return session.scalar(select(func.count()).select_from(SearchEvent))

    def check_event(body, payload):
        with Session(db.engine) as session:
            event = session.get(SearchEvent, UUID(body["search_event_id"]))
            assert event is not None and event.query_text == payload["query"]
            assert event.filters == payload.get("filters", {})
            assert all(getattr(event, key) == value for key, value in body["versions"].items())

    with httpx.Client(base_url=origin, timeout=90) as client:
        payloads = [dict(query="wooden chair", page=p, limit=6) for p in (1, 2, 34, 35)]
        payloads += [dict(query="chair", filters=filters),
                     dict(query="chair", filters={"category": "__issue66_no_category__"})]
        all_ids = []
        for payload in payloads:
            candidates = app.state.text_search_service.search_text(payload["query"],
                TextSearchFilters(**payload.get("filters", {})), candidate_limit=200)
            response = client.post("/api/v1/search/text", json=payload)
            assert response.status_code == 200
            body = response.json()
            start = (payload.get("page", 1) - 1) * payload.get("limit", 12)
            expected = candidates.hits[start:start + payload.get("limit", 12)]
            assert body["mock"] is False
            assert body["versions"] == candidates.versions.model_dump() == manifest.execution_versions().model_dump()
            assert body["pagination"]["total"] == len(candidates.hits)
            assert [r["asset"]["asset_id"] for r in body["results"]] == [h.asset_id for h in expected]
            assert [r["rank"] for r in body["results"]] == list(range(1, len(expected) + 1))
            assert all(abs(r["score"] - h.score) <= 1e-6 for r, h in zip(body["results"], expected))
            check_event(body, payload)
            observations.append(dict(payload=payload, status=200, total=len(candidates.hits),
                ids=[h.asset_id for h in expected], scores=[h.score for h in expected],
                search_event_id=body["search_event_id"]))
            if payload.get("page") in (1, 2):
                all_ids.extend(h.asset_id for h in expected)
        assert len(all_ids) == len(set(all_ids)) == 12
        baseline = count_events()
        for payload in ({"query": " "}, {"query": "chair", "page": 0},
                        {"query": "chair", "limit": 51}, {"query": "chair", "filters": {"face_count_min": -1}}):
            response = client.post("/api/v1/search/text", json=payload)
            assert response.status_code == 400 and response.json()["error"]["code"] == "INVALID_REQUEST"
        assert count_events() == baseline
        failures = []
        try:
            for mode, status in (("missing_index", 503), ("incompatible_index", 503),
                                 ("db_read_failure", 500), ("db_write_failure", 500)):
                baseline = count_events()
                faults.change(mode)
                response = client.post("/api/v1/search/text", json={"query": "wooden chair"})
                assert response.status_code == status, mode
                body = response.json()
                assert set(body) == {"error"} and body["error"]["code"]
                serialized = json.dumps(body).lower()
                assert not any(word in serialized for word in ("postgresql", "password", "traceback", "select ", "psycopg", "issue66_reject_event"))
                faults.change("healthy")
                assert count_events() == baseline
                payload = {"query": "wooden chair"}
                recovered = client.post("/api/v1/search/text", json=payload)
                assert recovered.status_code == 200
                check_event(recovered.json(), payload)
                assert count_events() == baseline + 1
                failures.append(dict(mode=mode, status=status, error=body, recovery_status=200))
            ui = run_ui(args, origin, faults.path, filters)
            for observation in ui.pop("http_observations"):
                if observation["status"] == 200:
                    check_event(observation["body"], observation["payload"])
            ui["successful_http_events_verified_in_postgresql"] = True
        finally:
            faults.change("healthy")
        # Bao gồm event từ UI: mọi event phải giữ phiên bản thật của snapshot.
        with Session(db.engine) as session:
            stored = session.scalars(select(SearchEvent)).all()
            assert all(all(getattr(event, key) == value for key, value in manifest.execution_versions().model_dump().items()) for event in stored)
        return dict(comparisons=observations, errors_and_recovery=failures,
                    invalid_requests_create_no_event=True, final_event_count=len(stored), ui=ui,
                    frontend_handoff=dict(api_origin=origin, cors_origins=args.ui_origins, filters=filters),
                    human_confirmation={"Duy": "pending", "Khue": "pending"})


def run_ui(args, origin, control_path, filters):
    environment = os.environ.copy()
    report = args.output.with_suffix(".playwright.json")
    environment.update(TEXT_SEARCH_API_URL=origin, TEXT_SEARCH_UI_PORT=str(args.ui_port),
        TEXT_SEARCH_CONTROL_URL=origin + control_path, TEXT_SEARCH_FILTERS=json.dumps(filters),
        TEXT_SEARCH_FRONTEND_DIR=str(args.frontend_dir.resolve()),
        PLAYWRIGHT_JSON_OUTPUT_FILE=str(report.resolve()))
    command = ["node", str(ROOT / "frontend/node_modules/@playwright/test/cli.js"), "test",
               "--config", "playwright.semantic.config.ts", "--reporter=list,json"]
    completed = subprocess.run(command, cwd=ROOT / "frontend", env=environment, timeout=480)
    assert completed.returncode == 0, "Real UI verification failed; inspect Playwright report."
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["stats"]["unexpected"] == result["stats"]["skipped"] == result["stats"]["flaky"] == 0
    observations = []

    def collect(suites):
        import base64
        for suite in suites:
            collect(suite.get("suites", []))
            for spec in suite.get("specs", []):
                for test in spec["tests"]:
                    for attempt in test["results"]:
                        for attachment in attempt.get("attachments", []):
                            if attachment["name"] == "real-text-search-http":
                                content = Path(attachment["path"]).read_bytes() if "path" in attachment else base64.b64decode(attachment["body"])
                                observations.extend(json.loads(content))

    collect(result["suites"])
    assert observations
    return dict(status="passed", stats=result["stats"], frontend_revision=args.frontend_revision,
        http_observations=observations, successful_http_requests=sum(x["status"] == 200 for x in observations),
        frontend_dir_mode="checkout" if args.frontend_dir.resolve() == (ROOT / "frontend").resolve() else "separate_export",
        browsers="Chrome desktop 1280x900 + mobile viewport 390x844", real_http_no_response_mocking=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("index-manifest", "index-root", "qdrant-local-path"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--frontend-dir", type=Path, default=ROOT / "frontend")
    parser.add_argument("--frontend-revision", required=True, help="SHA của source frontend kiểm chứng")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.ui_port = free_port()
    args.ui_origins = [f"http://127.0.0.1:{args.ui_port}"]
    faults = VerificationFaults()
    try:
        frontend_sha256 = frontend_identity(args.frontend_dir, args.frontend_revision)
        result = verify(args, configure_app=faults.configure,
            extra_checks=lambda *values: check_integration(*values, args=args, faults=faults))
        result["frontend_source_manifest_sha256"] = frontend_sha256
    except Exception as exc:
        result = dict(status="failed", error_code=type(exc).__name__)
        # Chỉ location, không dump exception/locals chứa connection string.
        result["failure_locations"] = [dict(file=Path(frame.filename).name, line=frame.lineno, function=frame.name)
            for frame in traceback.extract_tb(exc.__traceback__)]
    result.update(observed_at_utc=datetime.now(timezone.utc).isoformat(), platform=platform.platform(),
        base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        limits="Local CPU CLIP + persistent local Qdrant, disposable PostgreSQL schema; not remote Qdrant, benchmark, CI or human approval.")
    result["verification_source_sha256"] = {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), ROOT / "scripts/verify_text_search_api.py",
                  ROOT / "frontend/playwright.semantic.config.ts", ROOT / "frontend/tests/semantic/text-search.spec.ts",
                  ROOT / "frontend/tests/semantic/types.ts"]}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Issue #66: {result['status']}; report: {args.output}")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
