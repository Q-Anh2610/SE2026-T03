"""#137: browser-facing header/CORS qua Uvicorn TCP thật, retrieval fixture."""

import json
import logging
from uuid import UUID

import httpx
import pytest

from app.core.config import Settings
from app.main import create_app
from app.services.text_search import SearchUnavailable
from scripts.verify_jobs_api import http_server

pytestmark = pytest.mark.integration
PRIVATE = "private-http-fixture-137"


def test_real_http_error_headers_and_logs_without_raw_server_trace(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="app.request")
    request_logger = logging.getLogger("app.request")
    monkeypatch.setattr(request_logger, "handlers", [*[h for h in request_logger.handlers if h is not caplog.handler], caplog.handler])

    class UnavailableRetrieval:
        def search_text(self, *_args, **_kwargs):
            raise SearchUnavailable(PRIVATE)

    key = "fixture-admin-key-137-http-not-a-real-secret"
    app = create_app(Settings(_env_file=None, env="test", text_search_source="service",
        admin_api_key=key), text_search_service=UnavailableRetrieval())

    @app.get("/fixture-unexpected/{item}")
    def fail(item: str):
        raise RuntimeError(PRIVATE)

    observed = []
    with http_server(app) as origin, httpx.Client(base_url=origin, timeout=10, headers={
        "Origin": "http://localhost:5173", "X-Request-ID": PRIVATE,
        "Authorization": "Bearer " + PRIVATE,
    }) as client:
        # Uvicorn config vừa cài handlers của nó; capture sau startup để kiểm
        # cả server log thực tế, không chỉ các records thuộc app.request.
        server_logger = logging.getLogger("uvicorn.error")
        monkeypatch.setattr(server_logger, "handlers", [*[h for h in server_logger.handlers if h is not caplog.handler], caplog.handler])
        cases = [
            ("GET", "/healthz", {}, 200, None),
            ("POST", "/api/v1/search/text", {"json": {"query": ""}}, 400, "INVALID_REQUEST"),
            ("GET", "/api/v1/admin/jobs", {}, 403, "ADMIN_ACCESS_DENIED"),
            ("GET", "/" + PRIVATE + "?token=" + PRIVATE, {}, 404, "HTTP_404"),
            ("POST", "/api/v1/search/text", {"json": {"query": PRIVATE}}, 503, "SEARCH_UNAVAILABLE"),
            ("GET", "/fixture-unexpected/" + PRIVATE, {}, 500, "INTERNAL_ERROR"),
            ("GET", "/healthz", {}, 200, None),
        ]
        for method, path, kwargs, status, code in cases:
            response = client.request(method, path, **kwargs)
            assert response.status_code == status
            identifier = response.headers["X-Request-ID"]
            assert UUID(identifier).version == 4
            assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
            assert "x-request-id" in response.headers["access-control-expose-headers"].lower()
            if code:
                assert response.json()["error"]["code"] == code
            else:
                assert response.json() == {"status": "ok"}
            observed.append((identifier, status, code))
    rows = [json.loads(record.getMessage()) for record in caplog.records if record.name == "app.request"]
    assert len(rows) == len(observed) == len({row[0] for row in observed})
    assert {(row["request_id"], row["status"], row["error_code"]) for row in rows} == set(observed)
    assert PRIVATE not in caplog.text and key not in caplog.text
    assert "Traceback" not in caplog.text
    assert app.state.db_engine is None
