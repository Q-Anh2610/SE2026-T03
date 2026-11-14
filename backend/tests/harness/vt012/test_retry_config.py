"""Biên cấu hình retry và backoff; không cần dịch vụ thật."""

import pytest

from .support import embedding, make_store


@pytest.mark.parametrize("attempts", [0, -1, 4, True, 1.5, "3"])
def test_t20_invalid_attempt_budget_is_rejected(attempts):
    with pytest.raises(ValueError, match="max_attempts"):
        make_store(max_attempts=attempts)


@pytest.mark.parametrize("delay", [-0.1, 0.6, float("nan"), float("inf"), True, "0.1"])
def test_t21_invalid_backoff_is_rejected(delay):
    with pytest.raises(ValueError, match="retry_delay"):
        make_store(retry_delay=delay)


def test_t22_single_attempt_budget_never_sleeps(monkeypatch):
    waits = []
    monkeypatch.setattr("time.sleep", waits.append)
    store, client = make_store(["before", None], max_attempts=1, retry_delay=0)
    try:
        with pytest.raises(Exception) as caught:
            store.upsert([embedding()])
        assert type(caught.value).__name__ == "ResponseHandlingException"
        assert len(client.calls) == 1
        assert waits == []
    finally:
        client.close()


def test_t23_backoff_is_bounded_and_only_between_attempts(monkeypatch):
    waits = []
    monkeypatch.setattr("time.sleep", waits.append)
    store, client = make_store(["before", "before", None], retry_delay=0.5)
    try:
        assert store.upsert([embedding()]) == 1
        assert waits == [0.5, 1.0]
    finally:
        client.close()
