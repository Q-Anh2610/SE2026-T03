"""Đọc .env ở gốc repo, không phụ thuộc thư mục chạy lệnh."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        env_prefix="APP_",
        extra="ignore",
    )

    name: str = Field(default="3D Asset Semantic Search API", min_length=1)
    env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    mock_api_enabled: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: [
        "http://localhost:5173", "http://127.0.0.1:5173",
    ])
