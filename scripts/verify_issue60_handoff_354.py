"""Tạo index Qdrant local riêng và kiểm chứng retrieval cho gói #62 đã đối chiếu."""

import argparse
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZipFile


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
os.environ["HF_HUB_OFFLINE"] = "1"

from qdrant_client import QdrantClient

from app.search.index_manifest import IndexManifest, load_index_manifest, save_index_manifest
from app.search.qdrant_store import IndexConfig, QdrantStore
from app.search.retrieval_config import RetrievalConfig
from app.search.smoke import (
    MODULE_PATHS, SmokeCheckError, audit_index, digest, handoff_file, load_inputs,
    output_directory, read_json, require, run_queries,
)
from app.search.text_search import SearchUnavailableError, TextSearchService


SNAPSHOT = "home-interior-354-v1"
ASSET_COUNT = 354
ZIP_SHA256 = "a12bc29e1d5638e25eda9aab766e9324afdda1263fb6fbd3c14d2f17c30d4d25"
SOURCE_MANIFEST = "manifests/assets_354.json"
READY_MANIFEST = "assets_354.ready.json"
INPUT = {
    "manifest_sha256": "93f65237ca51060aad75f0f672b2b16f76c89a64dce64d7473791f428e944614",
    "ready_manifest_sha256": "7d0a3e59f4d1c697cb37fd8b82decea3ba3efa95d8c84235bda73b5afb67474c",
    "asset_count": ASSET_COUNT,
}
COLLECTION = "issue60_home_interior_354_clip_v1"
INDEX_VERSION = "issue60-home-interior-354-clip-v1"
BATCH_SIZE = 8
BUILD_MODULES = (
    *(name for name in MODULE_PATHS if name != "scripts/verify_issue60_text_retrieval.py"),
    "backend/app/embedding/batch.py",
    "scripts/verify_issue60_handoff_354.py",
)


def unpack_verified_input(archive, output):
    payload = archive.read_bytes()
    require(sha256(payload).hexdigest() == ZIP_SHA256, "handoff_zip_checksum_mismatch")
    prefix = SNAPSHOT + "/"
    fixed_files = {prefix + SOURCE_MANIFEST, prefix + READY_MANIFEST, prefix + "HANDOFF.json"}
    preview_pattern = re.compile(re.escape(prefix) + r"previews/[0-9a-f]{64}\.jpg")
    with ZipFile(BytesIO(payload)) as bundle:
        previews = [name for name in bundle.namelist() if preview_pattern.fullmatch(name)]
        require(len(previews) == len(set(previews)) == ASSET_COUNT, "handoff_preview_count_mismatch")
        for member in sorted(fixed_files) + previews:
            bundle.extract(member, output)
    return output / SNAPSHOT


