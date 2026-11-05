"""Kiểm chứng CLIP retrieval và audit index chỉ đọc."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from math import isclose, isfinite, sqrt
from pathlib import Path, PurePosixPath
import platform
import subprocess
import time
from uuid import NAMESPACE_URL, uuid4, uuid5

from PIL import Image
from qdrant_client import QdrantClient

from app.schemas.text_search import TextSearchFilters, TextSearchHit
from app.search.index_manifest import IndexManifest, load_index_manifest, save_index_manifest
from app.search.qdrant_store import IndexConfig, QdrantStore
from app.search.retrieval_config import RetrievalConfig
from app.search.text_search import SearchUnavailableError, TextSearchService


SOURCE_MANIFEST = "data/manifests/objaverse_200.json"
READY_MANIFEST = "data/processed/ingestion/objaverse_200.ready.json"
REPEAT_SCORE_ABS_TOLERANCE = 1e-12
MODULE_PATHS = (
    "backend/app/embedding/clip_encoder.py",
    "backend/app/search/filters.py",
    "backend/app/search/qdrant_store.py",
    "backend/app/search/retrieval_config.py",
    "backend/app/search/index_manifest.py",
    "backend/app/search/text_search.py",
    "backend/app/search/smoke.py",
    "backend/app/schemas/api.py",
    "backend/app/schemas/text_search.py",
    "scripts/verify_issue60_text_retrieval.py",
    "docs/configs/clip-text-exact-v1.json",
)


class SmokeCheckError(ValueError):
    """Mã lỗi cố định, không chứa query/URL/credentials hoặc exception gốc."""


def require(condition, code):
    if not condition:
        raise SmokeCheckError(code)


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def handoff_file(root, relative):
    require(isinstance(relative, str) and relative and ":" not in relative
            and "\\" not in relative and not PurePosixPath(relative).is_absolute()
            and all(part not in {"", ".", ".."} for part in relative.split("/")),
            "invalid_handoff_path")
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(root) and path.is_file(), "missing_or_external_handoff_file")
    return path


def load_inputs(root, reference, *, source_manifest=SOURCE_MANIFEST,
                ready_manifest=READY_MANIFEST, preview_directory="data/raw/objaverse/previews"):
    """Kiểm tra manifest, ready records và ảnh trong cùng gói bàn giao."""
    expected = reference["input"]
    source_path = handoff_file(root, source_manifest)
    ready_path = handoff_file(root, ready_manifest)
    require(digest(source_path) == expected["manifest_sha256"], "source_manifest_hash_mismatch")
    require(digest(ready_path) == expected["ready_manifest_sha256"], "ready_manifest_hash_mismatch")
    source, ready = read_json(source_path), read_json(ready_path)
    require(isinstance(source, list) and isinstance(ready, list)
            and len(source) == len(ready) == expected["asset_count"], "input_count_mismatch")
    metadata = {}
    for item in source:
        require(isinstance(item, dict), "invalid_source_record")
        aid = TextSearchHit(asset_id=item.get("asset_id"), score=0).asset_id
        require(aid not in metadata, "duplicate_source_asset")
        metadata[aid] = item
    seen_ids, preview_paths = set(), set()
    preview_root = (Path(root).resolve() / preview_directory).resolve()
    for row in ready:
        require(isinstance(row, dict) and isinstance(row.get("metadata"), dict), "invalid_ready_record")
        aid = row["metadata"].get("asset_id")
        require(isinstance(aid, str) and aid in metadata and aid not in seen_ids
                and row["metadata"] == metadata[aid], "ready_metadata_mismatch")
        seen_ids.add(aid)
        path = handoff_file(root, row.get("image_path"))
        require(path.is_relative_to(preview_root) and path not in preview_paths,
                "invalid_or_duplicate_preview_path")
        require(digest(path) == row.get("preview_sha256"), "preview_checksum_mismatch")
        with Image.open(path) as image:
            image.load()
        preview_paths.add(path)
    require(seen_ids == set(metadata), "ready_asset_ids_mismatch")
    return metadata, {
        "source_manifest": source_manifest,
        "manifest_sha256": digest(source_path),
        "ready_manifest": ready_manifest,
        "ready_manifest_sha256": digest(ready_path),
        "asset_count": len(metadata), "distinct_readable_previews": len(preview_paths),
    }


def audit_index(store, metadata):
    """Audit toàn bộ IDs/payload/vectors và fingerprint, chỉ dùng lệnh đọc."""
    store.validate_collection()
    client, name = store.client, store.collection_name
    count = client.count(collection_name=name, exact=True).count
    records, offset, cursors = [], None, set()
    while True:
        page, offset = client.scroll(
            collection_name=name, limit=256, offset=offset,
            with_payload=True, with_vectors=True,
        )
        records.extend(page)
        require(len(records) <= count, "collection_changed_during_audit")
        if offset is None:
            break
        require(str(offset) not in cursors, "repeated_scroll_cursor")
        cursors.add(str(offset))
    require(len(records) == count == len(metadata), "index_count_mismatch")
    point_ids, asset_ids, serialized = set(), set(), []
    for point in records:
        payload = point.payload or {}
        aid = payload.get("asset_id")
        require(isinstance(aid, str) and aid in metadata and aid not in asset_ids,
                "unknown_or_duplicate_index_asset")
        pid = str(point.id)
        expected_id = str(uuid5(NAMESPACE_URL, f"ai04/asset/{aid}"))
        require(pid == expected_id and pid not in point_ids, "invalid_index_point_id")
        expected_payload = {
            **metadata[aid],
            "model_version": f"{store.config.model_id}@{store.config.model_revision}",
            "index_version": store.config.index_version,
            "_index": {**asdict(store.config), "distance": "Cosine"},
        }
        require(payload == expected_payload, "index_payload_mismatch")
        require(isinstance(point.vector, dict) and set(point.vector) == {store.vector_name},
                "index_named_vector_mismatch")
        vector = point.vector[store.vector_name]
        require(isinstance(vector, list) and len(vector) == store.config.dimension
                and all(isinstance(v, (float, int)) and not isinstance(v, bool)
                        and isfinite(v) for v in vector), "invalid_index_vector")
        require(isclose(sqrt(sum(v * v for v in vector)), 1.0, rel_tol=0, abs_tol=1e-5),
                "index_vector_not_l2_normalized")
        point_ids.add(pid)
        asset_ids.add(aid)
        serialized.append({"point_id": pid, "payload": payload, "vector": point.vector})
    content = json.dumps(sorted(serialized, key=lambda p: p["point_id"]),
                         sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return {
        "exact_point_count": count, "scrolled_point_count": len(records),
        "unique_asset_ids": len(asset_ids), "unique_point_ids": len(point_ids),
        "point_id_set_sha256": sha256(json.dumps(sorted(point_ids)).encode("utf-8")).hexdigest(),
        "point_payload_vector_sha256": sha256(content.encode("utf-8")).hexdigest(),
    }


def matches(metadata, filters):
    """Đối chiếu độc lập trên metadata gốc, không gọi filter builder."""
    for key in ("category", "license"):
        value = getattr(filters, key)
        if value is not None and metadata.get(key) != value:
            return False
    if filters.format is not None and filters.format not in (metadata.get("formats") or []):
        return False
    if filters.face_count_min is not None or filters.face_count_max is not None:
        count = metadata.get("face_count")
        if isinstance(count, bool) or not isinstance(count, int):
            return False
        if filters.face_count_min is not None and count < filters.face_count_min:
            return False
        if filters.face_count_max is not None and count > filters.face_count_max:
            return False
    return True


def smoke_cases(metadata):
    ordered = sorted(metadata.values(), key=lambda row: row["asset_id"])
    complete = next((row for row in ordered if row.get("category") and row.get("license")
                     and row.get("formats") and isinstance(row.get("face_count"), int)
                     and not isinstance(row["face_count"], bool)), None)
    require(complete is not None, "missing_metadata_for_live_filter_coverage")
    empty_category = "__issue60_absent_category__"
    while any(row.get("category") == empty_category for row in ordered):
        empty_category += "_"
    return [
        ("unfiltered_en", "wooden chair", {}),
        ("unfiltered_vi", "ghế gỗ", {}),
        ("category", "wooden chair", {"category": complete["category"]}),
        ("license", "wooden chair", {"license": complete["license"]}),
        ("format", "wooden chair", {"format": complete["formats"][0]}),
        ("face_min", "wooden chair", {"face_count_min": complete["face_count"]}),
        ("face_max", "wooden chair", {"face_count_max": complete["face_count"]}),
        ("and_exact_bounds", "wooden chair", {
            "category": complete["category"], "license": complete["license"],
            "format": complete["formats"][0],
            "face_count_min": complete["face_count"], "face_count_max": complete["face_count"],
        }),
        ("empty", "wooden chair", {"category": empty_category}),
        ("token_truncation", ("chair " * 83).strip(), {}),
    ]


def run_queries(service, encoder, metadata, retrieval, reports=None):
    reports = [] if reports is None else reports
    for label, query, raw_filters in smoke_cases(metadata):
        filters = TextSearchFilters(**raw_filters)
        started = time.perf_counter()
        result = service.search_text(query, filters, candidate_limit=retrieval.candidate_limit)
        elapsed = time.perf_counter() - started
        expected = {aid for aid, row in metadata.items() if matches(row, filters)}
        ids = [hit.asset_id for hit in result.hits]
        expected_returned = min(len(expected), retrieval.candidate_limit)
        require(len(ids) == expected_returned and set(ids) <= expected
                and len(ids) == len(set(ids)), "query_filter_or_dedup_mismatch")
        vector = encoder.encode_text(query)
        norm = sqrt(sum(v * v for v in vector))
        require(len(vector) == service.store.config.dimension and isfinite(norm)
                and isclose(norm, 1.0, rel_tol=0, abs_tol=1e-5), "invalid_real_text_vector")
        input_tokens = len(encoder.processor.tokenizer(query, truncation=False, verbose=False)["input_ids"])
        max_tokens = encoder.model.config.text_config.max_position_embeddings
        if label == "token_truncation":
            require(input_tokens > max_tokens, "truncation_not_exercised")
        reports.append({
            "case": label, "query": query, "filters": filters.model_dump(exclude_none=True),
            "expected_asset_count": len(expected), "expected_returned_count": expected_returned,
            "returned_count": len(ids),
            "versions": result.versions.model_dump(), "elapsed_seconds": round(elapsed, 6),
            "text_vector_dimension": len(vector), "text_vector_l2_norm": norm,
            "input_tokens": input_tokens, "max_text_tokens": max_tokens,
            "truncated": input_tokens > max_tokens,
            "hits": [{**hit.model_dump(), "metadata": {
                key: metadata[hit.asset_id].get(key)
                for key in ("category", "license", "formats", "face_count")
            }} for hit in result.hits],
        })
        print(f"{label}: {len(ids)} results; filters checked against source metadata", flush=True)
    repeated = service.search_text("wooden chair", TextSearchFilters(),
                                   candidate_limit=retrieval.candidate_limit)
    first = reports[0]
    ordered_ids_equal = [hit.asset_id for hit in repeated.hits] == [
        hit["asset_id"] for hit in first["hits"]
    ]
    versions_equal = repeated.versions.model_dump() == first["versions"]
    max_score_delta = None
    if ordered_ids_equal:
        max_score_delta = max(
            (abs(hit.score - prior["score"]) for hit, prior in zip(repeated.hits, first["hits"], strict=True)),
            default=0.0,
        )
    first["repeat"] = {
        "ordered_asset_ids_equal": ordered_ids_equal,
        "versions_equal": versions_equal,
        "max_score_abs_delta": max_score_delta,
        "score_abs_tolerance": REPEAT_SCORE_ABS_TOLERANCE,
    }
    require(versions_equal and max_score_delta is not None
            and max_score_delta <= REPEAT_SCORE_ABS_TOLERANCE, "repeat_query_changed")
    return reports


def output_directory(repo, requested=None):
    base = (Path(repo) / "data/processed/issue60").resolve()
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6]
    target = ((Path(repo) / requested) if requested is not None else base / ("smoke-" + tag)).resolve()
    require(target != base and target.is_relative_to(base), "output_outside_issue60_runtime_directory")
    require(not target.exists(), "output_already_exists")
    target.mkdir(parents=True, exist_ok=False)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff-root", type=Path, required=True)
    parser.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[3]
    output = output_directory(repo, args.output_dir)
    started = datetime.now(timezone.utc)
    checks = {key: False for key in (
        "handoff_200_previews_verified", "index_200_points_verified", "real_clip_loaded",
        "all_queries_verified", "repeat_stable", "index_unchanged", "source_code_unchanged",
        "manifest_roundtrip_verified",
    )}
    report = {
        "schema_version": "issue60-text-retrieval-smoke-v1",
        "started_at_utc": started.isoformat(), "checks": checks,
        "errors": [], "queries": [],
        "limits": "Read-only service smoke on historical #39 snapshot; no HTTP/DB integration or relevance benchmark.",
    }
    client, store, metadata, before = None, None, None, None
    stage = "inputs"
    try:
        reference_path = repo / "docs/evidence/issue39-real-assets.json"
        reference = read_json(reference_path)["shared_config"]
        metadata, receipt = load_inputs(args.handoff_root.resolve(), reference)
        require(receipt["asset_count"] == 200, "expected_200_assets")
        report["input"] = receipt
        report["reference_evidence_sha256"] = digest(reference_path)
        report["current_repo_manifest_sha256"] = digest(repo / SOURCE_MANIFEST)
        checks["handoff_200_previews_verified"] = True
        print("Verified 200 source IDs and readable preview checksums in the old handoff.", flush=True)
        retrieval = RetrievalConfig.model_validate_json((repo / "docs/configs/clip-text-exact-v1.json").read_text(encoding="utf-8"))
        require(retrieval.candidate_limit == 200, "smoke_requires_candidate_window_200")
        config = IndexConfig(**reference["index_config"])
        require(config.dataset_snapshot.endswith("sha256:" + receipt["manifest_sha256"]), "snapshot_hash_mismatch")
        report["code_commit"] = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        report["working_tree_dirty"] = bool(subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL).strip())
        report["module_sha256"] = {name: digest(repo / name) for name in MODULE_PATHS}
        report["retrieval_config"] = retrieval.model_dump(mode="json")
        stage = "qdrant_audit"
        client = QdrantClient(url=args.qdrant_url, timeout=30)
        store = QdrantStore(client, collection_name=reference["collection"], config=config)
        require(store.vector_name == reference["vector_name"], "reference_vector_name_mismatch")
        before = audit_index(store, metadata)
        report["before"] = before
        report["qdrant_server"] = client.info().model_dump(mode="json")
        checks["index_200_points_verified"] = True
        print("Verified 200 existing Qdrant points, IDs, payloads and normalized vectors.", flush=True)
        stage = "model_cache"
        print("Loading pinned CLIP on CPU from local cache only (no model download)...", flush=True)
        import torch
        from app.embedding.clip_encoder import CLIPEncoder
        torch.manual_seed(0)
        encoder = CLIPEncoder(device="cpu", local_files_only=True)
        report["environment"] = {
            "python": platform.python_version(), "platform": platform.platform(),
            "torch_build": str(torch.__version__), "device": "cpu", "seed": 0,
            "packages": {name: version(name) for name in ("torch", "transformers", "qdrant-client", "Pillow")},
        }
        actual = (encoder.model_id, encoder.revision, encoder.dimension, encoder.preprocessing_version)
        require(actual == (config.model_id, config.model_revision, config.dimension, config.preprocessing_version),
                "real_encoder_incompatible")
        checks["real_clip_loaded"] = True
        stage = "queries"
        run_queries(TextSearchService(encoder, store), encoder, metadata, retrieval,
                    reports=report["queries"])
        checks["all_queries_verified"] = checks["repeat_stable"] = True
    except Exception as exc:
        code = exc.reason if isinstance(exc, SearchUnavailableError) else (str(exc) if isinstance(exc, SmokeCheckError) else type(exc).__name__)
        report["errors"].append({"stage": stage, "code": code})
    finally:
        if before is not None:
            try:
                report["after"] = audit_index(store, metadata)
                checks["index_unchanged"] = report["after"] == before
            except Exception as exc:
                report["errors"].append({"stage": "after_audit", "code": type(exc).__name__})
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                report["errors"].append({"stage": "close", "code": type(exc).__name__})
    if checks["all_queries_verified"] and not report["errors"]:
        try:
            current_hashes = {name: digest(repo / name) for name in MODULE_PATHS}
            checks["source_code_unchanged"] = current_hashes == report["module_sha256"]
            require(checks["source_code_unchanged"] and checks["index_unchanged"], "source_or_index_changed")
            observed = datetime.now(timezone.utc)
            manifest = IndexManifest(
                created_at_utc=datetime.now(timezone.utc), observed_at_utc=observed,
                index_config=asdict(config), collection=store.collection_name, vector_name=store.vector_name,
                processor_revision=encoder.revision, tokenizer_revision=encoder.revision,
                max_text_tokens=encoder.model.config.text_config.max_position_embeddings,
                source_manifest=SOURCE_MANIFEST, source_manifest_sha256=receipt["manifest_sha256"],
                ready_manifest=READY_MANIFEST, ready_manifest_sha256=receipt["ready_manifest_sha256"],
                asset_count=len(metadata), point_count=before["exact_point_count"],
                code_commit=report["code_commit"], working_tree_dirty=report["working_tree_dirty"],
                module_sha256=current_hashes, retrieval_config=retrieval,
            )
            manifest.check_encoder(encoder)
            manifest.verify_input_hashes(args.handoff_root)
            require(all(q["versions"] == manifest.execution_versions().model_dump() for q in report["queries"]), "query_manifest_versions_mismatch")
            save_index_manifest(manifest, output / "index-manifest.json")
            require(load_index_manifest(output / "index-manifest.json") == manifest, "manifest_roundtrip_mismatch")
            checks["manifest_roundtrip_verified"] = True
        except Exception as exc:
            report["errors"].append({"stage": "manifest", "code": str(exc) if isinstance(exc, SmokeCheckError) else type(exc).__name__})
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["acceptance"] = {"passed": all(checks.values()) and not report["errors"]}
    with (output / "report.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"acceptance": report["acceptance"], "checks": checks,
                      "errors": report["errors"], "query_cases": len(report["queries"])}, indent=2), flush=True)
    print(f"Report saved: {output / 'report.json'}", flush=True)
    if checks["manifest_roundtrip_verified"]:
        print(f"Index manifest saved: {output / 'index-manifest.json'}", flush=True)
    return 0 if report["acceptance"]["passed"] else 1
