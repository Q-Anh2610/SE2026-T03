"""#136: lỗi parser HTTP phải dùng cùng error envelope với validation DTO."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

KEY = "fixture-admin-key-136-not-a-real-secret"


@pytest.mark.parametrize("live", [False, True], ids=["mock", "service"])
@pytest.mark.parametrize("path,content,content_type", [
    ("/api/v1/search/text", b'\xff', "application/json"),
    ("/api/v1/feedback", b'\xff', "application/json"),
    ("/api/v1/admin/reindex", b'\xff', "application/json"),
    ("/api/v1/search/image", b'private-parser-input', "multipart/form-data"),
])
def test_body_parser_failure_is_invalid_request_before_db(live, path, content, content_type):
    settings = Settings(_env_file=None, env="test", admin_api_key=KEY,
        text_search_source="service" if live else "mock",
        image_search_source="service" if live else "mock",
        feedback_source="database" if live else "mock")
    # Không gọi retrieval cho body lỗi; không nạp encoder hoặc dùng DB/model thật.
    app = create_app(settings, text_search_service=object(), image_search_service=object())
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(path, content=content,
            headers={"Content-Type": content_type, "X-Admin-Key": KEY})
        assert response.status_code == 400
        assert response.json() == {"error": {"code": "INVALID_REQUEST",
            "message": "Yêu cầu không hợp lệ.", "details": []}}
        assert app.state.db_engine is None
        assert app.state.reindex_manager is None
        assert client.get("/healthz").json() == {"status": "ok"}


def test_unexpected_exception_and_non_400_http_errors_keep_safe_envelopes():
    app = create_app(Settings(_env_file=None, env="test"))

    @app.get("/fixture-failure")
    def fail():
        raise RuntimeError("private SQL password=fixture-private-value")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/fixture-failure")
        assert response.status_code == 500
        assert response.json()["error"] == {"code": "INTERNAL_ERROR",
            "message": "Lỗi máy chủ. Vui lòng thử lại sau.", "details": []}
        assert client.get("/route-does-not-exist").json()["error"]["code"] == "HTTP_404"
        unsupported = client.post("/healthz")
        assert unsupported.status_code == 405
        assert unsupported.json()["error"]["code"] == "HTTP_405"
        assert unsupported.headers["allow"] == "GET"
