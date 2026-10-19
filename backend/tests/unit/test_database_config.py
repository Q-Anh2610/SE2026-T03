import pytest

from app.core.config import Settings
from app.db.session import database_url


@pytest.fixture(autouse=True)
def clear_database_environment(monkeypatch):
    for key in ("DATABASE_URL", "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.delenv(key, raising=False)


def test_password_with_reserved_characters_is_not_corrupted():
    settings = Settings(_env_file=None, POSTGRES_PASSWORD="p@ss%:/#", POSTGRES_USER="demo")
    url = database_url(settings)
    assert url.username == "demo"
    assert url.password == "p@ss%:/#"
    assert "p@ss" not in repr(settings)


def test_explicit_url_has_priority():
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+psycopg://custom:secret@db:5433/custom_db",
        POSTGRES_HOST="ignored",
    )
    url = database_url(settings)
    assert (url.host, url.port, url.database) == ("db", 5433, "custom_db")
    assert "secret" not in repr(settings)


def test_database_commands_require_credentials():
    with pytest.raises(ValueError, match="Configure POSTGRES_PASSWORD"):
        database_url(Settings(_env_file=None))


def test_rejects_non_postgresql_url():
    with pytest.raises(ValueError, match="postgresql"):
        database_url(Settings(_env_file=None, DATABASE_URL="sqlite:///test.db"))
