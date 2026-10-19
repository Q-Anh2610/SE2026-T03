"""Liveness probe; không khởi tạo DB, index hay encoder."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
