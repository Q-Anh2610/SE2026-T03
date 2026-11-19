"""Kiểm raw pins cấu hình W6; không phải runner benchmark hoặc approval GitHub."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.search.frozen_retrieval_config import FrozenConfigError, load_frozen_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--config", type=Path, default=Path("evaluation/configs/issue114-w6-retrieval.frozen.json"))
    parser.add_argument("--expected-sha256", required=True, help="Hash của artifact được review; không tự suy từ file cần kiểm.")
    parser.add_argument("--local-inputs", action="store_true", help="Kiểm thêm local manifests/corpus/input bytes; không mở Qdrant hay weights.")
    args = parser.parse_args()
    path = args.config if args.config.is_absolute() else args.repo / args.config
    try:
        result = load_frozen_config(path, expected_sha256=args.expected_sha256,
                                    repo_root=args.repo, verify_local_inputs=args.local_inputs)
    except (FrozenConfigError, KeyError, TypeError, ValueError, OSError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error), "models_loaded": False,
                          "benchmark_executed": False, "test_authorized": False}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "frozen_config_verified", "config_version": result.config_version,
        "artifact_sha256": result.artifact_sha256, "mode": "clip_e5_rrf", "rrf": result.rrf_config.parameters(),
        "local_inputs_verified": result.local_inputs_verified, "models_loaded": False,
        "live_qdrant_verified": False, "benchmark_executed": False, "test_authorized": False,
        "next_gate": "reviewed commit/hash and Khue handoff; then existing service readiness"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
