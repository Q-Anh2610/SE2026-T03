"""Migrations chạy trong transaction rollback trên DB test riêng, không dùng DATABASE_URL."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, make_url


@pytest.fixture
def migrated_database():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL database named test_*.")
    url = make_url(value)
    if url.drivername != "postgresql+psycopg" or not (url.database or "").startswith("test_"):
        pytest.fail("Integration tests require postgresql+psycopg and a database name starting with test_.")

    engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        transaction = connection.begin()
        configuration = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        configuration.attributes["connection"] = connection
        try:
            command.upgrade(configuration, "head")
            yield connection, configuration
        finally:
            transaction.rollback()
    engine.dispose()
