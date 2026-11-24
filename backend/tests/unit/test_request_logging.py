"""#137: header/context/JSON allowlist, ASGI errors và CORS, không dùng DB/model."""

import asyncio
from io import BytesIO
import json
import logging
import traceback
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import httpx
import pytest
from PIL import Image

from app.core.config import Settings
from app.core.request_logging import RequestLoggingMiddleware, current_trace, log_request_error
from app.main import create_app
from app.services.text_search import SearchUnavailable

KEY = "fixture-admin-key-137-not-a-real-secret"
PRIVATE = "private-input-137-password"


@pytest.fixture(autouse=True)
def capture_request_logger(caplog, monkeypatch):
    logger = logging.getLogger("app.request")
    monkeypatch.setattr(logger, "handlers", [*[h for h in logger.handlers if h is not caplog.handler], caplog.handler])


def application(**options):
    return create_app(Settings(_env_file=None, env="test", asset_list_source="fixture",
        admin_api_key=KEY, **options), text_search_service=object(), image_search_service=object())


def records(caplog):
    return [json.loads(record.getMessage()) for record in caplog.records
            if record.name.startswith("app.") and record.getMessage().startswith("{")]


def completed(caplog):
    return [row for row in records(caplog) if row["event"] == "request.completed"]


@pytest.mark.parametrize("supplied", [None, str(uuid4()), "not-a-uuid", PRIVATE * 100])
def test_server_generates_id_ignores_incoming_header_and_keeps_body(supplied, caplog):
    caplog.set_level(logging.INFO, logger="app.request")
    with TestClient(application()) as client:
        response = client.get("/healthz", headers={"X-Request-ID": supplied} if supplied else {})
        assert response.json() == {"status": "ok"}
        identifier = response.headers["X-Request-ID"]
        assert UUID(identifier).version == 4 and identifier != supplied
        assert len(response.headers.get_list("X-Request-ID")) == 1
    row, = completed(caplog)
    assert row["request_id"] == identifier
    assert (row["method"], row["route"], row["status"], row["level"]) == ("GET", "/healthz", 200, "INFO")
    assert row["outcome"] == "completed" and row["error_code"] is None
    assert isinstance(row["duration_ms"], (float, int)) and row["duration_ms"] >= 0
    assert current_trace.get() is None
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize("case,status,code,stage", [
    ("validation", 400, "INVALID_REQUEST", "validation"),
    ("parser", 400, "INVALID_REQUEST", "validation"),
    ("authorization", 403, "ADMIN_ACCESS_DENIED", "authorization"),
    ("missing", 404, "HTTP_404", "http"),
    ("method", 405, "HTTP_405", "http"),
    ("unexpected", 500, "INTERNAL_ERROR", "unhandled"),
])
def test_error_summary_matches_response_without_private_input(case, status, code, stage, caplog):
    caplog.set_level(logging.INFO, logger="app.request")
    app = application()

    @app.get("/fixture-failure/{item}")
    def fail(item: str):
        raise RuntimeError(PRIVATE)

    # Unexpected 500 được gửi an toàn, không đẩy raw exception về ASGI server.
    with TestClient(app) as client:
        if case == "validation":
            response = client.post("/api/v1/search/text", json={"query": "", "private": PRIVATE})
        elif case == "parser":
            response = client.post("/api/v1/search/text", content=b'\xff', headers={"Content-Type": "application/json"})
        elif case == "authorization":
            response = client.get("/api/v1/admin/jobs", headers={"X-Admin-Key": PRIVATE})
        elif case == "missing":
            response = client.get("/" + PRIVATE + "?password=" + PRIVATE)
        elif case == "method":
            response = client.post("/healthz")
        else:
            response = client.get("/fixture-failure/" + PRIVATE)
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        row, = completed(caplog)
        assert row["request_id"] == response.headers["X-Request-ID"]
        assert (row["status"], row["error_code"], row["stage"]) == (status, code, stage)
        assert row["level"] == ("ERROR" if status == 500 else "WARNING")
        if case == "unexpected":
            assert row["route"] == "/fixture-failure/{item}" and row["outcome"] == "failed"
        assert app.state.db_engine is None
    assert PRIVATE not in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.parametrize("error,status,code,stage", [
    (SearchUnavailable(PRIVATE), 503, "SEARCH_UNAVAILABLE", "retrieval"),
    (RuntimeError(PRIVATE), 500, "INTERNAL_ERROR", "text_retrieval"),
])
def test_sync_retrieval_thread_error_and_summary_share_id(error, status, code, stage, caplog):
    caplog.set_level(logging.INFO, logger="app.request")

    class FailingRetrieval:
        def search_text(self, *_args, **_kwargs):
            raise error

    app = application(text_search_source="service")
    app.state.text_search_service = FailingRetrieval()
    with TestClient(app) as client:
        response = client.post("/api/v1/search/text", json={"query": PRIVATE})
        assert response.status_code == status
        identifier = response.headers["X-Request-ID"]
        rows = records(caplog)
        assert all(row["request_id"] == identifier for row in rows)
        assert all(row["stage"] == stage for row in rows)
        assert all(row["error_code"] == code for row in rows)
        assert len(rows) == (2 if status == 500 else 1)
        assert app.state.db_engine is None
    assert PRIVATE not in caplog.text


