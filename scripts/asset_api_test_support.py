"""Tài nguyên kiểm chứng dùng schema tạm trong PostgreSQL test_* riêng."""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import URL, Engine, create_engine, make_url
from sqlalchemy.schema import CreateSchema, DropSchema

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class AssetTestDatabase:
    engine: Engine
    url: URL
    schema: str

    def migrate(self):
        with self.engine.begin() as connection:
            config = Config(str(ROOT / "backend" / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            command.check(config)


@contextmanager
def isolated_asset_database(value: str):
    url = make_url(value)
    if url.drivername != "postgresql+psycopg" or not (url.database or "").startswith("test_"):
        raise ValueError("TEST_DATABASE_URL phải là postgresql+psycopg và database test_* riêng.")
    # Định danh do chương trình sinh; không nhận tên schema để xóa từ bên ngoài.
    schema = "test_asset_api_" + uuid4().hex
    admin = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    scoped_url = url.update_query_dict({"options": "-csearch_path=" + schema})
    engine = create_engine(scoped_url, hide_parameters=True, connect_args={"connect_timeout": 5})
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
            created = True
        yield AssetTestDatabase(engine, scoped_url, schema)
    finally:
        engine.dispose()
        try:
            if created:
                with admin.begin() as connection:
                    connection.execute(DropSchema(schema, cascade=True))
        finally:
            admin.dispose()
