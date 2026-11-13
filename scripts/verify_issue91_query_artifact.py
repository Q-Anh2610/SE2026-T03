"""Kiểm raw artifact/erratum #91 và bảo toàn lịch sử; không chạy retrieval."""

import argparse
from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
RECORD = "data/benchmark/query-artifact-erratum-91.json"
QUERY = "data/benchmark/queries.csv"
PRESERVED = {
    "data/benchmark/qrels.csv", "data/benchmark/labels_khue.csv",
    "data/benchmark/labels_huyen.csv", "data/benchmark/candidate_assets.csv",
    "data/manifests/objaverse_200.json",
}
HISTORICAL = {
    "evaluation/results/home-interior-text-v2-keyword-baseline.json",
    "evaluation/results/home-interior-clear-200-v3-clip-baseline.json",
    "docs/evaluation/home-interior-text-v2-keyword-baseline.md",
    "docs/evaluation/home-interior-clear-200-v3-clip-baseline.md",
    "evaluation/configs/home-interior-text-v2-keyword.json",
    "evaluation/run_issue71_clip.py", "evaluation/run_keyword_baseline.py",
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def manifest_projection_sha256(manifest):
    """Bind every manifest value except the explicitly amended lock fields."""
    value = deepcopy(manifest)
    for key in ("locked_revision", "updated_at_utc", "query_artifact_erratum"):
        value.pop(key, None)
    value["locked_files_sha256"].pop("queries.csv")
    value["file_sha256"].pop("queries.csv")
    # PyYAML represents unchanged UTC timestamps as datetime/date objects.
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                     default=lambda stamp: stamp.isoformat()).encode("utf-8")
    return digest(raw)


def inspect_query_bytes(raw, artifact):
    """Hash nguyên bytes trước parse; không bỏ BOM/newline hoặc serialize lại."""
    require(len(raw) == artifact["byte_count"], "Query byte count khác artifact.")
    require(digest(raw) == artifact["sha256"], "Query raw SHA-256 khác artifact.")
    require(artifact["encoding"] == "UTF-8" and artifact["bom_hex"] == "efbbbf"
            and raw.startswith(bytes.fromhex(artifact["bom_hex"])), "Query cần nguyên UTF-8 BOM.")
    require(artifact["newline"] == "LF" and artifact["contains_cr"] is False and b"\r" not in raw,
            "Query cần LF, không có CR.")
    tail = len(raw) - len(raw.rstrip(b"\n"))
    require(tail == artifact["trailing_lf_count"], "Query trailing LF khác artifact.")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
    ids = [r["query_id"] for r in rows]
    require(len(rows) == len(set(ids)) == 70, "Query cần 70 IDs duy nhất.")
    require(all(r["split"] in ("validation", "test") for r in rows), "Query split không hợp lệ.")
    groups = {split: {r["query_group_id"] for r in rows if r["split"] == split}
              for split in ("validation", "test")}
    return {"query_count": len(rows), "validation_count": sum(r["split"] == "validation" for r in rows),
            "test_count": sum(r["split"] == "test" for r in rows),
            "query_group_count": len(groups["validation"] | groups["test"]),
            "validation_group_count": len(groups["validation"]), "test_group_count": len(groups["test"]),
            "groups_overlap": bool(groups["validation"] & groups["test"])}


def verify_active_locks(manifest, config, record, raw_hashes):
    expected = {"queries.csv": record["source"]["sha256"],
                "qrels.csv": record["preserved_input_artifacts_raw_sha256"]["data/benchmark/qrels.csv"],
                "candidate_metadata": record["preserved_input_artifacts_raw_sha256"]["data/manifests/objaverse_200.json"]}
    require(manifest["benchmark_version"] == "home-interior-text-v2", "Benchmark version đổi.")
    require(manifest["locked_files_sha256"] == {k: expected[k] for k in ("queries.csv", "qrels.csv")},
            "Manifest locked_files_sha256 chưa nhất quán.")
    require(manifest["locked_revision"] == f"sha256-bundle:queries.csv={expected['queries.csv']};qrels.csv={expected['qrels.csv']}",
            "Manifest locked_revision chưa nhất quán.")
    require(manifest["file_sha256"]["queries.csv"] == expected["queries.csv"], "Manifest file_sha256 query chưa nhất quán.")
    require(manifest["file_sha256"]["qrels.csv"] == expected["qrels.csv"], "Manifest file_sha256 qrels đổi.")
    require(manifest["snapshot_name"] == "home-interior-clear-200-v3"
            and manifest["candidate_asset_count"] == 200
            and manifest["snapshot_manifest_sha256"] == expected["candidate_metadata"], "Snapshot/candidate đổi.")
    require(config["expected_sha256"] == expected, "Pending config pins chưa nhất quán.")
    require(config["input_confirmation"] == {"status": "pending", "evidence_url": None, "queries_byte_policy": None},
            "Erratum chưa được review/merge: giữ config pending, không tạo confirmed.")
    for path, actual in raw_hashes.items():
        if path == QUERY:
            require(actual == expected["queries.csv"], "Query raw hash sai.")
        else:
            require(actual == record["preserved_input_artifacts_raw_sha256"][path], f"Input raw bytes đổi: {path}")
    for path in PRESERVED - {"data/manifests/objaverse_200.json"}:
        require(manifest["file_sha256"][Path(path).name] == raw_hashes[path], f"Manifest file_sha256 sai: {path}")
    require(manifest["query_artifact_erratum"]["record_file"] == RECORD
            and manifest["query_artifact_erratum"]["proposal_evidence"] == record["proposal_evidence"]
            and manifest["query_artifact_erratum"]["confirmation_gate"] == "review-and-merge-before-confirmed",
            "Manifest chưa liên kết đúng erratum/gate.")
    require(manifest_projection_sha256(manifest) == record["preserved_manifest_projection_sha256"],
            "Manifest ngoài các trường đính chính đã đổi (split/groups/history/provenance).")


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if result.returncode != 0:
        raise ValueError("Git read-only verification failed; cần clone/object tương ứng.")
    return result.stdout


