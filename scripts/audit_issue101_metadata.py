"""Read-only candidate-200 metadata reconciliation on an isolated DB and index copies.

No seed, migration, upsert, embeddings, retrieval, or benchmark is performed.
Qdrant local may maintain lock files; only the disposable audit copy is opened.
"""

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from getpass import getpass
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from uuid import NAMESPACE_URL, uuid4, uuid5


SOURCE = "data/manifests/objaverse_200.json"
SOURCE_HASH = "9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd"
CORPUS_HASH = "66efd87e34447c23b4171e13ac77d78a9c193519141d0dd6a31985c01e65b4f5"
CORPUS_MANIFEST_HASH = "d069a0f126812e39785a6395aec5e0c03195abbe596abb5a2e3aecc7a5d6f922"
RECIPE = "e5-metadata-passage-v1-draft"
FIELDS = ("source", "source_id", "name", "description", "tags", "category",
          "license", "formats", "face_count", "source_url", "author",
          "thumbnail_path", "model_path", "checksum", "ingestion_status")
INDEXES = {
    "clip": {
        "relative": "data/processed/issue89/clip-preflight-76d5d2c095b6",
        "inputs": "data/processed/issue89/inputs-1d75f15977be",
        "collection": "issue89_image_previews", "vector": "clip_bdd84b49a263010b",
        "manifest_hash": "7ebba709c46fec69dc4485cd0b358e82ca48c60ce568b3a03111ac943b882528",
        "version": "issue89-clip-preflight-76d5d2c095b6", "dimension": 512,
    },
    "e5": {
        "relative": "data/processed/issue91/e5-index-20261113-2",
        "inputs": "data/processed/issue91/e5-index-20261113-2",
        "collection": "issue91_e5_metadata", "vector": "e5_0c0cbdfd79bca607",
        "manifest_hash": "b89e50f8dbf3a5d6e57e41f5302a585fd06afb05f09eeb41fe0e09fdaf22a51d",
        "version": "issue91-e5-metadata-1588f4dc33fbe62609d8", "dimension": 384,
    },
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprint(rows):
    ordered = sorted(rows, key=lambda row: str(row.get("asset_id", "")))
    return digest(json.dumps(ordered, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), default=str).encode("utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def compare_records(expected, actual, fields=FIELDS):
    """Exact metadata comparison; missing keys and null are distinct."""
    expected_by_id = {row["asset_id"]: row for row in expected}
    require(len(expected_by_id) == len(expected), "Duplicate expected IDs")
    counts = Counter(row.get("asset_id") for row in actual
                     if isinstance(row.get("asset_id"), str) and row["asset_id"])
    actual_by_id = {row["asset_id"]: row for row in actual
                    if isinstance(row.get("asset_id"), str) and row["asset_id"]}
    missing = sorted(set(expected_by_id) - set(actual_by_id))
    outside = sorted(set(actual_by_id) - set(expected_by_id))
    duplicate = sorted(aid for aid, count in counts.items() if count > 1)
    invalid = sum(not isinstance(row.get("asset_id"), str) or not row.get("asset_id")
                  for row in actual)
    differences = []
    for aid in sorted(set(expected_by_id) & set(actual_by_id)):
        before, after = expected_by_id[aid], actual_by_id[aid]
        for field in fields:
            before_present, after_present = field in before, field in after
            if (before_present != after_present
                    or (before_present and (type(before[field]) is not type(after[field])
                                            or before[field] != after[field]))):
                differences.append({
                    "asset_id": aid, "field": field,
                    "expected_present": before_present, "actual_present": after_present,
                    "expected": before.get(field), "actual": after.get(field),
                })
    return {
        "status": "passed" if not (missing or duplicate or invalid or differences) else "failed",
        "record_count": len(actual), "unique_valid_ids": len(actual_by_id),
        "matched_candidate_ids": len(set(expected_by_id) & set(actual_by_id)),
        "missing_ids": missing, "out_of_scope_ids": outside,
        "duplicate_ids": duplicate, "invalid_id_count": invalid,
        "metadata_mismatches": differences,
    }


def checked_bytes(path, expected_hash):
    data = path.read_bytes()
    require(digest(data) == expected_hash, f"SHA-256 mismatch: {path.name}")
    return data


def load_exporter(repo):
    path = repo / "scripts/build_metadata_corpus.py"
    spec = importlib.util.spec_from_file_location("issue101_corpus_exporter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(module.RECIPE_VERSION == RECIPE, "Exporter recipe version changed")
    return module


def check_artifacts(repo, root):
    require("received" not in [part.lower() for part in root.parts],
            "Refusing to open the received/original artifact tree; use audit-copy")
    raw = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{SOURCE}"],
                         check=True, capture_output=True).stdout
    require(digest(raw) == SOURCE_HASH, "Repository source hash mismatch")
    expected = json.loads(raw.decode("utf-8-sig"))
    require(json.loads((repo / SOURCE).read_text(encoding="utf-8-sig")) == expected,
            "Repository checkout metadata differs from its committed source")
    require(len(expected) == 200 and len({row["asset_id"] for row in expected}) == 200,
            "Source must contain exactly 200 unique IDs")

    # Check the extracted files, including all SQLite files, before opening clients.
    checks = (root / "handoff/CHECKSUMS.sha256").read_text(encoding="utf-8").splitlines()
    checked_paths = set()
    for line in checks:
        checksum, relative = line.split("  ", 1)
        path = PurePosixPath(relative)
        require(not path.is_absolute() and ".." not in path.parts and "\\" not in relative
                and ":" not in relative, "Unsafe checksum path")
        require(relative not in checked_paths, "Duplicate checksum path")
        checked_paths.add(relative)
        checked_bytes(root / relative, checksum)
    require(len(checked_paths) == 223, "Expected 223 checksummed handoff entries")

    manifests = {}
    for name, pin in INDEXES.items():
        index_root, input_root = root / pin["relative"], root / pin["inputs"]
        manifest = json.loads(checked_bytes(index_root / "index-manifest.json", pin["manifest_hash"]))
        checked_bytes(input_root / manifest["source_manifest"], SOURCE_HASH)
        config = manifest["index_config"]
        require(manifest["collection"] == pin["collection"] and manifest["vector_name"] == pin["vector"],
                f"{name}: collection/named vector mismatch")
        require(config["index_version"] == pin["version"] and config["dimension"] == pin["dimension"],
                f"{name}: index version/dimension mismatch")
        require(config["dataset_snapshot"] == "home-interior-clear-200-v3-sha256:" + SOURCE_HASH,
                f"{name}: snapshot mismatch")
        require(manifest["asset_count"] == manifest["point_count"] == 200,
                f"{name}: manifest count mismatch")
        require(manifest["source_manifest_sha256"] == SOURCE_HASH, f"{name}: source pin mismatch")
        if name == "clip":
            ready = json.loads(checked_bytes(input_root / manifest["ready_manifest"],
                                             manifest["ready_manifest_sha256"]))
            ready_rows = [row["metadata"] for row in ready]
            require(compare_records(expected, ready_rows)["status"] == "passed"
                    and len(ready_rows) == 200, "CLIP ready metadata mismatch")
        manifests[name] = manifest

    e5_root = root / INDEXES["e5"]["relative"]
    corpus_manifest = json.loads(checked_bytes(e5_root / "corpus-manifest.json", CORPUS_MANIFEST_HASH))
    corpus_bytes = checked_bytes(e5_root / "corpus.jsonl", CORPUS_HASH)
    require(corpus_manifest["recipe_version"] == RECIPE, "Pinned corpus recipe mismatch")
    rows = [json.loads(line) for line in corpus_bytes.decode("utf-8").splitlines()]
    ids = [row["asset_id"] for row in rows]
    require(len(ids) == 200 and ids == sorted(row["asset_id"] for row in expected),
            "Corpus candidate IDs/order mismatch")
    exporter = load_exporter(repo)
    expected_by_id = {row["asset_id"]: row for row in expected}
    require(all(row["passage"] and row["passage"] == exporter.make_passage(expected_by_id[row["asset_id"]])
                for row in rows), "Corpus passages differ from the accepted recipe")
    require(manifests["e5"]["corpus_manifest_sha256"] == CORPUS_MANIFEST_HASH
            and manifests["e5"]["corpus_sha256"] == CORPUS_HASH
            and manifests["e5"]["recipe_version"] == RECIPE, "E5 corpus provenance mismatch")
    return expected, manifests, {"checksummed_entries": len(checked_paths),
                                "candidate_count": 200, "corpus_hash": CORPUS_HASH,
                                "recipe_version": RECIPE,
                                "historical_corpus_status": corpus_manifest.get("status")}


def audit_index(root, name, manifest, expected):
    from qdrant_client import QdrantClient
    pin = INDEXES[name]
    storage = root / pin["relative"] / "qdrant"
    sqlite_files = sorted(storage.rglob("storage.sqlite"))
    require(storage.is_dir() and sqlite_files, f"{name}: storage is absent")
    before = {str(path.relative_to(storage)): digest(path.read_bytes()) for path in sqlite_files}
    records, compatibility = [], []
    with closing(QdrantClient(path=str(storage))) as client:
        collection = client.get_collection(pin["collection"])
        vectors = collection.config.params.vectors
        require(isinstance(vectors, dict) and set(vectors) == {pin["vector"]},
                f"{name}: actual named vector mismatch")
        vector_config = vectors[pin["vector"]]
        require(vector_config.size == pin["dimension"] and vector_config.distance.value == "Cosine",
                f"{name}: actual vector dimension/distance mismatch")
        actual_count = client.count(pin["collection"], exact=True).count
        offset, visited = None, set()
        while True:
            points, next_offset = client.scroll(pin["collection"], offset=offset, limit=256,
                                                with_payload=True, with_vectors=False)
            for point in points:
                payload = point.payload or {}
                records.append(payload)
                aid = payload.get("asset_id")
                config = manifest["index_config"]
                expected_versions = {
                    "model_version": config["model_id"] + "@" + config["model_revision"],
                    "index_version": config["index_version"],
                    "_index": {**config, "distance": "Cosine"},
                }
                if name == "e5":
                    expected_versions["_corpus"] = {
                        "sha256": CORPUS_HASH, "manifest_sha256": CORPUS_MANIFEST_HASH,
                        "recipe_version": RECIPE,
                    }
                for field, wanted in expected_versions.items():
                    if field not in payload or payload[field] != wanted:
                        compatibility.append({"asset_id": aid, "field": field,
                                              "expected": wanted, "actual": payload.get(field)})
                if not isinstance(aid, str) or str(point.id) != str(uuid5(NAMESPACE_URL, f"ai04/asset/{aid}")):
                    compatibility.append({"asset_id": aid, "field": "point_id_mapping"})
            require(len(records) <= 10000, "Unexpectedly large index; stop audit")
            if next_offset is None:
                break
            require(points and str(next_offset) not in visited, "Invalid/repeated Qdrant scroll offset")
            visited.add(str(next_offset))
            offset = next_offset
    after = {str(path.relative_to(storage)): digest(path.read_bytes()) for path in sqlite_files}
    report = compare_records(expected, records)
    report.update(collection=pin["collection"], vector_name=pin["vector"],
                  index_version=pin["version"], exact_point_count=actual_count,
                  compatibility_mismatches=compatibility,
                  sqlite_bytes_unchanged=before == after,
                  sqlite_sha256_before=before, sqlite_sha256_after=after,
                  payload_fingerprint=fingerprint(records))
    if compatibility or actual_count != 200 or len(records) != 200 or before != after:
        report["status"] = "failed"
    return records, report


def read_database(preparation, user, password):
    import psycopg
    from psycopg import sql
    schema = preparation["schema"]
    require(preparation["database"] == "test_issue101", "Only test_issue101 is permitted")
    require(re.fullmatch(r"test_asset_api_[0-9a-f]{32}", schema) is not None, "Invalid isolated schema")
    require(preparation["host"] in {"127.0.0.1", "localhost", "::1"}, "Only local DB is permitted")
    with psycopg.connect(host=preparation["host"], port=preparation["port"], user=user,
                        password=password, dbname="test_issue101", connect_timeout=5) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        require(connection.execute("SHOW transaction_read_only").fetchone()[0] == "on",
                "Database transaction is not read-only")
        query = sql.SQL("SELECT * FROM {}.assets ORDER BY asset_id").format(sql.Identifier(schema))
        cursor = connection.execute(query)
        fields = [column.name for column in cursor.description]
        rows = [dict(zip(fields, values)) for values in cursor.fetchall()]
        revision = connection.execute(sql.SQL("SELECT version_num FROM {}.alembic_version")
                                      .format(sql.Identifier(schema))).fetchone()[0]
        identity = connection.execute("SELECT current_database(), current_setting('server_version')").fetchone()
    return rows, {"database": identity[0], "schema": schema, "server_version": identity[1],
                  "migration_revision": revision, "transaction_read_only": True,
                  "fixture_from_frozen_manifest": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--preparation-report", type=Path)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--storage-only", action="store_true",
                        help="Preflight only: never claims PostgreSQL reconciliation passed")
    args = parser.parse_args()
    repo, root = args.repo.resolve(), args.artifact_root.resolve()
    require(importlib.metadata.version("qdrant-client") == "1.15.1", "Use qdrant-client 1.15.1")
    output = repo / "work/issue101-audit" / uuid4().hex
    output.mkdir(parents=True, exist_ok=False)
    report_path = output / "audit.json"
    report = {"issue": 101, "status": "blocked", "audited_at_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "frozen-source / isolated-DB-fixture / received-index-copies; not business-DB sync",
              "python": sys.version.split()[0], "qdrant_client": "1.15.1",
              "auditor_sha256": digest(Path(__file__).read_bytes()),
              "business_database_sync": "not_verified", "benchmark": "not_run", "errors": []}
    exit_code = 1
    try:
        expected, manifests, input_report = check_artifacts(repo, root)
        report["inputs"] = input_report
        db_rows = None
        if not args.storage_only:
            require(args.preparation_report is not None, "Pass --preparation-report")
            preparation = json.loads(args.preparation_report.read_bytes())
            require(preparation.get("status") == "prepared" and preparation.get("schema_lifecycle") == "open",
                    "Preparation schema is not open; rerun the preparation script and keep it open")
            require(preparation["source_manifest_sha256"] == SOURCE_HASH, "Preparation source hash mismatch")
            db_rows, identity = read_database(preparation, args.user, getpass("PostgreSQL password (hidden): "))
            report["database"] = {**identity, **compare_records(expected, db_rows),
                                  "rows_sha256": fingerprint(db_rows)}
            report["database"]["source_versions"] = compare_records(
                expected, db_rows, fields=("model_version", "index_version"))
            if report["database"]["source_versions"]["status"] != "passed":
                report["database"]["status"] = "failed"
        report["indexes"] = {}
        for name, manifest in manifests.items():
            rows, index_report = audit_index(root, name, manifest, expected)
            if db_rows is not None:
                candidate_ids = {row["asset_id"] for row in expected}
                scoped_db = [row for row in db_rows if row["asset_id"] in candidate_ids]
                index_report["database_comparison"] = compare_records(scoped_db, rows)
                if index_report["database_comparison"]["status"] != "passed":
                    index_report["status"] = "failed"
            report["indexes"][name] = index_report
        good = all(row["status"] == "passed" for row in report["indexes"].values())
        if args.storage_only:
            report["status"] = "storage_preflight_passed" if good else "failed"
            report["database"] = {"status": "not_run"}
        else:
            report["status"] = "passed" if good and report["database"]["status"] == "passed" else "failed"
        exit_code = 0 if report["status"] in {"passed", "storage_preflight_passed"} else 1
    except Exception as error:
        report["status"] = "blocked"
        safe = str(error) if isinstance(error, (ValueError, FileNotFoundError, ModuleNotFoundError)) else "Inspect local environment/connectivity; no success is claimed."
        report["errors"].append({"type": type(error).__name__, "message": safe})
    finally:
        report_path.write_bytes((json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n").encode("utf-8"))
        print("AUDIT STATUS:", report["status"])
        if "database" in report:
            print("PostgreSQL:", report["database"]["status"])
        for name, item in report.get("indexes", {}).items():
            print(name.upper() + ":", item["status"], "count=" + str(item["record_count"]),
                  "metadata_mismatches=" + str(len(item["metadata_mismatches"])),
                  "compatibility_mismatches=" + str(len(item["compatibility_mismatches"])))
        for error in report["errors"]:
            print("ERROR:", error["type"], error["message"])
        print("Report:", report_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())