def test_body_headers_query_and_asset_path_are_not_logged(caplog):
    caplog.set_level(logging.INFO, logger="app.request")
    with TestClient(application()) as client:
        for _ in range(2):
            response = client.post("/api/v1/search/text?", json={"query": PRIVATE},
                headers={"X-Admin-Key": KEY, "Authorization": "Bearer " + PRIVATE})
            assert response.status_code == 200
        client.get("/api/v1/assets/" + PRIVATE + "?token=" + PRIVATE)
    rows = completed(caplog)
    assert len(rows) == 3 and len({row["request_id"] for row in rows}) == 3
    assert rows[-1]["route"] == "/api/v1/assets/{asset_id}"
    assert PRIVATE not in caplog.text and KEY not in caplog.text
    assert not any(key in row for row in rows for key in ("headers", "body", "query", "path", "url", "exception"))


def test_concurrent_contexts_are_isolated_and_reset(caplog):
    caplog.set_level(logging.INFO, logger="app.request")
    app = application()

    @app.get("/fixture-interleave/{item}")
    async def interleave(item: str):
        before = current_trace.get().request_id
        await asyncio.sleep(.01)
        assert current_trace.get().request_id == before
        return {"request_id": before}

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            responses = await asyncio.gather(*(client.get(f"/fixture-interleave/{i}") for i in range(12)))
            for response in responses:
                assert response.json()["request_id"] == response.headers["X-Request-ID"]
            assert len({response.headers["X-Request-ID"] for response in responses}) == 12
        assert current_trace.get() is None

    asyncio.run(run())
    assert len(completed(caplog)) == 12
    assert {row["route"] for row in completed(caplog)} == {"/fixture-interleave/{item}"}


@pytest.mark.parametrize("valid", [True, False])
def test_upload_remains_readable_and_does_not_log_bytes_or_filename(valid, caplog):
    caplog.set_level(logging.INFO, logger="app.request")
    image = BytesIO()
    Image.new("RGB", (4, 4)).save(image, "PNG")
    content = image.getvalue() if valid else PRIVATE.encode()
    with TestClient(application()) as client:
        response = client.post("/api/v1/search/image", files={"image": (PRIVATE + ".png", content)})
        assert response.status_code == (200 if valid else 400)
    row, = completed(caplog)
    assert row["route"] == "/api/v1/search/image" and row["request_id"] == response.headers["X-Request-ID"]
    assert PRIVATE not in caplog.text


def test_database_initialization_error_log_is_correlated(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="app.request")

    def fail(_settings):
        raise ValueError(PRIVATE)

    monkeypatch.setattr("app.db.dependencies.create_db_engine", fail)
    app = create_app(Settings(_env_file=None, env="test", mock_api_enabled=False))
    with TestClient(app) as client:
        response = client.get("/api/v1/assets")
        assert response.status_code == 500
    rows = records(caplog)
    assert len(rows) == 2 and {row["request_id"] for row in rows} == {response.headers["X-Request-ID"]}
    assert {row["stage"] for row in rows} == {"database"}
    assert PRIVATE not in caplog.text


