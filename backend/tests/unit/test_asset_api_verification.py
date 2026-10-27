import pytest

from scripts.asset_api_test_support import isolated_asset_database


@pytest.mark.parametrize("value", [
    "sqlite:///test_local.db",
    "postgresql+psycopg://user:password@localhost/semantic_search",
    "postgresql+psycopg://user:password@localhost/postgres",
])
def test_verification_refuses_non_test_database_before_connecting(monkeypatch, value):
    def fail(*args, **kwargs):
        pytest.fail("Must refuse unsafe URL before creating any engine")
    monkeypatch.setattr("scripts.asset_api_test_support.create_engine", fail)
    with pytest.raises(ValueError, match="test_"):
        with isolated_asset_database(value):
            pytest.fail("Unsafe database must not be opened")
