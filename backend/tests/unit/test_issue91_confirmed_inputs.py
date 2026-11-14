"""Provenance fixtures only: no benchmark/model/index access."""

from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from evaluation import e5_rrf_validation as runner
from scripts import run_e5_rrf_validation as cli
from test_e5_rrf_validation import Dataset, factory_for, services


@pytest.fixture
def confirmed(tmp_path):
    data = Dataset(tmp_path / "fixture-inputs")
    raw = data.paths["queries"].read_bytes()
    data.record = {
        "schema_version": "issue91-query-artifact-erratum-v1", "issue": 91,
        "source": {"commit": "a" * 40, "path": data.config["paths"]["queries"],
            "sha256": runner.sha(raw), "byte_count": len(raw), "encoding": "UTF-8",
            "bom_hex": "", "newline": "LF", "contains_cr": False,
            "trailing_lf_count": 1},
    }
    data.record_path = data.root / "fixture-erratum.json"
    data.config["schema_version"] = "issue91-validation-config-v2"
    # Fictional evidence is only used inside fixture runs, never real configs.
    url = "https://github.com/Q-Anh2610/SE2026-T03/pull/1"
    data.config["input_confirmation"]["evidence_url"] = url
    data.config["artifact_provenance"] = {
        "source_commit": "a" * 40, "source_path": data.config["paths"]["queries"],
        "erratum_pr_url": url, "erratum_head_commit": "b" * 40,
        "erratum_merge_commit": "c" * 40, "record_path": "fixture-erratum.json",
        "record_sha256": "0" * 64,
    }
    save_record(data)
    return data


def save_record(data):
    data.record_path.write_bytes(runner.encoded(data.record))
    data.config["artifact_provenance"]["record_sha256"] = runner.sha(data.record_path.read_bytes())
    data.save_config()


def test_v2_preflight_verifies_record_without_constructing_model(confirmed, monkeypatch, capsys):
    monkeypatch.setattr(cli, "ROOT", confirmed.root)
    factory = Mock(side_effect=AssertionError("must not load weights"))
    monkeypatch.setattr(cli, "real_service_factory", factory)
    assert cli.main(["--config", str(confirmed.config_path), "--preflight-only"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "inputs_verified" and report["models_loaded"] is False
    assert report["input_sha256"]["artifact_record"] == runner.sha(confirmed.record_path.read_bytes())
    assert len(confirmed.load().queries) == 28
    factory.assert_not_called()


@pytest.mark.parametrize("change", [
    "missing_commit", "zero_commit", "short_commit", "source_path", "record_path_escape",
    "record_path_absolute", "record_path_backslash", "bad_digest", "wrong_digest",
    "wrong_pr", "evidence_mismatch", "unknown_field", "missing_provenance", "wrong_schema",
])
def test_malformed_v2_provenance_rejected_before_csv_parse(confirmed, monkeypatch, change):
    provenance = confirmed.config["artifact_provenance"]
    if change == "missing_commit": provenance.pop("erratum_merge_commit")
    elif change == "zero_commit": provenance["erratum_merge_commit"] = "0" * 40
    elif change == "short_commit": provenance["source_commit"] = "aaaaaaa"
    elif change == "source_path": provenance["source_path"] = "other.csv"
    elif change == "record_path_escape": provenance["record_path"] = "../fixture-erratum.json"
    elif change == "record_path_absolute": provenance["record_path"] = confirmed.record_path.as_posix()
    elif change == "record_path_backslash": provenance["record_path"] = "data\\fixture.json"
    elif change == "bad_digest": provenance["record_sha256"] = "wrong"
    elif change == "wrong_digest": provenance["record_sha256"] = "0" * 64
    elif change == "wrong_pr": provenance["erratum_pr_url"] = "https://example.com/pull/1"
    elif change == "evidence_mismatch": provenance["erratum_pr_url"] += "0"
    elif change == "unknown_field": provenance["extra"] = True
    elif change == "missing_provenance": confirmed.config.pop("artifact_provenance")
    else: confirmed.config["schema_version"] = "issue91-validation-config-v3"
    confirmed.save_config()
    monkeypatch.setattr(runner, "_csv", Mock(side_effect=AssertionError("must not parse")))
    with pytest.raises(ValueError): confirmed.load()


@pytest.mark.parametrize("field,value", [
    ("commit", "d" * 40), ("sha256", "e" * 64), ("byte_count", 1),
    ("bom_hex", "efbbbf"), ("newline", "CRLF"), ("trailing_lf_count", 4),
    ("contains_cr", True), ("path", "different.csv"), ("encoding", "ASCII"),
])
def test_record_must_bind_exact_source_commit_and_bytes(confirmed, field, value):
    confirmed.record["source"][field] = value
    save_record(confirmed)  # Valid record hash alone cannot bypass byte/provenance checks.
    with pytest.raises(ValueError, match="source commit/bytes"): confirmed.load()


def test_pending_v2_still_blocks_before_record_or_csv_reads(confirmed):
    confirmed.config["input_confirmation"].update(status="pending", evidence_url=None, queries_byte_policy=None)
    confirmed.save_config()
    confirmed.record_path.unlink()
    confirmed.paths["queries"].unlink()
    with pytest.raises(runner.InputsNotConfirmed): confirmed.load()


@pytest.mark.parametrize("change_during_run", [False, True])
def test_v2_run_exports_provenance_and_checks_record_after_run(confirmed, tmp_path, change_during_run):
    inputs = confirmed.load()
    output = tmp_path / "fixture-output"
    original = confirmed.record_path.read_bytes()
    def after():
        if change_during_run: confirmed.record_path.write_bytes(original + b"\n")
    if change_during_run:
        with pytest.raises(runner.ValidationRunFailed):
            runner.run_validation(inputs, factory_for(services(inputs), after=after), output, rank_constant=10)
    else:
        runner.run_validation(inputs, factory_for(services(inputs), after=after), output, rank_constant=10)
    report = json.loads((output / "run.json").read_bytes())
    assert report["artifact_provenance"] == confirmed.config["artifact_provenance"]
    assert (output / "query-artifact-erratum.json").read_bytes() == original
    assert report["files_sha256"]["query-artifact-erratum.json"] == runner.sha(original)
    assert report["benchmark"] is False
    assert report["status"] == ("failed" if change_during_run else "passed")
    if change_during_run:
        assert report["errors"][0]["phase"] == "input_integrity_after_run"


def test_v2_record_change_between_preflight_and_setup_is_rejected(confirmed, tmp_path):
    inputs = confirmed.load()
    confirmed.record_path.write_bytes(confirmed.record_path.read_bytes() + b"\n")
    factory = Mock(side_effect=AssertionError("must not load models"))
    output = tmp_path / "changed-before-setup"
    with pytest.raises(runner.ValidationRunFailed):
        runner.run_validation(inputs, factory, output, rank_constant=60)
    report = json.loads((output / "run.json").read_bytes())
    assert report["status"] == "failed" and report["errors"][0]["phase"] == "setup"
    factory.assert_not_called()
