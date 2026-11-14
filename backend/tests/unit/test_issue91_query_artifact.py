"""Erratum #91: chỉ kiểm byte/hash/provenance, không search hoặc tune test."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from scripts import verify_issue91_query_artifact as verify

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def bundle():
    record = json.loads((ROOT / verify.RECORD).read_text(encoding="utf-8-sig"))
    manifest = yaml.safe_load((ROOT / "data/benchmark/manifest.yaml").read_text(encoding="utf-8-sig"))
    config = json.loads((ROOT / record["runner"]["pending_config"]).read_text(encoding="utf-8-sig"))
    hashes = {path: verify.digest((ROOT / path).read_bytes()) for path in {verify.QUERY, *verify.PRESERVED}}
    return record, manifest, config, hashes


def test_exact_artifact_bytes_and_all_groups_match_the_record(bundle):
    record, _, _, _ = bundle
    raw = (ROOT / verify.QUERY).read_bytes()
    assert verify.inspect_query_bytes(raw, record["source"]) == record["structural_invariants"]
    assert len(raw) == 7851 and raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw
    assert raw.endswith(b"\n" * 4) and not raw.endswith(b"\n" * 5)
    assert verify.digest(raw) == "e202a0dc62406826ec29a2946d489c359a222133e6c530a9954832760d965470"
    assert record["source"]["commit"] == "ff7b64abbbb21677fc2fc6f6ac7daf6f2025742a"
    assert record["previous_lock"]["artifact_reproduced"] is False
    assert record["previous_lock"]["historical_run_raw_byte_provenance_confirmed"] is False


@pytest.mark.parametrize("change", ["strip_bom", "crlf", "trim_blank_lines", "remove_lf", "add_lf", "edit_byte"])
def test_raw_byte_drift_is_rejected_without_normalization(bundle, change):
    record, _, _, _ = bundle
    raw = (ROOT / verify.QUERY).read_bytes()
    if change == "strip_bom": raw = raw[3:]
    elif change == "crlf": raw = raw.replace(b"\n", b"\r\n")
    elif change == "trim_blank_lines": raw = raw.rstrip(b"\n") + b"\n"
    elif change == "remove_lf": raw = raw[:-1]
    elif change == "add_lf": raw += b"\n"
    else: raw = raw[:32] + bytes([raw[32] ^ 1]) + raw[33:]
    with pytest.raises(ValueError): verify.inspect_query_bytes(raw, record["source"])


def test_active_locks_agree_and_qrels_snapshot_pins_are_preserved(bundle):
    record, manifest, config, hashes = bundle
    verify.verify_active_locks(manifest, config, record, hashes)
    assert hashes["data/benchmark/qrels.csv"] == "cc1d42f6e3f41f92fab1b842c7a70ca68be4341cdd30e4262e13989f99019df5"
    assert hashes["data/manifests/objaverse_200.json"] == "9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd"


@pytest.mark.parametrize("change", ["locked_revision", "locked_query", "file_query", "config_query", "confirmed",
    "byte_policy", "qrels", "snapshot", "candidate_count", "query_raw", "label_raw", "record_link", "split_seed", "split_groups", "diagnostic_metadata"])
def test_inconsistent_locks_or_premature_confirmation_are_rejected(bundle, change):
    record, manifest, config, hashes = deepcopy(bundle)
    old = record["previous_lock"]["queries_sha256"]
    if change == "locked_revision": manifest["locked_revision"] = manifest["locked_revision"].replace(record["source"]["sha256"], old)
    elif change == "locked_query": manifest["locked_files_sha256"]["queries.csv"] = old
    elif change == "file_query": manifest["file_sha256"]["queries.csv"] = old
    elif change == "config_query": config["expected_sha256"]["queries.csv"] = old
    elif change == "confirmed": config["input_confirmation"]["status"] = "confirmed"
    elif change == "byte_policy": config["input_confirmation"]["queries_byte_policy"] = {"bom": True, "newline": "LF", "final_newline": True}
    elif change == "qrels": manifest["locked_files_sha256"]["qrels.csv"] = "0" * 64
    elif change == "snapshot": manifest["snapshot_manifest_sha256"] = "0" * 64
    elif change == "candidate_count": manifest["candidate_asset_count"] = 199
    elif change == "query_raw": hashes[verify.QUERY] = "0" * 64
    elif change == "label_raw": hashes["data/benchmark/labels_khue.csv"] = "0" * 64
    elif change == "split_seed": manifest["split_seed"] = 43
    elif change == "split_groups": manifest["validation_group_ids"] = ["changed"]
    elif change == "diagnostic_metadata": manifest["diagnostic_keyword_run"]["result_sha256"] = "0" * 64
    else: manifest["query_artifact_erratum"]["record_file"] = "wrong.json"
    with pytest.raises(ValueError): verify.verify_active_locks(manifest, config, record, hashes)


def test_shallow_safe_tree_verification_preserves_history_and_checkout_hashes():
    report = verify.verify_tree(ROOT)
    assert report["status"] == "passed" and report["benchmark_run"] is False
    assert report["source_commit_bytes_compared"] is False  # CI needs HEAD only, not old objects.
    assert report["head_query_blob_unchanged"] is True and report["historical_worktree_content_unchanged"] is True
    assert report["runner_confirmation"] == "pending"
    assert report["checkout_raw_sha256_by_autocrlf"]["true"] == report["checkout_raw_sha256_by_autocrlf"]["false"]
    assert report["structure"]["validation_count"] == 28 and report["structure"]["test_count"] == 42


def test_changed_historical_blob_pin_is_detected(bundle):
    record, _, _, _ = deepcopy(bundle)
    record["historical_files_git_blob_sha256"][sorted(verify.HISTORICAL)[0]] = "0" * 64
    with pytest.raises(ValueError, match="Git blob đổi"):
        verify.verify_preserved_files(ROOT, record)


def test_uncommitted_changes_in_preserved_files_are_detected(bundle, monkeypatch):
    record, _, _, _ = bundle
    original = verify.git
    def changed(root, *args):
        if args[0] == "hash-object": return b"0" * 40 + b"\n"
        return original(root, *args)
    monkeypatch.setattr(verify, "git", changed)
    with pytest.raises(ValueError, match="working content đổi"):
        verify.verify_preserved_files(ROOT, record)


def test_wrong_eol_policy_is_detected_before_simulated_checkout(bundle):
    record, _, _, _ = deepcopy(bundle)
    record["checkout_eol"][verify.QUERY] = "crlf"
    with pytest.raises(ValueError, match="EOL rule sai"):
        verify.verify_checkout(ROOT, record)


def test_default_runner_is_still_blocked_before_models_load():
    result = subprocess.run([sys.executable, "-B", "scripts/run_e5_rrf_validation.py", "--preflight-only"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 2
    assert json.loads(result.stdout) == {"status": "blocked", "reason": "canonical_query_artifact_not_confirmed", "models_loaded": False}
