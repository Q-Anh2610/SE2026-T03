"""Chuẩn hóa lỗi JSON; không trả input, stack trace hay exception message nội bộ."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.api import ErrorResponse


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def install_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        body = ErrorResponse.model_validate({"error": {
            "code": "INVALID_REQUEST",
            "message": "Yêu cầu không hợp lệ.",
            "details": [
                {"field": ".".join(str(part) for part in item["loc"]), "message": "Giá trị không hợp lệ."}
                for item in exc.errors()
            ],
        }})
        return JSONResponse(status_code=400, content=body.model_dump(mode="json"))

    @application.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {
            "code": f"HTTP_{exc.status_code}",
            "message": "Không tìm thấy tài nguyên." if exc.status_code == 404 else "Không thể thực hiện yêu cầu.",
        }
        body = ErrorResponse(error=detail)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"), headers=exc.headers)

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        body = ErrorResponse(error={"code": "INTERNAL_ERROR", "message": "Lỗi máy chủ. Vui lòng thử lại sau."})
        return JSONResponse(status_code=500, content=body.model_dump(mode="json"))
