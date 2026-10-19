"""Alembic dùng cùng settings/metadata với backend, không lưu credentials trong INI."""

from logging.config import fileConfig

from alembic import context

from app.core.config import Settings
from app.db.base import Base
from app.db.session import create_db_engine, database_url
from app.models import Asset, Feedback, SearchEvent  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(Settings()),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def migrate(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied = config.attributes.get("connection")
    if supplied is not None:
        migrate(supplied)
        return
    engine = create_db_engine()
    try:
        with engine.connect() as connection:
            migrate(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
