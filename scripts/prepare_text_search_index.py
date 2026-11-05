"""Dựng index local RIÊNG từ manifest/preview được chỉ định, không ghi DB nghiệp vụ."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--download-previews", action="store_true", required=True,
                        help="Explicitly download only previews in the selected manifest.")
    args = parser.parse_args()
    from app.ingestion.downloader import download_preview_with_retry
    from app.ingestion.source_adapter import SourceAdapter

    adapter = SourceAdapter(args.manifest)
    metadata, invalid = adapter.normalize_and_validate(adapter.load_manifest())
    if invalid or not metadata:
        raise ValueError("Manifest must contain only valid nonempty metadata.")
    output = ROOT / "data/processed/issue65" / ("index-" + uuid4().hex[:12])
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.manifest, output / "source.json")
    previews = output / "previews"
    previews.mkdir()
    results, errors = {}, []
    print(f"Downloading {len(metadata)} selected previews; no model download.", flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(download_preview_with_retry, row["thumbnail_path"], previews, max_attempts=2): row
                   for row in metadata}
        for index, future in enumerate(as_completed(futures), 1):
            row = futures[future]
            try:
                result = future.result()
                results[row["asset_id"]] = {**result, "asset_id": row["asset_id"]}
            except Exception as exc:
                errors.append({"asset_id": row["asset_id"], "code": type(exc).__name__})
            if index % 25 == 0 or index == len(metadata):
                print(f"Preview progress {index}/{len(metadata)}, failed={len(errors)}", flush=True)
    (output / "downloads.json").write_text(json.dumps({"results": list(results.values()), "errors": errors},
                                                     ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        print("Input incomplete; report retained, no index built: " + str(output), flush=True)
        return 1
    ready = [{"metadata": row, "image_path": Path(results[row["asset_id"]]["preview_local_path"]).resolve().relative_to(output).as_posix(),
              "checksum": results[row["asset_id"]]["checksum"]} for row in metadata]
    (output / "ready.json").write_text(json.dumps(ready, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from app.embedding.batch import AssetImage, embed_assets
    from app.services.text_search_runtime import load_encoder
    from app.search.index_manifest import IndexManifest, save_index_manifest
    from app.search.qdrant_store import IndexConfig, QdrantStore
    from app.search.retrieval_config import RetrievalConfig
    from qdrant_client import QdrantClient

    print("Loading pinned CLIP from cache, then embedding previews...", flush=True)
    encoder = load_encoder()
    batch = embed_assets([AssetImage(row["metadata"], output / row["image_path"]) for row in ready], encoder, batch_size=8)
    if batch.summary != {"embedded": len(metadata), "failed": 0, "skipped": 0}:
        print("Embedding incomplete: " + str(batch.summary), flush=True)
        return 1
    digest = lambda path: sha256(path.read_bytes()).hexdigest()
    config = IndexConfig(model_id=encoder.model_id, model_revision=encoder.revision, dimension=encoder.dimension,
        preprocessing_version=encoder.preprocessing_version,
        dataset_snapshot=args.snapshot + "-sha256:" + digest(output / "source.json"),
        index_version="issue65-" + args.snapshot + "-clip-v1")
    with closing(QdrantClient(path=str(output / "qdrant"))) as client:
        store = QdrantStore(client, collection_name="issue65_text_search", config=config)
        assert store.upsert(batch.embedded) == len(metadata)
        count = client.count(store.collection_name, exact=True).count
        assert count == len(metadata)
        observed = datetime.now(timezone.utc)
        manifest = IndexManifest(
            created_at_utc=datetime.now(timezone.utc), observed_at_utc=observed,
            index_config=asdict(config), collection=store.collection_name, vector_name=store.vector_name,
            processor_revision=encoder.revision, tokenizer_revision=encoder.revision,
            max_text_tokens=encoder.model.config.text_config.max_position_embeddings,
            source_manifest="source.json", source_manifest_sha256=digest(output / "source.json"),
            ready_manifest="ready.json", ready_manifest_sha256=digest(output / "ready.json"),
            asset_count=len(metadata), point_count=count,
            code_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            working_tree_dirty=bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
            module_sha256={name: digest(ROOT / name) for name in (
                "scripts/prepare_text_search_index.py", "backend/app/embedding/clip_encoder.py",
                "backend/app/search/text_search.py", "backend/app/search/qdrant_store.py")},
            retrieval_config=RetrievalConfig(),
        )
        save_index_manifest(manifest, output / "index-manifest.json")
    print("Prepared standalone index: " + str(output), flush=True)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")
    raise SystemExit(main())
