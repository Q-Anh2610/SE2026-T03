"""Harness #149 phải từ chối target dùng chung trước khi ghi dữ liệu/nạp model."""

from pathlib import Path

import pytest

from scripts.prepare_w7_e2e import prepare


@pytest.mark.parametrize("database_url", [
    "postgresql+psycopg://user:fake@127.0.0.1/semantic_search",
    "postgresql+psycopg://user:fake@127.0.0.1/test_other_issue",
    "postgresql+psycopg://user:fake@db.example/test_issue149_demo",
    "sqlite:///test_issue149_demo.db",
])
def test_refuses_non_dedicated_database_before_reading_inputs(monkeypatch, database_url):
    monkeypatch.setenv("TEST_DATABASE_URL", database_url)
    with pytest.raises(ValueError, match="test_issue149"):
        prepare(Path("missing-handoff"), "http://127.0.0.1:6439")


@pytest.mark.parametrize("qdrant_url", [
    "http://qdrant.example:6333",
    "http://user:fake@127.0.0.1:6333",
    "http://127.0.0.1:6333/collections",
    "http://127.0.0.1:6333?api_key=fake",
    "http://127.0.0.1:6333#fragment",
])
def test_refuses_non_local_or_credentialed_qdrant_before_reading_inputs(monkeypatch, qdrant_url):
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+psycopg://user:fake@127.0.0.1/test_issue149_demo")
    with pytest.raises(ValueError, match="Qdrant HTTP origin local"):
        prepare(Path("missing-handoff"), qdrant_url)