def verify_preserved_files(root, record):
    """Giữ Git blob lịch sử; worktree so bằng đúng clean filter của từng path.

    Quy tắc Git này chỉ dùng so lịch sử, không dùng tính hash artifact query.
    Không dùng hash-object -w, không thay index hoặc cấu hình Git.
    """
    for field, names in (("preserved_inputs_git_blob_sha256", PRESERVED),
                         ("historical_files_git_blob_sha256", HISTORICAL)):
        pins = record[field]
        require(set(pins) == names, "Danh sách file cần bảo toàn đổi.")
        for name in sorted(names):
            raw = git(root, "show", f"HEAD:{name}")
            require(digest(raw) == pins[name], f"Historical/source Git blob đổi: {name}")
            oid = git(root, "rev-parse", f"HEAD:{name}").strip()
            working_oid = git(root, "hash-object", f"--path={name}", str(root / name)).strip()
            require(working_oid == oid, f"Historical/source working content đổi: {name}")


def verify_checkout(root, record):
    expected = record["checkout_eol"]
    require(set(expected) == {QUERY, *[p for p in PRESERVED if p.endswith(".csv")]}, "Checkout paths đổi.")
    attrs = git(root, "check-attr", "-z", "text", "eol", "--", *sorted(expected)).rstrip(b"\0").split(b"\0")
    actual = {(attrs[i].decode(), attrs[i+1].decode()): attrs[i+2].decode() for i in range(0, len(attrs), 3)}
    for name, eol in expected.items():
        require(actual[(name, "text")] == "set" and actual[(name, "eol")] == eol, f"Git EOL rule sai: {name}")
    # cat-file --filters simulates checkout without changing files/config/index.
    simulations = {}
    for mode in ("false", "true"):
        hashes = {name: digest(git(root, "-c", f"core.autocrlf={mode}", "cat-file", "--filters", f"HEAD:{name}"))
                  for name in sorted(expected)}
        for name, hashed in hashes.items():
            wanted = record["source"]["sha256"] if name == QUERY else record["preserved_input_artifacts_raw_sha256"][name]
            require(hashed == wanted, f"Checkout raw bytes không tái lập: autocrlf={mode}, {name}")
        simulations[mode] = hashes
    return simulations


def verify_tree(root=ROOT, *, compare_source_commit=False):
    root = Path(root).resolve()
    record = json.loads((root / RECORD).read_text(encoding="utf-8-sig"))
    require(record["schema_version"] == "issue91-query-artifact-erratum-v1" and record["issue"] == 91,
            "Erratum schema không hợp lệ.")
    artifact = record["source"]
    require(artifact["path"] == QUERY and re.fullmatch(r"[0-9a-f]{40}", artifact["commit"]), "Artifact source không hợp lệ.")
    raw = (root / QUERY).read_bytes()
    structure = inspect_query_bytes(raw, artifact)
    require(structure == record["structural_invariants"], "IDs/groups/split counts khác source lock.")
    require(git(root, "show", f"HEAD:{QUERY}") == raw, "Query working bytes khác Git blob; không serialize lại CSV.")
    if compare_source_commit:
        require(git(root, "show", f"{artifact['commit']}:{QUERY}") == raw, "Query không giống nguyên blob source commit.")
    manifest = yaml.safe_load((root / "data/benchmark/manifest.yaml").read_text(encoding="utf-8-sig"))
    config = json.loads((root / record["runner"]["pending_config"]).read_text(encoding="utf-8-sig"))
    raw_hashes = {name: digest((root / name).read_bytes()) for name in {QUERY, *PRESERVED}}
    verify_active_locks(manifest, config, record, raw_hashes)
    verify_preserved_files(root, record)
    checkout = verify_checkout(root, record)
    return {"status": "passed", "benchmark_run": False, "runner_confirmation": "pending",
        "record": RECORD, "query_sha256": artifact["sha256"], "query_byte_count": len(raw),
        "query_bom": True, "query_newline": "LF", "query_trailing_lf_count": artifact["trailing_lf_count"],
        "source_commit": artifact["commit"], "source_commit_bytes_compared": compare_source_commit,
        "head_query_blob_unchanged": True, "structure": structure, "raw_input_sha256": raw_hashes,
        "preserved_git_blob_sha256": record["preserved_inputs_git_blob_sha256"],
        "historical_git_blob_sha256": record["historical_files_git_blob_sha256"],
        "historical_worktree_content_unchanged": True, "checkout_raw_sha256_by_autocrlf": checkout}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--compare-source-commit", action="store_true",
                        help="Cần object ff7b64a trong clone; CI shallow có thể bỏ cờ này.")
    args = parser.parse_args(argv)
    try:
        report = verify_tree(args.repo, compare_source_commit=args.compare_source_commit)
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "failed", "reason": str(error), "benchmark_run": False}))
        return 1
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
