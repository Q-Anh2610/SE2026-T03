"""Tạo engine khi cần; import module không tự kết nối hoặc tạo bảng."""

from sqlalchemy import URL, Engine, create_engine, make_url

from app.core.config import Settings


def database_url(settings: Settings) -> URL:
    if settings.database_url is not None:
        url = make_url(settings.database_url.get_secret_value())
        if url.drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use postgresql+psycopg.")
        return url
    if settings.postgres_password is None:
        raise ValueError("Configure POSTGRES_PASSWORD or DATABASE_URL before using the database.")
    return URL.create(
        "postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )


def create_db_engine(settings: Settings | None = None) -> Engine:
    return create_engine(
        database_url(settings if settings is not None else Settings()),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )
