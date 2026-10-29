"""Verify real Objaverse-200 CLIP indexing, then repeat the full batch.

Run from the repository root with backend/.venv/Scripts/python.exe.
Uses the project's existing encoder, batch runner and Qdrant store.
Writes JSON evidence without vectors; does not modify PostgreSQL or the handoff.
"""

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import time
from uuid import NAMESPACE_URL, uuid5


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative_file(root, name):
    require(isinstance(name, str) and name and ":" not in name
            and "\\" not in name, "Expected a portable relative file path")
    path = (root / name).resolve()
    require(path.is_relative_to(root) and path.is_file(),
            f"Missing file or path outside handoff: {name}")
    return path


def load_handoff(root, repo):
    base = "data/manifests/objaverse_200"
    manifest_path = root / (base + ".json")
    manifest = read_json(manifest_path)
    provenance = read_json(root / (base + ".provenance.json"))
    handoff = read_json(root / "HANDOFF.json")
    ready_path = root / "data/processed/ingestion/objaverse_200.ready.json"
    ready = read_json(ready_path)
    manifest_hash = digest(manifest_path)
    require(manifest_hash == provenance["manifest_sha256"]
            == handoff["manifest_sha256"]
            == digest(repo / (base + ".json")),
            "Handoff and repository W1 manifest hashes must match")
    require(digest(root / (base + ".annotations.json"))
            == provenance["annotations_sha256"], "Annotation hash mismatch")
    require(isinstance(manifest, list) and isinstance(ready, list)
            and len(manifest) == len(ready) == 200, "Expected 200 input assets")
    ids = [item["asset_id"] for item in manifest]
    require(len(set(ids)) == 200, "Duplicate manifest asset IDs")
    require(len({(item["source"], item["source_id"]) for item in manifest})
            == 200, "Duplicate source identities")
    expected = {item["asset_id"]: item for item in manifest}
    preview_rows = provenance["previews"]
    previews = {item["asset_id"]: item for item in preview_rows}
    require(len(preview_rows) == len(previews) == 200
            and set(previews) == set(expected), "Provenance IDs differ")
    report_path = relative_file(root, handoff["report_path"])
    require(digest(report_path) == handoff["report_sha256"],
            "Ingestion report hash mismatch")
    ingestion = read_json(report_path)
    require(ingestion["manifest_sha256"] == manifest_hash,
            "Ingestion report uses a different manifest")
    results = ingestion["results"]
    by_id = {item["asset_id"]: item for item in results}
    require(len(results) == len(by_id) == 200 and set(by_id) == set(expected),
            "Ingestion report IDs differ")
    counts = Counter(item["status"] for item in results)
    require(set(counts) <= {"downloaded", "skipped"},
            "Ingestion has failed or unknown states")
    require(ingestion["summary"] == {
        "input_count": 200, "succeeded": counts["downloaded"],
        "failed": 0, "skipped": counts["skipped"]},
        "Ingestion summary is inconsistent")
    preview_root = (root / "data/raw/objaverse/previews").resolve()
    seen = set()
    paths = set()
    prepared = []
    for row in ready:
        metadata = row["metadata"]
        aid = metadata["asset_id"]
        require(aid in expected and aid not in seen and metadata == expected[aid],
                f"Ready metadata/identity mismatch: {aid}")
        seen.add(aid)
        original = previews[aid]
        result = by_id[aid]
        image_path = relative_file(root, row["image_path"])
        require(image_path.is_relative_to(preview_root),
                f"Preview outside expected directory: {aid}")
        require(image_path == relative_file(root, result["preview_local_path"]),
                f"Ready/report image path mismatch: {aid}")
        require(digest(image_path) == row["preview_sha256"]
                == original["sha256"] == result["checksum"],
                f"Preview checksum mismatch: {aid}")
        require(metadata["thumbnail_path"] == original["url"]
                == result["preview_source_url"]
                and result["checksum_resource"] == "preview",
                f"Preview source mismatch: {aid}")
        require(all(metadata.get(key) for key in ("source_url", "author", "license")),
                f"Missing source/author/license: {aid}")
        paths.add(image_path)
        prepared.append((metadata, image_path))
    require(len(paths) == 200, "Expected 200 distinct preview files")
    receipt = {
        "asset_count": len(prepared), "distinct_preview_files": len(paths),
        "w1_preview_hashes_match": True, "manifest_sha256": manifest_hash,
        "ready_manifest_sha256": digest(ready_path),
        "handoff_json_sha256": digest(root / "HANDOFF.json"),
        "sender_source_commit": handoff.get("source_commit"),
        "ingestion_report_sha256": digest(report_path),
        "ingestion_summary": ingestion["summary"],
    }
    return prepared, receipt


def point_id(asset_id):
    return str(uuid5(NAMESPACE_URL, f"ai04/asset/{asset_id}"))