def main():
    parser = argparse.ArgumentParser(description="Build a separate local Qdrant index and verify retrieval for the #62 handoff.")
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    output = output_directory(REPO)
    started = datetime.now(timezone.utc)
    report = {
        "schema_version": "issue60-handoff-354-smoke-v1",
        "started_at_utc": started.isoformat(),
        "snapshot": SNAPSHOT,
        "storage_mode": "qdrant_persistent_local",
        "storage_directory": "qdrant",
        "package_directory": SNAPSHOT,
        "queries": [],
        "acceptance": {"passed": False},
    }
    stage = "handoff"
    try:
        root = unpack_verified_input(args.archive, output)
        metadata, receipt = load_inputs(
            root, {"input": INPUT}, source_manifest=SOURCE_MANIFEST,
            ready_manifest=READY_MANIFEST, preview_directory="previews",
        )
        report["input"] = {**receipt, "zip_sha256": ZIP_SHA256}
        print(f"Verified {len(metadata)} assets and previews in {SNAPSHOT}.", flush=True)

        stage = "model_cache"
        print("Loading pinned CLIP on CPU from the local cache...", flush=True)
        import torch
        from app.embedding.batch import AssetImage, embed_assets
        from app.embedding.clip_encoder import CLIPEncoder

        torch.manual_seed(0)
        encoder = CLIPEncoder(device="cpu", local_files_only=True)
        require(encoder.dimension == 512, "unexpected_clip_dimension")
        retrieval = RetrievalConfig.model_validate_json(
            (REPO / "docs/configs/clip-text-exact-v1.json").read_text(encoding="utf-8")
        )
        require(retrieval.candidate_limit == 200, "smoke_requires_candidate_window_200")
        config = IndexConfig(
            model_id=encoder.model_id, model_revision=encoder.revision,
            dimension=encoder.dimension, preprocessing_version=encoder.preprocessing_version,
            dataset_snapshot=f"{SNAPSHOT}-sha256:{receipt['manifest_sha256']}",
            index_version=INDEX_VERSION,
        )
        code_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
        dirty = bool(subprocess.check_output(
            ["git", "--no-optional-locks", "status", "--porcelain"], cwd=REPO, text=True,
        ).strip())
        source_hashes = {name: digest(REPO / name) for name in BUILD_MODULES}
        report["index_config"] = asdict(config)
        report["environment"] = {
            "python": sys.version.split()[0], "torch_build": str(torch.__version__),
            "device": "cpu", "seed": 0, "batch_size": BATCH_SIZE,
            "packages": {name: version(name) for name in ("torch", "transformers", "qdrant-client", "Pillow")},
        }

        stage = "embedding"
        ready = read_json(root / READY_MANIFEST)
        assets = [AssetImage(row["metadata"], handoff_file(root, row["image_path"])) for row in ready]
        print(f"Encoding {len(assets)} preview images...", flush=True)
        batch = embed_assets(assets, encoder, batch_size=BATCH_SIZE)
        report["embedding"] = batch.summary
        require(batch.summary == {"embedded": ASSET_COUNT, "failed": 0, "skipped": 0}, "incomplete_embedding_batch")

        stage = "index_build"
        storage = output / "qdrant"
        require(not storage.exists(), "index_storage_already_exists")
        with closing(QdrantClient(path=str(storage))) as client:
            store = QdrantStore(client, collection_name=COLLECTION, config=config)
            require(store.upsert(batch.embedded) == ASSET_COUNT, "incomplete_index_write")

        stage = "retrieval"
        with closing(QdrantClient(path=str(storage))) as client:
            store = QdrantStore(client, collection_name=COLLECTION, config=config)
            report["before"] = audit_index(store, metadata)
            print(f"Wrote and audited {report['before']['exact_point_count']} points in a new local index.", flush=True)
            service = TextSearchService(encoder, store)
            run_queries(service, encoder, metadata, retrieval, reports=report["queries"])

        # Qdrant local có thể chuẩn hóa vector in-place trong bộ nhớ khi tính cosine.
        # Mở lại client để audit cùng dữ liệu đã lưu như lúc bắt đầu retrieval.
        stage = "persisted_index_audit"
        with closing(QdrantClient(path=str(storage))) as client:
            store = QdrantStore(client, collection_name=COLLECTION, config=config)
            report["after"] = audit_index(store, metadata)
        require(report["after"] == report["before"], "persisted_index_changed")

        stage = "manifest"
        require(source_hashes == {name: digest(REPO / name) for name in BUILD_MODULES}, "source_code_changed")
        observed = datetime.now(timezone.utc)
        manifest = IndexManifest(
            created_at_utc=datetime.now(timezone.utc), observed_at_utc=observed,
            index_config=asdict(config), collection=COLLECTION, vector_name=store.vector_name,
            processor_revision=encoder.revision, tokenizer_revision=encoder.revision,
            max_text_tokens=encoder.model.config.text_config.max_position_embeddings,
            source_manifest=SOURCE_MANIFEST, source_manifest_sha256=receipt["manifest_sha256"],
            ready_manifest=READY_MANIFEST, ready_manifest_sha256=receipt["ready_manifest_sha256"],
            asset_count=len(metadata), point_count=report["after"]["exact_point_count"],
            code_commit=code_commit, working_tree_dirty=dirty, module_sha256=source_hashes,
            retrieval_config=retrieval,
        )
        manifest.check_encoder(encoder)
        manifest.verify_input_hashes(root)
        versions = manifest.execution_versions().model_dump()
        require(all(case["versions"] == versions for case in report["queries"]), "query_manifest_versions_mismatch")
        manifest_path = output / "index-manifest.json"
        save_index_manifest(manifest, manifest_path)
        require(load_index_manifest(manifest_path) == manifest, "manifest_roundtrip_mismatch")
        report["index_manifest_sha256"] = digest(manifest_path)
        report["acceptance"]["passed"] = True
    except Exception as exc:
        if isinstance(exc, SearchUnavailableError):
            code = exc.reason
        elif isinstance(exc, SmokeCheckError):
            code = str(exc)
        else:
            code = type(exc).__name__
        report["error"] = {"stage": stage, "code": code}

    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    report_path = output / "report.json"
    with report_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"acceptance": report["acceptance"], "error": report.get("error"),
                      "query_cases": len(report["queries"])}, indent=2), flush=True)
    print(f"Report saved: {report_path}", flush=True)
    if report["acceptance"]["passed"]:
        print(f"Index manifest saved: {manifest_path}", flush=True)
    return 0 if report["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
