"""ASGI entrypoint cho Uvicorn."""

from copy import deepcopy

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from app.api.health import router as health_router
from app.core.config import Settings
from app.core.errors import install_error_handlers
from app.api.mock import router as mock_router
from app.services.mock_api import MockStore


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()
    application = FastAPI(
        title=settings.name, debug=settings.debug,
        description="Contract mock v1 cho phát triển frontend. Không chạy semantic search hoặc lưu feedback vào database.",
    )
    install_error_handlers(application)
    application.include_router(health_router)
    if settings.mock_api_enabled and settings.env != "production":
        application.state.mock_store = MockStore()
        application.include_router(mock_router)
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware, allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
        )

    def openapi_contract():
        if application.openapi_schema is None:
            schema = get_openapi(
                title=application.title, version=application.version,
                description=application.description, routes=application.routes,
            )
            for path, operations in schema["paths"].items():
                if path.startswith("/api/v1/"):
                    for operation in operations.values():
                        operation.get("responses", {}).pop("422", None)
            for name in ("HTTPValidationError", "ValidationError"):
                schema.get("components", {}).get("schemas", {}).pop(name, None)
            # FastAPI excludes None while encoding OpenAPI metadata. Preserve
            # explicit nulls in examples: frontend requires nullable keys present.
            for route in mock_router.routes:
                if not isinstance(route, APIRoute):
                    continue
                for method in route.methods:
                    operation = schema["paths"].get(route.path, {}).get(method.lower())
                    if operation is None:
                        continue
                    for status, metadata in route.responses.items():
                        example = metadata.get("content", {}).get("application/json", {}).get("example")
                        if example is not None:
                            operation["responses"][str(status)]["content"]["application/json"]["example"] = deepcopy(example)
            application.openapi_schema = schema
        return application.openapi_schema

    application.openapi = openapi_contract
    return application


app = create_app()
