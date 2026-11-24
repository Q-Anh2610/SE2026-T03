"""Request tracing ASGI: JSON allowlist, không đọc body/query/header đầu vào."""

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

REQUEST_HEADER = "X-Request-ID"
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"}


@dataclass
class RequestTrace:
    scope: dict
    request_id: str
    started: float
    status: int | None = None
    error_code: str | None = None
    stage: str | None = None


current_trace: ContextVar[RequestTrace | None] = ContextVar("request_trace", default=None)


def mark_request_error(code: str, stage: str, *, overwrite: bool = True) -> None:
    trace = current_trace.get()
    if trace is not None and (overwrite or trace.error_code is None):
        trace.error_code, trace.stage = code, stage


def _payload(logger, event, *, code=None, stage=None):
    trace = current_trace.get()
    route = trace.scope.get("route") if trace else None
    method = trace.scope.get("method") if trace else None
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "component": logger.name,
        "request_id": trace.request_id if trace else None,
        "method": method if method in METHODS else ("OTHER" if trace else None),
        # Template từ router, tuyệt đối không dùng scope[path]/raw_path/query_string.
        "route": getattr(route, "path", None) or "<unmatched>",
        "status": trace.status if trace else None,
        "duration_ms": round((perf_counter() - trace.started) * 1000, 3) if trace else None,
        "error_code": code if code is not None else (trace.error_code if trace else None),
        "stage": stage if stage is not None else (trace.stage if trace else None),
    }


def _emit(logger, level, payload):
    payload["level"] = logging.getLevelName(level)
    logger.log(level, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def log_request_error(logger, event: str, *, stage: str, code: str = "INTERNAL_ERROR") -> None:
    """Caller chỉ truyền event/code/stage hằng; không nhận exception hoặc input."""
    mark_request_error(code, stage)
    _emit(logger, logging.ERROR, _payload(logger, event, code=code, stage=stage))


def configure_request_logger():
    logger = logging.getLogger("app.request")
    # Một handler cho các app factories trong cùng process, không thay root logger.
    if not any(getattr(handler, "request_trace_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.request_trace_handler = True
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Handler riêng, không in lặp qua root/Alembic.
    return logger


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app
        self.logger = configure_request_logger()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        trace = RequestTrace(scope, str(uuid4()), perf_counter())
        token = current_trace.set(trace)
        completed = False
        failed = False

        async def traced_send(message):
            nonlocal completed
            if message["type"] == "http.response.start":
                trace.status = message["status"]
                headers = [(key, value) for key, value in message.get("headers", [])
                           if key.lower() != b"x-request-id"]
                message = {**message, "headers": [*headers, (b"x-request-id", trace.request_id.encode("ascii"))]}
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                completed = True

        try:
            await self.app(scope, receive, traced_send)
        except Exception:
            failed = True
            if trace.error_code is None:
                mark_request_error("INTERNAL_ERROR" if completed else "REQUEST_ABORTED",
                                   "unhandled" if completed else "response_stream")
            if completed:
                # Response (thường là JSON 500 của handler) đã gửi xong. Không
                # chuyển raw exception/SQL sang Uvicorn để in traceback chứa input.
                return
            # Stream đã lỗi thì phải để server đóng kết nối; bỏ exception gốc,
            # không thay bằng HTTP 200 hoặc một body 500 thứ hai sau response start.
            raise RuntimeError("ASGI response aborted; inspect the structured request log.") from None
        except BaseException:
            failed = True
            mark_request_error("REQUEST_ABORTED", "cancelled", overwrite=False)
            raise
        finally:
            try:
                if trace.status is not None and trace.status >= 400 and trace.error_code is None:
                    mark_request_error(f"HTTP_{trace.status}", "http")
                level = (logging.ERROR if failed or not completed or (trace.status or 0) >= 500 else
                         logging.WARNING if (trace.status or 0) >= 400 else logging.INFO)
                payload = _payload(self.logger, "request.completed")
                payload["outcome"] = ("aborted" if not completed else
                                      "failed" if failed or (trace.status or 0) >= 500 else "completed")
                _emit(self.logger, level, payload)
            finally:
                current_trace.reset(token)


class RequestLoggedFastAPI(FastAPI):
    def build_middleware_stack(self):
        # Đặt ngoài ServerErrorMiddleware: giữ context và header kể cả 500 không dự kiến.
        stack = super().build_middleware_stack()
        origins = self.state.settings.cors_origins
        if origins:
            stack = CORSMiddleware(stack, allow_origins=origins,
                allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Admin-Key"],
                expose_headers=[REQUEST_HEADER])
        return RequestLoggingMiddleware(stack)
