"""CLI validation #91; chỉ chạy sau xác nhận canonical inputs, models offline."""

import argparse
from contextlib import ExitStack, closing, contextmanager
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from evaluation.e5_rrf_validation import (
    InputsNotConfirmed, ValidationRunFailed, load_inputs, run_validation, sha,
)


def runtime_context(args):
    modules = (
        "evaluation/e5_rrf_validation.py", "evaluation/run_keyword_baseline.py",
        "scripts/run_e5_rrf_validation.py", "scripts/smoke_e5_rrf_service.py",
        "backend/app/search/experimental_text_search.py", "backend/app/search/vector_search.py",
        "backend/app/search/text_search.py", "backend/app/search/rrf.py",
        "backend/app/search/filters.py", "backend/app/search/e5_index.py",
        "backend/app/search/smoke.py", "backend/app/embedding/e5_encoder.py",
        "backend/app/embedding/clip_encoder.py",
    )
    return {"python": platform.python_version(), "platform": platform.platform(),
        "machine": platform.machine(), "processor": platform.processor(), "device": args.device,
        "command": ["scripts/run_e5_rrf_validation.py", *sys.argv[1:]],
        "code_commit": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "working_tree_dirty": bool(subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip()),
        "module_sha256": {name: sha((ROOT / name).read_bytes()) for name in modules},
        "package_versions": {name: version(name) for name in ("torch", "transformers", "qdrant-client", "numpy", "pydantic")}}


def real_service_factory(args, context):
    @contextmanager
    def factory(output):
        import torch
        from app.embedding.clip_encoder import CLIPEncoder
        from app.embedding.e5_encoder import E5Encoder
        from app.search.experimental_text_search import CLIPTextSource, E5MetadataSearchService, ExperimentalFusionService
        from app.search.smoke import audit_index
        from app.search.e5_index import audit_metadata_index
        from scripts.smoke_e5_rrf_service import open_existing_index

        started = perf_counter()
        clip_encoder = CLIPEncoder(device=args.device, local_files_only=True)
        e5_encoder = E5Encoder(device=args.device, local_files_only=True)
        context["model_load_seconds"] = perf_counter() - started
        context["torch_threads"] = torch.get_num_threads()
        context["torch_interop_threads"] = torch.get_num_interop_threads()
        with ExitStack() as stack:
            clip_client = stack.enter_context(closing(open_existing_index(args.clip_index_root)))
            e5_client = stack.enter_context(closing(open_existing_index(args.e5_index_root)))
            clip = CLIPTextSource(clip_encoder, clip_client, args.clip_index_root,
                input_root=args.clip_input_root, manifest_ref="clip-index-manifest.json")
            e5 = E5MetadataSearchService(e5_encoder, e5_client, args.e5_index_root,
                manifest_ref="e5-index-manifest.json")
            fusion = ExperimentalFusionService(clip, e5)
            context["persisted_before"] = {"clip": clip.baseline, "e5": e5.baseline}
            for name, root in (("clip-index-manifest.json", args.clip_index_root),
                               ("e5-index-manifest.json", args.e5_index_root)):
                with (output / name).open("xb") as stream:
                    stream.write((root / "index-manifest.json").read_bytes())
            yield fusion
            clip.assert_ready(); e5.assert_ready()
            context["ram_after_queries"] = {"clip": clip.current_audit, "e5": e5.current_audit}
        # Separate clients inspect persisted values after all timed calls.
        with ExitStack() as reopened:
            clip_disk = reopened.enter_context(closing(open_existing_index(args.clip_index_root)))
            e5_disk = reopened.enter_context(closing(open_existing_index(args.e5_index_root)))
            after = {"clip": audit_index(clip.manifest.make_store(clip_disk), clip.metadata),
                     "e5": audit_metadata_index(e5.manifest, e5_disk, args.e5_index_root)}
        context["persisted_after_reopen"] = after
        context["persisted_fingerprints_unchanged"] = after == context["persisted_before"]
        if not context["persisted_fingerprints_unchanged"]:
            raise ValueError("Persisted index thay đổi trong validation.")
    return factory


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "evaluation/configs/issue91-e5-rrf-validation.pending.json")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--rrf-k", type=int, choices=(10, 20, 60))
    parser.add_argument("--clip-index-root", type=Path)
    parser.add_argument("--clip-input-root", type=Path)
    parser.add_argument("--e5-index-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args(argv)
    try:
        inputs = load_inputs(args.config, ROOT)
    except InputsNotConfirmed as error:
        print(json.dumps({"status": "blocked", "reason": str(error), "models_loaded": False}))
        return 2
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "blocked", "reason": "input_preflight_failed",
                          "error_type": type(error).__name__, "detail": str(error), "models_loaded": False}))
        return 2
    if args.preflight_only:
        print(json.dumps({"status": "inputs_verified", "input_sha256": inputs.hashes,
                          "validation_queries": len(inputs.queries), "models_loaded": False}))
        return 0
    if args.rrf_k is None or any(getattr(args, name) is None for name in
            ("clip_index_root", "clip_input_root", "e5_index_root", "output")):
        parser.error("Sau preflight cần --rrf-k, cả ba index/input roots và --output mới.")
    if args.output.exists():
        parser.error("Output đã tồn tại; chọn thư mục mới.")
    context = runtime_context(args)
    try:
        report = run_validation(inputs, real_service_factory(args, context), args.output,
            rank_constant=args.rrf_k, execution_kind="real_model_cache", context=context)
    except ValidationRunFailed:
        print(json.dumps({"status": "failed", "output": str(args.output), "report": "run.json"}))
        return 1
    print(json.dumps({"status": report["status"], "output": str(args.output),
        "measured_samples_per_configuration": {key: value["completed_samples"]
                                               for key, value in report["configurations"].items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
