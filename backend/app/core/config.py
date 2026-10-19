"""Đọc .env ở gốc repo, không phụ thuộc thư mục chạy lệnh."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
    database_url: SecretStr | None = Field(default=None, validation_alias="DATABASE_URL")
    postgres_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, ge=1, le=65535, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(default="semantic_search", min_length=1, validation_alias="POSTGRES_DB")
    postgres_user: str = Field(default="semantic", min_length=1, validation_alias="POSTGRES_USER")
    postgres_password: SecretStr | None = Field(default=None, validation_alias="POSTGRES_PASSWORD")
    mock_api_enabled: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: [
        "http://localhost:5173", "http://127.0.0.1:5173",
    ])
