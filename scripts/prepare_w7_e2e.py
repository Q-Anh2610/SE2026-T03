"""Chuẩn bị dữ liệu thật cho #149 trong DB test rỗng và collection mới, offline."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def prepare(handoff, qdrant_url):
    from qdrant_client import QdrantClient
    from sqlalchemy import create_engine, func, make_url, select
    from sqlalchemy.orm import Session
    from app.embedding.batch import AssetImage, embed_assets
    from app.models import Asset, Feedback, SearchEvent
    from app.search.image_index_manifest import load_image_index_manifest, save_image_index_manifest
    from app.search.image_search import ImageRetrievalConfig
    from app.search.index_manifest import IndexManifest, save_index_manifest
    from app.search.qdrant_store import IndexConfig, QdrantStore
    from app.search.retrieval_config import RetrievalConfig
    from app.services.text_search_runtime import load_encoder

    db_url = make_url(os.environ["TEST_DATABASE_URL"])
    if (db_url.drivername != "postgresql+psycopg"
            or not (db_url.database or "").startswith("test_issue149_")
            or db_url.host not in {"127.0.0.1", "localhost"}):
        raise ValueError("Cần PostgreSQL local test_issue149_* riêng, đã migrate và rỗng.")
    target = urlsplit(qdrant_url)
    if (target.scheme != "http" or target.hostname not in {"localhost", "127.0.0.1"}
            or target.username or target.password or target.path not in {"", "/"}
            or target.query or target.fragment):
        raise ValueError("Cần Qdrant HTTP origin local riêng.")
    handoff = handoff.resolve()
    original = load_image_index_manifest(handoff / "index/index-manifest.json")
    inputs = handoff / "input"
    original.verify_input_hashes(inputs)
    if original.source_manifest_sha256 != "9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd":
        raise ValueError("Harness này dùng snapshot home-interior-clear-200-v3 đã bàn giao.")
    source = json.loads((inputs / original.source_manifest).read_text(encoding="utf-8"))
    ready = json.loads((inputs / original.ready_manifest).read_text(encoding="utf-8"))
    if (len(source) != 200 or len(ready) != 200
            or len({row["asset_id"] for row in source}) != 200
            or {row["asset_id"]: row for row in source}
            != {row["metadata"]["asset_id"]: row["metadata"] for row in ready}):
        raise ValueError("Source/ready cần khớp đúng 200 asset duy nhất.")
    for row in ready:
        path = (inputs / row["image_path"]).resolve()
        if not path.is_relative_to(inputs.resolve()) or digest(path) != row["preview_sha256"]:
            raise ValueError("Preview path/checksum không hợp lệ.")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output = ROOT / "data/runtime/issue149" / run_id
    output.mkdir(parents=True, exist_ok=False)
    for name in (original.source_manifest, original.ready_manifest):
        shutil.copyfile(inputs / name, output / name)
    for row in ready:
        destination = output / row["image_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(inputs / row["image_path"], destination)
    engine = create_engine(db_url, hide_parameters=True, connect_args={"connect_timeout": 5})
    client = QdrantClient(url=qdrant_url, timeout=30)
    try:
        with Session(engine) as session:
            if any(session.scalar(select(func.count()).select_from(model)) for model in (Asset, SearchEvent, Feedback)):
                raise ValueError("DB không rỗng; giữ dữ liệu hiện có, dùng DB mới.")
        import torch
        torch.set_num_threads(4)
        torch.manual_seed(0)
        encoder = load_encoder()  # local_files_only=True; không tải weights.
        original.check_encoder(encoder)
        print("Encoding 200 checked previews with pinned CLIP offline...", flush=True)
        batch = embed_assets([AssetImage(row["metadata"], output / row["image_path"]) for row in ready], encoder, batch_size=8)
        if batch.summary != {"embedded": 200, "failed": 0, "skipped": 0}:
            raise ValueError("Embedding chưa hoàn tất; giữ output để kiểm tra.")
        config = IndexConfig(**{**asdict(original.as_index_config()), "index_version": "issue149-" + run_id})
        store = QdrantStore(client, collection_name="issue149_" + uuid4().hex, config=config)
        if client.collection_exists(store.collection_name):
            raise ValueError("Collection đã tồn tại; không ghi đè.")
        if store.upsert(batch.embedded) != 200 or client.count(store.collection_name, exact=True).count != 200:
            raise ValueError("Qdrant chưa xác nhận đủ 200 point.")
        store.validate_collection()
        with Session(engine) as session, session.begin():
            session.add_all([Asset(**{**row, "model_version": f"{config.model_id}@{config.model_revision}",
                                      "index_version": config.index_version}) for row in source])
        now = datetime.now(timezone.utc)
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
        common = dict(created_at_utc=now, observed_at_utc=now, index_config=asdict(config),
                      collection=store.collection_name, vector_name=store.vector_name,
                      code_commit=commit, working_tree_dirty=dirty,
                      module_sha256={name: digest(ROOT / name) for name in (
                          "scripts/prepare_w7_e2e.py", "backend/app/embedding/clip_encoder.py",
                          "backend/app/embedding/batch.py", "backend/app/search/qdrant_store.py")})
        image = original.model_copy(update={**common, "retrieval_config": ImageRetrievalConfig()})
        save_image_index_manifest(image, output / "image-index-manifest.json")
        text = IndexManifest(**common, processor_revision=encoder.revision, tokenizer_revision=encoder.revision,
                             max_text_tokens=encoder.model.config.text_config.max_position_embeddings,
                             source_manifest=original.source_manifest, source_manifest_sha256=original.source_manifest_sha256,
                             ready_manifest=original.ready_manifest, ready_manifest_sha256=original.ready_manifest_sha256,
                             asset_count=200, point_count=200, retrieval_config=RetrievalConfig())
        save_index_manifest(text, output / "text-index-manifest.json")
        complete = next(row for row in source if row["category"] and row["license"] and row["formats"] and row["face_count"] is not None)
        write_json(output / "suite-input.json", dict(query_image=ready[0]["image_path"],
                   query_sha256=ready[0]["preview_sha256"], asset_count=200,
                   text_versions=text.execution_versions().model_dump(), image_versions=image.execution_versions().model_dump(),
                   filters=dict(category=complete["category"], license=complete["license"], format=complete["formats"][0],
                                face_count_min=complete["face_count"], face_count_max=complete["face_count"])))
        write_json(output / "preparation.json", dict(status="prepared", run_id=run_id, code_commit=commit,
                   working_tree_dirty=dirty, database=db_url.database, collection=store.collection_name,
                   embedding=batch.summary, model_revision=encoder.revision, dimension=encoder.dimension,
                   source_sha256=original.source_manifest_sha256, ready_sha256=original.ready_manifest_sha256,
                   input_previews_unchanged=all(digest(inputs / r["image_path"]) == r["preview_sha256"] for r in ready),
                   packages={name: version(name) for name in ("torch", "transformers", "qdrant-client", "Pillow")},
                   manifests={name: digest(output / name) for name in ("text-index-manifest.json", "image-index-manifest.json")},
                   module_sha256=common["module_sha256"]))
        print(json.dumps({"status": "prepared", "output": str(output)}))
    finally:
        client.close()
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--qdrant-url", required=True)
    args = parser.parse_args()
    try:
        prepare(args.handoff, args.qdrant_url)
    except Exception as error:
        # Không in connection URL/SQL params/credentials khi chuẩn bị thất bại.
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}))
        raise SystemExit(1)
