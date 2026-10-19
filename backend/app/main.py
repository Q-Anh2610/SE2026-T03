"""ASGI entrypoint cho Uvicorn."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()
    application = FastAPI(title=settings.name, debug=settings.debug)
    application.include_router(health_router)
    return application


app = create_app()
