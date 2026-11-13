"""Build index E5 local mới từ corpus #101 đã tiếp nhận; chỉ dùng cache offline."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True).stdout


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output đã tồn tại; cần thư mục mới, không ghi đè index.")
    if not 1 <= args.batch_size <= 200:
        parser.error("batch-size cần từ 1 đến 200.")

    from app.search.e5_index import (
        CORPUS_SHA256, RECIPE_VERSION, SOURCE_SHA256,
        audit_metadata_index, build_metadata_index, digest, json_bytes,
        load_metadata_corpus, read_member,
    )
    from app.embedding.e5_encoder import E5Encoder
    from qdrant_client import QdrantClient
    import torch

    # Dùng chính Git blob mà exporter #101 đã dùng, không đổi newline checkout.
    info = json.loads(read_member(args.corpus_root, "manifest.json"))
    source_commit = info.get("source_commit", "")
    if not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("Corpus source commit không hợp lệ.")
    source = git("show", f"{source_commit}:data/manifests/objaverse_200.json")
    corpus = load_metadata_corpus(
        args.corpus_root, source, expected_source_sha256=SOURCE_SHA256,
        expected_corpus_sha256=CORPUS_SHA256, expected_recipe_version=RECIPE_VERSION,
    )
    modules = (
        "backend/app/embedding/e5_encoder.py", "backend/app/search/e5_index.py",
        "backend/app/search/qdrant_store.py", "backend/app/search/index_manifest.py",
        "backend/app/schemas/text_search.py", "scripts/build_e5_metadata_index.py",
    )
    provenance = {
        "code_commit": git("rev-parse", "HEAD").decode().strip(),
        "working_tree_dirty": bool(git("status", "--porcelain").strip()),
        "module_sha256": {name: digest((ROOT / name).read_bytes()) for name in modules},
        "package_versions": {name: version(name) for name in (
            "torch", "transformers", "tokenizers", "safetensors", "qdrant-client", "pydantic",
        )},
    }
    started_at = datetime.now(timezone.utc).isoformat()
    start = perf_counter()
    print("Loading pinned E5 from local cache...", flush=True)
    encoder = E5Encoder(device=args.device, local_files_only=True)
    load_seconds = perf_counter() - start
    print("Encoding 200 passages, building new local index and auditing...", flush=True)
    start = perf_counter()
    manifest = build_metadata_index(encoder, corpus, args.output,
                                    batch_size=args.batch_size, **provenance)
    build_seconds = perf_counter() - start
    # Đóng/mở lại local storage để kiểm chứng persistence, không chỉ state trong RAM.
    with closing(QdrantClient(path=str(args.output / "qdrant"))) as client:
        reopened = audit_metadata_index(manifest, client, args.output)
    original = json.loads((args.output / "audit.json").read_bytes())
    if reopened != original:
        raise RuntimeError("Fingerprint index thay đổi sau đóng/mở lại.")
    report = {
        "schema_version": "issue91-e5-index-build-v1", "status": "passed",
        "scope": "200-passage index build and compatibility audit; not retrieval benchmark",
        "started_at_utc": started_at, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": platform.platform(),
        "device": str(encoder.device), "batch_size": args.batch_size,
        "torch_threads": torch.get_num_threads(), "torch_interop_threads": torch.get_num_interop_threads(),
        "load_seconds": load_seconds, "encode_build_audit_seconds": build_seconds,
        "corpus_sha256": manifest.corpus_sha256,
        "index_manifest_sha256": digest((args.output / "index-manifest.json").read_bytes()),
        "persistence_audit_sha256": digest((args.output / "persistence-audit.json").read_bytes()),
        "reopened_audit": reopened, "package_versions": provenance["package_versions"],
    }
    with (args.output / "build-report.json").open("xb") as stream:
        stream.write(json_bytes(report, pretty=True))
    print(json.dumps({"status": "passed", "asset_count": 200,
                      "collection": manifest.collection, "vector_name": manifest.vector_name,
                      "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
