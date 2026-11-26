"""Audits W7: compare compatible indexes, open only copies of reference storage."""

from dataclasses import asdict
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import shutil


class RebuildCheckError(ValueError):
    """Fixed diagnostic code, without paths, queries or exception details."""

    def __init__(self, code, *, details=None):
        super().__init__(code)
        self.details = details


def require(condition, code):
    if not condition:
        raise RebuildCheckError(code)


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                      allow_nan=False) + "\n").encode("utf-8")
    with Path(path).open("xb") as stream:
        stream.write(raw)


def storage_hashes(root):
    """Reject hot SQLite copies and external files; never open reference Qdrant."""
    root = Path(root).resolve()
    require(root.is_dir(), "missing_storage")
    entries = list(root.rglob("*"))
    require(not any(p.is_symlink() or not p.resolve().is_relative_to(root)
                    for p in entries), "external_storage_member")
    files = sorted(p for p in entries if p.is_file() and p.name != ".lock")
    require((root / "meta.json").is_file()
            and any(p.name == "storage.sqlite" for p in files), "incomplete_storage")
    require(not any(p.name.endswith(("-wal", "-shm", "-journal")) for p in files),
            "storage_writer_or_sqlite_sidecar")
    return {p.relative_to(root).as_posix(): file_hash(p) for p in files}


def copy_reference(root, output, expected):
    root, output = Path(root).resolve(), Path(output).resolve()
    require(not output.exists() and not output.is_relative_to(root), "unsafe_reference_copy")
    require(storage_hashes(root / "qdrant") == expected, "reference_changed_before_copy")
    output.mkdir(parents=True, exist_ok=False)
    # Copy only the small manifest/input files required by existing auditors.
    for name in ("index-manifest.json", "source.json", "corpus.jsonl", "corpus-manifest.json"):
        member = root / name
        if member.exists():
            require(member.is_file() and not member.is_symlink(), "external_reference_member")
            shutil.copyfile(member, output / name)
    shutil.copytree(root / "qdrant", output / "qdrant", ignore=shutil.ignore_patterns(".lock"))
    require(storage_hashes(output / "qdrant") == expected, "reference_copy_hash_mismatch")
    require(storage_hashes(root / "qdrant") == expected, "reference_changed_during_copy")


def points_by_asset(store):
    """Read vectors after reopen and before any cosine query mutates local RAM."""
    records, offset, cursors = {}, None, set()
    while True:
        page, offset = store.client.scroll(store.collection_name, limit=256, offset=offset,
                                           with_payload=True, with_vectors=True)
        for point in page:
            payload = point.payload or {}
            aid = payload.get("asset_id")
            require(isinstance(aid, str) and aid not in records, "duplicate_or_missing_asset_id")
            require(isinstance(point.vector, dict) and set(point.vector) == {store.vector_name},
                    "unexpected_named_vector")
            records[aid] = {"point_id": str(point.id), "payload": payload,
                            "vector": point.vector[store.vector_name]}
        require(len(records) <= 200, "unexpected_candidate_count")
        if offset is None:
            break
        require(page and str(offset) not in cursors, "invalid_scroll_cursor")
        cursors.add(str(offset))
    return records


def _payload_without_index_version(payload):
    require(isinstance(payload.get("_index"), dict), "missing_payload_index_config")
    result = dict(payload)
    result.pop("index_version", None)
    result["_index"] = {k: v for k, v in payload["_index"].items() if k != "index_version"}
    return result


def compare_indexes(reference_store, rebuilt_store, *, vector_abs_tolerance, expected_ids):
    """Only index_version/named-vector identity may differ, never model or metadata.

    Call existing model-specific auditors first. This comparison adds a fixed
    per-component vector bound; it does not round vectors or compare their hashes.
    """
    require(type(vector_abs_tolerance) in (int, float)
            and isfinite(vector_abs_tolerance) and 0 <= vector_abs_tolerance <= 1e-6,
            "invalid_vector_tolerance")
    a, b = asdict(reference_store.config), asdict(rebuilt_store.config)
    a.pop("index_version")
    b.pop("index_version")
    require(a == b and reference_store.collection_name == rebuilt_store.collection_name,
            "reference_rebuild_config_mismatch")
    old, new = points_by_asset(reference_store), points_by_asset(rebuilt_store)
    require(len(expected_ids) == len(set(expected_ids)) == 200
            and set(old) == set(new) == set(expected_ids), "reference_rebuild_ids_mismatch")
    maximum, differing, count = 0.0, 0, 0
    for aid in sorted(old):
        left, right = old[aid], new[aid]
        require(left["point_id"] == right["point_id"], "reference_rebuild_point_id_mismatch")
        require(_payload_without_index_version(left["payload"])
                == _payload_without_index_version(right["payload"]), "reference_rebuild_payload_mismatch")
        x, y = left["vector"], right["vector"]
        require(isinstance(x, list) and isinstance(y, list)
                and len(x) == len(y) == reference_store.config.dimension, "reference_rebuild_dimension_mismatch")
        require(all(type(v) in (int, float) and isfinite(v) for v in x + y),
                "reference_rebuild_nonfinite_vector")
        delta = max((abs(v - w) for v, w in zip(x, y, strict=True)), default=0.0)
        maximum = max(maximum, delta)
        differing += x != y
        count += 1
    result = {"passed": maximum <= vector_abs_tolerance, "asset_count": count, "different_vector_count": differing,
            "max_component_abs_delta": maximum, "vector_abs_tolerance": vector_abs_tolerance,
            "payload_policy": "exact_except_index_version", "point_ids_equal": True,
            "ranking_comparison_performed": False}
    if not result["passed"]:
        raise RebuildCheckError("reference_rebuild_vector_tolerance_exceeded", details=result)
    return result