def test_reindex_submission_error_has_safe_phase_and_request_id(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="app.request")

    def fail(_settings):
        raise ValueError(PRIVATE)

    monkeypatch.setattr("app.api.reindex.validate_configuration", lambda _settings: None)
    monkeypatch.setattr("app.api.reindex.create_db_engine", fail)
    with TestClient(application()) as client:
        response = client.post("/api/v1/admin/reindex", json={"request_id": str(uuid4())},
                               headers={"X-Admin-Key": KEY})
        assert response.status_code == 500
    rows = records(caplog)
    assert len(rows) == 2
    assert {row["request_id"] for row in rows} == {response.headers["X-Request-ID"]}
    assert {row["stage"] for row in rows} == {"reindex_submission"}
    assert PRIVATE not in caplog.text and KEY not in caplog.text


@pytest.mark.parametrize("path,status", [("/healthz", 200), ("/missing", 404), ("/fixture-failure", 500)])
def test_cors_exposes_request_id_on_success_and_errors(path, status):
    app = application()

    @app.get("/fixture-failure")
    def fail():
        raise RuntimeError(PRIVATE)

    with TestClient(app) as client:
        response = client.get(path, headers={"Origin": "http://localhost:5173"})
        assert response.status_code == status
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "x-request-id" in response.headers["access-control-expose-headers"].lower()
        assert UUID(response.headers["X-Request-ID"]).version == 4


def test_cors_preflight_permissions_and_disallowed_origin_stay_restricted():
    with TestClient(application()) as client:
        allowed = client.options("/api/v1/admin/jobs", headers={"Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "X-Admin-Key"})
        assert allowed.status_code == 200
        denied = client.get("/healthz", headers={"Origin": "https://untrusted.example"})
        assert "access-control-allow-origin" not in denied.headers
        # ID chỉ trả về từ server, không bổ sung quyền gửi header ID từ browser.
        supplied_id = client.options("/healthz", headers={"Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "X-Request-ID"})
        assert supplied_id.status_code == 400
    with TestClient(application(cors_origins=[])) as client:
        assert "access-control-allow-origin" not in client.get("/healthz").headers


@pytest.mark.parametrize("complete", [False, True], ids=["stream-abort", "after-body-error"])
def test_after_start_failure_never_logs_success_or_leaks_exception(complete, caplog):
    caplog.set_level(logging.INFO, logger="app.request")

    async def broken(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"prefix", "more_body": not complete})
        raise RuntimeError(PRIVATE)

    messages = []

    async def send(message):
        messages.append(message)

    async def run():
        middleware = RequestLoggingMiddleware(broken)
        if complete:
            await middleware({"type": "http", "method": "GET"}, None, send)
        else:
            with pytest.raises(RuntimeError) as caught:
                await middleware({"type": "http", "method": "GET"}, None, send)
            assert PRIVATE not in "".join(traceback.format_exception(caught.value))
        assert current_trace.get() is None

    asyncio.run(run())
    row, = completed(caplog)
    assert row["level"] == "ERROR" and row["status"] == 200
    assert row["outcome"] == ("failed" if complete else "aborted")
    assert len(messages) == 2 and PRIVATE not in caplog.text


def test_cancellation_propagates_and_context_resets(caplog):
    caplog.set_level(logging.INFO, logger="app.request")

    async def cancelled(scope, receive, send):
        raise asyncio.CancelledError(PRIVATE)

    async def run():
        with pytest.raises(asyncio.CancelledError):
            await RequestLoggingMiddleware(cancelled)({"type": "http", "method": "GET"}, None, None)
        assert current_trace.get() is None

    asyncio.run(run())
    row, = completed(caplog)
    assert row["stage"] == "cancelled" and row["status"] is None and row["outcome"] == "aborted"
    assert PRIVATE not in caplog.text


def test_factory_does_not_duplicate_console_handler_or_modify_root(caplog):
    caplog.set_level(logging.INFO, logger="app.request")
    root = logging.getLogger()
    handlers = list(root.handlers)
    for _ in range(3):
        with TestClient(application()) as client:
            client.get("/healthz")
    assert list(root.handlers) == handlers
    logger = logging.getLogger("app.request")
    assert sum(bool(getattr(handler, "request_trace_handler", False)) for handler in logger.handlers) == 1
    assert len(completed(caplog)) == 3
    log_request_error(logging.getLogger("app.fixture"), "fixture outside request", stage="fixture")
    assert records(caplog)[-1]["request_id"] is None
