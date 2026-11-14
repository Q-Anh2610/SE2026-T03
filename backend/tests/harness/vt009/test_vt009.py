"""Behavior oracles use fixture IDs and file contents, not implementation mocks."""

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from app.schemas.text_search import TextSearchFilters
from app.search.retrieval_config import RetrievalConfig
from app.search.configurable_search import ConfigurableSearch
from .support import AUTH_ADMIN, AUTH_VIEWER, environment


@pytest.fixture
def rig(tmp_path):
    with environment(tmp_path) as value:
        yield value


def query(http, **filters):
    return http.post("/harness/search", json={"query": "chair", "filters": filters})


def test_TC01_default_preserves_top200(rig):
    boundary, http, _ = rig
    response = query(http)
    assert response.status_code == 200
    body = response.json()
    assert [h["asset_id"] for h in body["hits"]] == [f"a{i:03}" for i in range(200)]
    assert body["versions"]["config_version"].endswith("-k200")


@pytest.mark.parametrize("limit", [1, 2, 199, 200])
def test_TC02_valid_boundaries_change_actual_results(rig, limit):
    boundary, http, _ = rig
    changed = http.put("/harness/config", json={"candidate_limit": limit}, headers=AUTH_ADMIN)
    assert changed.status_code == 200
    response = query(http)
    assert response.status_code == 200
    body = response.json()
    assert [h["asset_id"] for h in body["hits"]] == [f"a{i:03}" for i in range(limit)]
    assert body["versions"]["config_version"].endswith(f"-k{limit}")
    assert boundary.snapshot().candidate_limit == limit
    assert json.loads(boundary.config_path.read_text())["candidate_limit"] == limit


@pytest.mark.parametrize("limit", [0, 201, -1, True, 1.5, "2"])
def test_TC03_invalid_config_has_no_business_effect(rig, limit):
    boundary, http, _ = rig
    before = boundary.config_path.read_bytes()
    response = http.put("/harness/config", json={"candidate_limit": limit}, headers=AUTH_ADMIN)
    assert response.status_code == 422
    assert boundary.config_path.read_bytes() == before
    assert len(query(http).json()["hits"]) == 200


def test_TC04_viewer_cannot_change_file_or_search_outcome(rig):
    boundary, http, _ = rig
    before = boundary.config_path.read_bytes()
    response = http.put("/harness/config", json={"candidate_limit": 1}, headers=AUTH_VIEWER)
    # Business assertions are deliberately before the status assertion.
    assert boundary.config_path.read_bytes() == before
    result = query(http).json()
    assert len(result["hits"]) == 200
    assert result["versions"]["config_version"].endswith("-k200")
    assert response.status_code == 403


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer unknown"},
                                     {"Authorization": "fixture-admin"}])
def test_TC05_missing_or_forged_identity_is_rejected(rig, headers):
    boundary, http, _ = rig
    before = boundary.config_path.read_bytes()
    response = http.put("/harness/config", json={"candidate_limit": 1}, headers=headers)
    assert response.status_code == 401
    assert boundary.config_path.read_bytes() == before
    assert len(query(http).json()["hits"]) == 200


def test_TC06_filters_and_tie_order_survive_config_change(rig):
    _, http, _ = rig
    http.put("/harness/config", json={"candidate_limit": 2}, headers=AUTH_ADMIN)
    body = query(http, category="lamp").json()
    assert [h["asset_id"] for h in body["hits"]] == ["a200", "a201"]
    assert len({h["asset_id"] for h in body["hits"]}) == 2
    assert body["versions"]["config_version"].endswith("-k2")


def test_TC07_empty_filtered_result_is_successful(rig):
    _, http, _ = rig
    response = query(http, category="nonexistent")
    assert response.status_code == 200
    assert response.json()["hits"] == []


def test_TC08_write_failure_preserves_old_policy(rig, monkeypatch):
    boundary, http, _ = rig
    before = boundary.config_path.read_bytes()
    def fail_replace(*args):
        raise OSError("fixture disk failure")
    monkeypatch.setattr(os, "replace", fail_replace)
    response = http.put("/harness/config", json={"candidate_limit": 2}, headers=AUTH_ADMIN)
    assert response.status_code == 503
    assert boundary.config_path.read_bytes() == before
    assert len(query(http).json()["hits"]) == 200
    assert not list(boundary.config_path.parent.glob("*.tmp"))


def test_TC09_reconstructed_wrapper_observes_saved_policy(rig):
    boundary, http, _ = rig
    http.put("/harness/config", json={"candidate_limit": 2}, headers=AUTH_ADMIN)
    rebuilt = ConfigurableSearch(boundary.service, boundary.config_path)
    assert len(rebuilt.search("chair", TextSearchFilters()).hits) == 2
    assert rebuilt.snapshot().candidate_limit == 2


@pytest.mark.parametrize("content", ['{"candidate_limit": 0}', '{broken json',
    RetrievalConfig().model_copy(update={"config_version": "wrong"}).model_dump_json()])
def test_TC10_corrupt_policy_fails_closed(rig, content):
    boundary, http, _ = rig
    boundary.config_path.write_text(content, encoding="utf-8")
    assert query(http).status_code == 503


def test_TC11_incompatible_encoder_is_not_reported_as_success(rig):
    boundary, http, _ = rig
    boundary.service.service.encoder.revision = "different"
    response = query(http)
    assert response.status_code == 503
    assert "hits" not in response.json()


@pytest.mark.parametrize("role", ["viewer", "", "ADMIN"])
def test_TC12_service_boundary_also_enforces_authorization(rig, role):
    boundary, _, _ = rig
    before = boundary.config_path.read_bytes()
    with pytest.raises(PermissionError):
        boundary.change_limit(role, 1)
    assert boundary.config_path.read_bytes() == before


@pytest.mark.parametrize("value", [0, 201, True, "2"])
def test_TC13_service_boundary_also_validates_limits(rig, value):
    boundary, _, _ = rig
    with pytest.raises(ValidationError):
        boundary.change_limit("admin", value)
    assert boundary.snapshot().candidate_limit == 200


def test_TC14_concurrent_read_and_update_use_complete_snapshots(rig):
    boundary, _, _ = rig
    def operation(index):
        if index % 3 == 0:
            boundary.change_limit("admin", 1 if index % 2 else 2)
            return
        result = boundary.search("chair", TextSearchFilters())
        k = int(result.versions.config_version.rsplit("-k", 1)[1])
        assert len(result.hits) == k
        assert [h.asset_id for h in result.hits] == [f"a{i:03}" for i in range(k)]
    with ThreadPoolExecutor(max_workers=20) as executor:
        list(executor.map(operation, range(60)))


def test_TC15_unknown_field_cannot_supply_a_role(rig):
    boundary, http, _ = rig
    before = boundary.config_path.read_bytes()
    response = http.put("/harness/config", json={"candidate_limit": 2, "role": "admin"},
                        headers=AUTH_VIEWER)
    assert response.status_code == 422
    assert boundary.config_path.read_bytes() == before
