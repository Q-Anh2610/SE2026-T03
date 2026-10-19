import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.fixture(autouse=True)
def clear_app_environment(monkeypatch):
    for key in ("APP_NAME", "APP_ENV", "APP_DEBUG"):
        monkeypatch.delenv(key, raising=False)


def test_defaults_without_env_file():
    settings = Settings(_env_file=None)

    assert settings.name == "3D Asset Semantic Search API"
    assert settings.env == "development"
    assert settings.debug is False


def test_reads_utf8_dotenv_and_ignores_other_service_settings(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_NAME=Tìm kiếm 3D\nAPP_ENV=test\nAPP_DEBUG=true\nBACKEND_PORT=9000\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.name == "Tìm kiếm 3D"
    assert settings.env == "test"
    assert settings.debug is True


def test_environment_overrides_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("APP_NAME=From file\n", encoding="utf-8")
    monkeypatch.setenv("APP_NAME", "From environment")

    assert Settings(_env_file=env_file).name == "From environment"


def test_default_dotenv_path_is_independent_of_working_directory(tmp_path, monkeypatch):
    env_path = Settings.model_config["env_file"]
    monkeypatch.chdir(tmp_path)

    assert env_path.is_absolute()
    assert env_path.name == ".env"
    assert (env_path.parent / "backend" / "app" / "main.py").is_file()


@pytest.mark.parametrize("values", [{"env": "invalid"}, {"debug": "invalid"}, {"name": ""}])
def test_rejects_invalid_settings(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)
