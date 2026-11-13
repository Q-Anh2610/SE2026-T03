"""Smoke E5 #91 bằng weights có sẵn; không tải model, không dùng benchmark."""

from datetime import datetime, timezone
from importlib.metadata import version
import argparse
import json
import math
import os
from pathlib import Path
import platform
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

def main() -> int:
    # Console Windows có thể dùng cp1252 khi stdout/stderr được pipe.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output đã tồn tại; chọn file mới để giữ bằng chứng.")

    # --help không cần import torch/transformers hoặc mở model cache.
    from app.embedding.e5_encoder import (
        E5Encoder, MODEL_ID, MODEL_REVISION, PREPROCESSING_VERSION,
    )

    started_at = datetime.now(timezone.utc).isoformat()
    start = perf_counter()
    encoder = E5Encoder(device=args.device, local_files_only=True)
    load_seconds = perf_counter() - start
    # Dữ liệu tự tạo chỉ kiểm tra kỹ thuật, không đánh giá chất lượng tiếng Việt.
    queries = ["wooden chair", "ghế gỗ"]
    passages = ["A wooden chair with four legs.", "A rectangular dining table."]
    encoder.encode_text(queries[0])
    encoder.encode_passages(passages)
    start = perf_counter()
    first = [encoder.encode_text(query) for query in queries]
    encoded_passages = encoder.encode_passages(passages, batch_size=2)
    second = [encoder.encode_text(query) for query in queries]
    elapsed_seconds = perf_counter() - start
    for vector in first + second + encoded_passages:
        if (len(vector) != 384 or not all(math.isfinite(value) for value in vector)
                or not math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, abs_tol=1e-5)):
            raise RuntimeError("E5 smoke nhận vector không hợp lệ.")
    repeat_max_abs_difference = max(
        abs(a - b) for left, right in zip(first, second, strict=True)
        for a, b in zip(left, right, strict=True))
    if repeat_max_abs_difference > 1e-12:
        raise RuntimeError("E5 repeat vượt tolerance 1e-12; cần kiểm tra môi trường.")
    result = {
        "schema_version": "issue91-e5-encoder-smoke-v1",
        "status": "passed", "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "synthetic encoder diagnostic; not a relevance benchmark or index smoke",
        "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
        "tokenizer_revision": encoder.tokenizer_revision,
        "preprocessing_version": PREPROCESSING_VERSION,
        "dimension": encoder.dimension, "max_text_tokens": encoder.max_text_tokens,
        "local_files_only": True, "device": str(encoder.device),
        "queries": queries, "passages": passages,
        "query_prefix": "query: ", "passage_prefix": "passage: ",
        "normalization": "L2", "pooling": "attention-mask mean in float32",
        "load_seconds": load_seconds,
        "warmup": {"query_calls": 1, "passage_calls": 1},
        "timed_operations": {"query_calls": 4, "passages": 2, "total_seconds": elapsed_seconds},
        "repeat_max_abs_difference": repeat_max_abs_difference,
        "repeat_tolerance": 1e-12,
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "machine": platform.machine(), "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "packages": {name: version(name) for name in (
                "torch", "transformers", "tokenizers", "safetensors")},
        },
        "command": [sys.executable, *sys.argv],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": "passed", "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