def audit_collection(client, store, metadata):
    config = asdict(store.config)
    expected = {point_id(aid): aid for aid in metadata}
    records = []
    offset = None
    while True:
        page, offset = client.scroll(collection_name=store.collection_name,
                                     limit=256, offset=offset,
                                     with_payload=True, with_vectors=False)
        records.extend(page)
        if offset is None:
            break
    valid = set()
    invalid = []
    ids = []
    asset_ids = []
    for record in records:
        pid = str(record.id)
        ids.append(pid)
        payload = record.payload or {}
        asset_ids.append(payload.get("asset_id"))
        aid = expected.get(pid)
        expected_payload = dict(metadata[aid]) if aid is not None else None
        if expected_payload is not None:
            expected_payload.update(
                model_version=f"{config['model_id']}@{config['model_revision']}",
                index_version=config["index_version"],
                _index={**config, "distance": "Cosine"})
        if expected_payload is None or payload != expected_payload:
            invalid.append(pid)
        else:
            valid.add(aid)
    exact_count = client.count(collection_name=store.collection_name, exact=True).count
    ids_hash = hashlib.sha256(json.dumps(sorted(ids)).encode("utf-8")).hexdigest()
    summary = {
        "exact_point_count": exact_count, "scrolled_point_count": len(records),
        "unique_point_ids": len(set(ids)),
        "unique_payload_asset_ids": len(set(asset_ids)),
        "duplicate_asset_ids": sorted(aid for aid, count in Counter(asset_ids).items()
                                      if count > 1 and isinstance(aid, str)),
        "invalid_payload_or_point_ids": invalid,
        "verified_indexed_asset_count": len(valid), "point_id_set_sha256": ids_hash,
    }
    return summary, valid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff-root", type=Path, required=True)
    parser.add_argument("--phase", choices=("first", "repeat"), required=True)
    parser.add_argument("--collection", default="issue39_objaverse200_clip_v1")
    parser.add_argument("--index-version", default="issue39-objaverse200-clip-v1")
    parser.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--previous-report", type=Path,
                        default=Path("data/processed/issue39/real-assets-first.json"))
    args = parser.parse_args()
    require(args.batch_size > 0, "Batch size must be positive")
    require(args.collection.startswith("issue39_objaverse200_"),
            "Use a dedicated collection starting with issue39_objaverse200_")
    repo = Path(__file__).resolve().parents[1]
    require((repo / "backend/app/embedding/batch.py").is_file(),
            "Place this script under the repository scripts/ directory")
    output = args.report or Path(f"data/processed/issue39/real-assets-{args.phase}.json")
    output = output.resolve()
    require(output.is_relative_to((repo / "data/processed/issue39").resolve()),
            "Save runtime reports under data/processed/issue39/")
    require(not output.exists(), f"Report already exists: {output}; use a new --report")
    prepared, receipt = load_handoff(args.handoff_root.resolve(), repo)
    print("Input verified: 200 unique assets; 200 preview hashes match W1.", flush=True)
    sys.path.insert(0, str(repo / "backend"))
    import torch
    from qdrant_client import QdrantClient
    from app.embedding.batch import AssetImage, embed_assets
    from app.embedding.clip_encoder import (
        CLIPEncoder, MODEL_ID, MODEL_REVISION, PREPROCESSING_VERSION)
    from app.search.qdrant_store import IndexConfig, QdrantStore

    config = IndexConfig(
        model_id=MODEL_ID, model_revision=MODEL_REVISION, dimension=512,
        preprocessing_version=PREPROCESSING_VERSION,
        dataset_snapshot="objaverse200-w1-sha256:" + receipt["manifest_sha256"],
        index_version=args.index_version)
    metadata = {item["asset_id"]: item for item, _ in prepared}
    client = QdrantClient(url=args.qdrant_url, timeout=120)
    store = QdrantStore(client, collection_name=args.collection, config=config)
    prior = None
    if args.phase == "repeat":
        prior = read_json(args.previous_report)
        require(prior["phase"] == "first" and prior["acceptance"]["passed"],
                "Repeat requires a successful first-run report")
        require(prior["collection"] == args.collection
                and prior["index_config"] == asdict(config)
                and prior["input"] == receipt, "First/repeat inputs or config differ")
        require(client.collection_exists(args.collection), "First-run collection is missing")
    store.ensure_collection()
    before, _ = audit_collection(client, store, metadata)
    if args.phase == "first":
        require(before["exact_point_count"] == 0, "First run requires an empty collection")
    else:
        require(before == prior["after"], "Collection changed since the first-run report")
    print(f"Collection: {args.collection}; points before: {before['exact_point_count']}", flush=True)
    command = ["git", "-C", str(repo), "rev-parse", "HEAD"]
    commit = subprocess.check_output(command, text=True).strip()
    started = time.perf_counter()
    evidence = {
        "schema_version": "issue39-real-assets-v1", "phase": args.phase,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_commit": commit, "runner_sha256": digest(Path(__file__)),
        "module_sha256": {name: digest(repo / name) for name in (
            "backend/app/embedding/clip_encoder.py", "backend/app/embedding/batch.py",
            "backend/app/search/qdrant_store.py")},
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "torch_build": str(torch.__version__),
                        "packages": {name: version(name) for name in (
                            "torch", "transformers", "qdrant-client", "Pillow")}},
        "input": receipt, "index_config": asdict(config),
        "processor_revision": MODEL_REVISION, "similarity": "Cosine",
        "normalization": "L2", "device": "cpu", "seed": 0,
        "batch_size": args.batch_size, "collection": args.collection,
        "vector_name": store.vector_name, "qdrant_server": client.info().model_dump(mode="json"),
        "before": before, "previous_report": str(args.previous_report) if prior else None,
        "embedding": {"embedded": 0, "failed": 0, "skipped": 0},
        "upsert_acknowledged": 0, "errors": [], "asset_results": [],
        "limits": "Embedding/index verification only; no PostgreSQL/searchable-state update or retrieval benchmark.",
    }
    norms = []
    try:
        torch.manual_seed(0)
        print("Loading the pinned CLIP model on CPU...", flush=True)
        encoder = CLIPEncoder(device="cpu")
        require(encoder.dimension == config.dimension, "Model dimension mismatch")
        for start in range(0, len(prepared), args.batch_size):
            group = prepared[start:start + args.batch_size]
            batch = embed_assets([AssetImage(item, path) for item, path in group],
                                 encoder, batch_size=args.batch_size)
            for key, value in batch.summary.items():
                evidence["embedding"][key] += value
            for item in batch.embedded:
                norms.append(math.sqrt(sum(v * v for v in item["vector"])))
                evidence["asset_results"].append({"asset_id": item["asset_id"],
                    "point_id": point_id(item["asset_id"]), "embedding": "embedded"})
            for failure in batch.failed:
                evidence["asset_results"].append({**failure, "embedding": "failed"})
            for aid in batch.skipped:
                evidence["asset_results"].append({"asset_id": aid, "embedding": "skipped"})
            try:
                evidence["upsert_acknowledged"] += store.upsert(batch.embedded)
            except Exception as exc:
                evidence["errors"].append({"stage": "upsert", "batch_start": start,
                                            "error": f"{type(exc).__name__}: {exc}"})
            counts = evidence["embedding"]
            print(f"Processed {start + len(group)}/200: embedded={counts['embedded']}, "
                  f"failed={counts['failed']}, skipped={counts['skipped']}, "
                  f"upsert_acknowledged={evidence['upsert_acknowledged']}", flush=True)
    except Exception as exc:
        evidence["errors"].append({"stage": "embedding", "error": f"{type(exc).__name__}: {exc}"})
    valid = set()
    try:
        after, valid = audit_collection(client, store, metadata)
        evidence["after"] = after
    except Exception as exc:
        evidence["after"] = None
        evidence["errors"].append({"stage": "audit", "error": f"{type(exc).__name__}: {exc}"})
    for result in evidence["asset_results"]:
        result["indexed_and_payload_verified"] = result["asset_id"] in valid
    evidence["indexing"] = {"verified_indexed": len(valid), "not_verified_indexed": 200 - len(valid)}
    evidence["embedding"]["not_processed"] = 200 - sum(evidence["embedding"].values())
    evidence["vector_norm"] = {"min": min(norms), "max": max(norms)} if norms else None
    after = evidence["after"]
    checks = {
        "embedded_all_200": evidence["embedding"] == {
            "embedded": 200, "failed": 0, "skipped": 0, "not_processed": 0},
        "all_upserts_acknowledged": evidence["upsert_acknowledged"] == 200,
        "no_runtime_errors": not evidence["errors"],
        "exactly_200_verified_points": bool(after and after["exact_point_count"] == 200
            and after["scrolled_point_count"] == 200 and after["unique_point_ids"] == 200
            and after["unique_payload_asset_ids"] == 200
            and after["verified_indexed_asset_count"] == 200
            and not after["invalid_payload_or_point_ids"] and not after["duplicate_asset_ids"]),
    }
    if prior:
        checks["point_count_unchanged_on_repeat"] = bool(after
            and after["exact_point_count"] == before["exact_point_count"])
        checks["point_ids_unchanged_on_repeat"] = bool(after
            and after["point_id_set_sha256"] == before["point_id_set_sha256"])
    evidence["acceptance"] = {"passed": all(checks.values()), "checks": checks}
    evidence["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    evidence["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    client.close()
    print(json.dumps({key: evidence[key] for key in (
        "phase", "collection", "embedding", "upsert_acknowledged", "indexing",
        "before", "after", "acceptance", "errors", "elapsed_seconds")}, indent=2))
    print(f"Report saved: {output}", flush=True)
    return 0 if evidence["acceptance"]["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
