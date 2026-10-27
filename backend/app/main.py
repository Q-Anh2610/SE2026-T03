"""ASGI entrypoint cho Uvicorn."""

from copy import deepcopy
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from app.api.health import router as health_router
from app.core.config import Settings
from app.core.errors import install_error_handlers
from app.api.mock import router as mock_router
from app.api.mock import list_router as mock_list_router
from app.api.assets import router as assets_router
from app.services.mock_api import MockStore


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    @asynccontextmanager
    async def lifespan(application):
        try:
            yield
        finally:
            if application.state.db_engine is not None:
                application.state.db_engine.dispose()

    application = FastAPI(
        title=settings.name, debug=settings.debug,
        description="Danh sách asset đọc PostgreSQL. Detail/search/feedback hiện là mock phục vụ phát triển; chưa semantic search.",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.db_engine = None
    application.state.db_engine_lock = Lock()
    install_error_handlers(application)
    application.include_router(health_router)
    mocks_enabled = settings.mock_api_enabled and settings.env != "production"
    list_router = mock_list_router if mocks_enabled and settings.asset_list_source == "fixture" else assets_router
    application.include_router(list_router)
    if mocks_enabled:
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
            for route in [*list_router.routes, *(mock_router.routes if mocks_enabled else [])]:
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
