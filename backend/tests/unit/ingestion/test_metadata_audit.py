"""Fixture tests; no live PostgreSQL, storage, model, or network access."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest


ROOT = Path(__file__).resolve().parents[4]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load_script("audit_issue101_metadata")
prepare = load_script("prepare_issue101_db")


@pytest.fixture
def sample():
    return [{"asset_id": "asset_a", "category": None, "tags": ["wood", "chair"],
             "name": " Chair ", "face_count": 1}]


def test_exact_match_and_inputs_unchanged(sample):
    before = copy.deepcopy(sample)
    assert audit.compare_records(sample, copy.deepcopy(sample))["status"] == "passed"
    assert sample == before


@pytest.mark.parametrize("field,value", [
    ("category", "furniture"), ("tags", ["chair", "wood"]),
    ("name", "Chair"), ("face_count", True),
])
def test_field_differences_are_not_normalized_away(sample, field, value):
    actual = copy.deepcopy(sample)
    actual[0][field] = value
    result = audit.compare_records(sample, actual)
    assert result["status"] == "failed"
    assert result["metadata_mismatches"][0]["field"] == field


def test_missing_field_is_distinct_from_null(sample):
    actual = copy.deepcopy(sample)
    del actual[0]["category"]
    difference = audit.compare_records(sample, actual)["metadata_mismatches"][0]
    assert difference["expected_present"] is True
    assert difference["actual_present"] is False


def test_missing_candidate_is_failure(sample):
    result = audit.compare_records(sample, [])
    assert result["status"] == "failed"
    assert result["missing_ids"] == ["asset_a"]


def test_outside_ids_are_reported_without_being_called_missing(sample):
    result = audit.compare_records(sample, sample + [{"asset_id": "outside"}])
    assert result["status"] == "passed"
    assert result["out_of_scope_ids"] == ["outside"]
    assert result["missing_ids"] == []


def test_duplicate_actual_id_fails(sample):
    result = audit.compare_records(sample, sample * 2)
    assert result["status"] == "failed"
    assert result["duplicate_ids"] == ["asset_a"]


@pytest.mark.parametrize("aid", [None, "", 123])
def test_invalid_actual_ids_fail(sample, aid):
    result = audit.compare_records(sample, sample + [{"asset_id": aid}])
    assert result["status"] == "failed"
    assert result["invalid_id_count"] == 1


def test_duplicate_reference_is_rejected(sample):
    with pytest.raises(ValueError, match="Duplicate expected"):
        audit.compare_records(sample * 2, sample)


def test_fingerprint_ignores_record_order():
    rows = [{"asset_id": "a", "name": "A"}, {"asset_id": "b", "name": "B"}]
    assert audit.fingerprint(rows) == audit.fingerprint(list(reversed(rows)))


def test_wrong_file_hash_is_rejected(tmp_path):
    path = tmp_path / "source.json"
    path.write_bytes(b"original")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        audit.checked_bytes(path, "0" * 64)


@pytest.fixture
def source_fixture(tmp_path, monkeypatch):
    records = [{"asset_id": f"asset_{i:03d}"} for i in range(200)]

    def setup(rows=None, checkout=None):
        rows = records if rows is None else rows
        raw = json.dumps(rows).encode("utf-8")
        path = tmp_path / prepare.SOURCE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows if checkout is None else checkout), encoding="utf-8")
        monkeypatch.setattr(prepare, "git", lambda *args: raw)
        monkeypatch.setattr(prepare, "SOURCE_HASH", hashlib.sha256(raw).hexdigest())
        return tmp_path

    return records, setup


def test_preparation_accepts_frozen_200_ids(source_fixture):
    records, setup = source_fixture
    _, actual = prepare.read_source(setup())
    assert actual == records


def test_preparation_rejects_changed_checkout(source_fixture):
    records, setup = source_fixture
    changed = copy.deepcopy(records)
    changed[0]["name"] = "changed"
    with pytest.raises(ValueError, match="differs"):
        prepare.read_source(setup(checkout=changed))


def test_preparation_rejects_wrong_hash(source_fixture, monkeypatch):
    _, setup = source_fixture
    root = setup()
    monkeypatch.setattr(prepare, "SOURCE_HASH", "0" * 64)
    with pytest.raises(ValueError, match="hash"):
        prepare.read_source(root)


def test_preparation_rejects_wrong_count(source_fixture):
    records, setup = source_fixture
    with pytest.raises(ValueError, match="200 source"):
        prepare.read_source(setup(rows=records[:-1]))


def test_preparation_rejects_duplicate_ids(source_fixture):
    records, setup = source_fixture
    changed = copy.deepcopy(records)
    changed[1]["asset_id"] = changed[0]["asset_id"]
    with pytest.raises(ValueError, match="Duplicate"):
        prepare.read_source(setup(rows=changed))


@pytest.fixture
def db_fixture(monkeypatch):
    import psycopg
    calls = []
    state = {"readonly": "on", "connections": 0}

    class Cursor:
        description = [SimpleNamespace(name="asset_id"), SimpleNamespace(name="name")]

        def __init__(self, one=None, rows=None):
            self.one, self.rows = one, rows

        def fetchone(self):
            return self.one

        def fetchall(self):
            return self.rows

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query):
            query = query if isinstance(query, str) else query.as_string()
            calls.append(query)
            if query.startswith("SET TRANSACTION"):
                return Cursor()
            if query == "SHOW transaction_read_only":
                return Cursor((state["readonly"],))
            if query.startswith("SELECT *"):
                return Cursor(rows=[("asset_a", "Chair")])
            if "version_num" in query:
                return Cursor(("0002",))
            if "current_database" in query:
                return Cursor(("test_issue101", "fixture-server"))
            raise AssertionError("Unexpected SQL: " + query)

    def connect(**kwargs):
        state["connections"] += 1
        assert kwargs["dbname"] == "test_issue101"
        return Connection()

    monkeypatch.setattr(psycopg, "connect", connect)
    preparation = {"database": "test_issue101", "schema": "test_asset_api_" + "0" * 32,
                   "host": "127.0.0.1", "port": 5432}
    return preparation, calls, state


def test_database_sets_readonly_before_select_and_only_reads(db_fixture):
    preparation, calls, _ = db_fixture
    rows, identity = audit.read_database(preparation, "fixture-user", "fixture-password")
    assert calls[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert all(query.startswith(("SET TRANSACTION", "SHOW ", "SELECT ")) for query in calls)
    assert identity["transaction_read_only"] is True
    assert rows == [{"asset_id": "asset_a", "name": "Chair"}]


def test_database_stops_if_readonly_is_not_enabled(db_fixture):
    preparation, calls, state = db_fixture
    state["readonly"] = "off"
    with pytest.raises(ValueError, match="not read-only"):
        audit.read_database(preparation, "fixture-user", "fixture-password")
    assert not any(query.startswith("SELECT") for query in calls)


@pytest.mark.parametrize("field,value", [
    ("database", "semantic_search"), ("schema", "public"),
    ("schema", "test_asset_api_bad; DROP TABLE assets"), ("host", "remote.example"),
])
def test_database_refuses_unapproved_targets_before_connect(db_fixture, field, value):
    preparation, _, state = db_fixture
    preparation[field] = value
    with pytest.raises(ValueError):
        audit.read_database(preparation, "fixture-user", "fixture-password")
    assert state["connections"] == 0


@pytest.fixture
def index_fixture(tmp_path, monkeypatch):
    import qdrant_client
    state = {"closed": 0, "mutate_storage": False}

    def setup(name):
        pin = audit.INDEXES[name]
        storage = tmp_path / pin["relative"] / "qdrant"
        storage.mkdir(parents=True, exist_ok=True)
        file = storage / "storage.sqlite"
        file.write_bytes(b"fixture bytes; no real SQLite or Qdrant")
        config = {"model_id": name, "model_revision": "fixture-revision", "dimension": pin["dimension"],
                  "index_version": pin["version"], "dataset_snapshot": "fixture-snapshot",
                  "preprocessing_version": "fixture-preprocessing"}
        expected = [{"asset_id": f"asset_{i:03d}", "category": None} for i in range(200)]
        points = []
        for record in expected:
            payload = {**record, "model_version": name + "@fixture-revision", "index_version": pin["version"],
                       "_index": {**config, "distance": "Cosine"}}
            if name == "e5":
                payload["_corpus"] = {"sha256": audit.CORPUS_HASH,
                                       "manifest_sha256": audit.CORPUS_MANIFEST_HASH,
                                       "recipe_version": audit.RECIPE}
            points.append(SimpleNamespace(id=str(uuid5(NAMESPACE_URL, f"ai04/asset/{record['asset_id']}")),
                                          payload=payload))
        state.update(points=points, vector=pin["vector"], dimension=pin["dimension"], count=200)

        class Client:
            def __init__(self, **kwargs):
                assert kwargs["path"] == str(storage)

            def close(self):
                state["closed"] += 1
                if state["mutate_storage"]:
                    file.write_bytes(b"changed")

            def get_collection(self, collection):
                assert collection == pin["collection"]
                vectors = {state["vector"]: SimpleNamespace(size=state["dimension"],
                           distance=SimpleNamespace(value="Cosine"))}
                return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(vectors=vectors)))

            def count(self, collection, exact):
                assert exact is True
                return SimpleNamespace(count=state["count"])

            def scroll(self, collection, **kwargs):
                assert kwargs["with_payload"] is True and kwargs["with_vectors"] is False
                return state["points"], None

        monkeypatch.setattr(qdrant_client, "QdrantClient", Client)
        return tmp_path, name, {"index_config": config}, expected

    return setup, state


@pytest.mark.parametrize("name", ["clip", "e5"])
def test_each_index_accepts_its_own_versions_and_closes(index_fixture, name):
    setup, state = index_fixture
    _, report = audit.audit_index(*setup(name))
    assert report["status"] == "passed"
    assert report["sqlite_bytes_unchanged"] is True
    assert state["closed"] == 1


@pytest.mark.parametrize("field", ["model_version", "index_version", "_index", "_corpus"])
def test_wrong_payload_provenance_is_reported(index_fixture, field):
    setup, state = index_fixture
    args = setup("e5")
    state["points"][0].payload[field] = "wrong"
    _, report = audit.audit_index(*args)
    assert report["status"] == "failed"
    assert report["compatibility_mismatches"][0]["field"] == field


@pytest.mark.parametrize("field,value", [("vector", "wrong"), ("dimension", 42)])
def test_actual_vector_configuration_is_checked(index_fixture, field, value):
    setup, state = index_fixture
    args = setup("clip")
    state[field] = value
    with pytest.raises(ValueError):
        audit.audit_index(*args)
    assert state["closed"] == 1


def test_bad_point_id_mapping_is_reported(index_fixture):
    setup, state = index_fixture
    args = setup("clip")
    state["points"][0].id = "wrong-id"
    _, report = audit.audit_index(*args)
    assert report["status"] == "failed"
    assert report["compatibility_mismatches"][0]["field"] == "point_id_mapping"


def test_missing_index_candidate_is_reported(index_fixture):
    setup, state = index_fixture
    args = setup("clip")
    state["points"].pop()
    state["count"] = 199
    _, report = audit.audit_index(*args)
    assert report["status"] == "failed"
    assert len(report["missing_ids"]) == 1


def test_sqlite_mutation_during_audit_is_detected(index_fixture):
    setup, state = index_fixture
    args = setup("clip")
    state["mutate_storage"] = True
    _, report = audit.audit_index(*args)
    assert report["status"] == "failed"
    assert report["sqlite_bytes_unchanged"] is False
