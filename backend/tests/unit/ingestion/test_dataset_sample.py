"""Sample exporter tests: synthetic metadata, real validator, no Git/network/DB."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from unittest import result

import pytest


REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / "scripts/prepare_dataset_sample.py"
SPEC = importlib.util.spec_from_file_location("dataset_sample_142", SCRIPT)
sample = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sample)
COMMIT = "1" * 40
FILES = {"assets.json", "attribution.json", "provenance.json", "CHECKSUMS.sha256"}


@pytest.fixture
def source_fixture(tmp_path, monkeypatch):
    records = [{
        "asset_id": f"fixture_{number:03d}",
        "source": "fixture",
        "source_id": str(number),
        "source_url": f"https://example.com/assets/{number}",
        "name": f"  Ghế {number}  ",
        "description": None,
        "author": "Fixture author",
        "license": "by-nc" if number == 0 else "by",
        "tags": [" wood ", "wood", "wood"],
        "formats": None,
        "fixture_extra": {"preserve": True},
    } for number in reversed(range(200))]
    calls = []
    monkeypatch.setattr(sys, "path", sys.path.copy())

    def setup(rows=None, checkout=None, wrong_hash=False):
        selected = copy.deepcopy(records if rows is None else rows)
        raw = json.dumps(selected, ensure_ascii=False).encode("utf-8")
        source = tmp_path / sample.SOURCE_PATH
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(json.dumps(
            selected if checkout is None else checkout,
            ensure_ascii=False,
        ).encode("utf-8"))
        expected = "0" * 64 if wrong_hash else hashlib.sha256(raw).hexdigest()
        # Synthetic source pin applies only within this test fixture.
        monkeypatch.setattr(sample, "SOURCE_HASH", expected)

        def fake_git(repo, *args):
            calls.append(args)
            if args == ("rev-parse", "--verify", "--end-of-options", "fixture-ref^{commit}"):
                return (COMMIT + "\n").encode("ascii")
            if args == ("show", f"{COMMIT}:{sample.SOURCE_PATH}"):
                return raw
            raise AssertionError(f"Unexpected Git operation: {args}")

        monkeypatch.setattr(sample, "git", fake_git)
        return tmp_path, selected, raw, source

    return records, setup, calls


def export(repo, output, count=5):
    return sample.prepare_sample(repo, output, count, "fixture-ref")


def test_export_preserves_source_metadata_and_records_provenance(source_fixture):
    _, setup, calls = source_fixture
    repo, records, raw, source = setup()
    original = source.read_bytes()
    output = repo / "output"
    result = export(repo, output)

    assert {p.name for p in output.iterdir()} == FILES
    assets_raw = (output / "assets.json").read_bytes()
    assets = json.loads(assets_raw)
    assert assets == sorted(records, key=lambda row: row["asset_id"])[:5]
    assert assets[0]["name"] == "  Ghế 0  "
    assert assets[0]["tags"] == [" wood ", "wood", "wood"]
    assert assets[0]["formats"] is None
    assert assets[0]["fixture_extra"] == {"preserve": True}

    provenance = json.loads((output / "provenance.json").read_bytes())
    assert provenance["source_commit"] == COMMIT
    assert provenance["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert provenance["source_count"] == 200
    assert provenance["asset_count"] == 5
    assert provenance["asset_ids"] == [row["asset_id"] for row in assets]
    assert provenance["sample_sha256"] == hashlib.sha256(assets_raw).hexdigest()
    assert provenance["attribution_sha256"] == hashlib.sha256(
        (output / "attribution.json").read_bytes()
    ).hexdigest()
    assert provenance["generator_sha256"] == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    assert provenance["status"] == "sample_selection_confirmed"
    assert provenance["previews"] == "not_downloaded_or_verified"
    assert provenance["database"] == "not_written"
    assert provenance["index"] == "not_built"
    assert result["previews_verified"] is False
    assert result["sample_sha256"] == provenance["sample_sha256"]
    assert result["status"] == "offline_sample_generated"
    assert result["sample_selection_status"] == "sample_selection_confirmed"
    assert source.read_bytes() == original
    assert len(calls) == 2

    for name in FILES:
        content = (output / name).read_bytes()
        assert not content.startswith(b"\xef\xbb\xbf")
        assert b"\r" not in content
        assert content.endswith(b"\n")
        content.decode("utf-8")

    checked = set()
    for line in (output / "CHECKSUMS.sha256").read_text().splitlines():
        checksum, name = line.split("  ", 1)
        assert checksum == hashlib.sha256((output / name).read_bytes()).hexdigest()
        checked.add(name)
    assert checked == FILES - {"CHECKSUMS.sha256"}


def test_repeat_exports_match_all_bytes_and_leave_source_unchanged(source_fixture):
    _, setup, _ = source_fixture
    repo, _, _, source = setup()
    original = source.read_bytes()
    export(repo, repo / "run1")
    export(repo, repo / "run2")
    for name in FILES:
        assert (repo / "run1" / name).read_bytes() == (repo / "run2" / name).read_bytes()
    assert source.read_bytes() == original


@pytest.mark.parametrize("author", [None, ""])
def test_attribution_reports_missing_author_and_keeps_license(source_fixture, author):
    records, setup, _ = source_fixture
    rows = copy.deepcopy(records)
    first = next(row for row in rows if row["asset_id"] == "fixture_000")
    first["author"] = author
    repo, _, _, _ = setup(rows=rows)
    export(repo, repo / "output")
    attribution = json.loads((repo / "output/attribution.json").read_bytes())
    assert attribution["records"][0]["author"] == author
    assert attribution["records"][0]["license"] == "by-nc"
    assert attribution["missing_fields"] == {"fixture_000": ["author"]}
    assert attribution["status"] == "source_metadata_only_not_distribution_clearance"


@pytest.mark.parametrize("count", [0, -1, True, 1.5, 201])
def test_invalid_count_fails_before_git_or_output(source_fixture, count):
    _, setup, calls = source_fixture
    repo, _, _, _ = setup()
    with pytest.raises(ValueError, match="count"):
        export(repo, repo / "output", count)
    assert calls == []
    assert not (repo / "output").exists()


def test_wrong_source_hash_is_rejected_before_output(source_fixture):
    _, setup, _ = source_fixture
    repo, _, _, _ = setup(wrong_hash=True)
    with pytest.raises(ValueError, match="SHA-256"):
        export(repo, repo / "output")
    assert not (repo / "output").exists()


def test_changed_checkout_is_rejected_before_output(source_fixture):
    records, setup, _ = source_fixture
    changed = copy.deepcopy(records)
    changed[0]["name"] = "Changed checkout"
    repo, _, _, _ = setup(checkout=changed)
    with pytest.raises(ValueError, match="checkout"):
        export(repo, repo / "output")
    assert not (repo / "output").exists()


@pytest.mark.parametrize("damage", ["count", "duplicate_id", "duplicate_source", "missing_license"])
def test_invalid_source_is_rejected_before_output(source_fixture, damage):
    records, setup, _ = source_fixture
    rows = copy.deepcopy(records)
    if damage == "count":
        rows.pop()
    elif damage == "duplicate_id":
        rows[1]["asset_id"] = rows[0]["asset_id"]
    elif damage == "duplicate_source":
        rows[1]["source_id"] = rows[0]["source_id"]
    else:
        rows[0].pop("license")
    repo, _, _, _ = setup(rows=rows)
    with pytest.raises(ValueError):
        export(repo, repo / "output")
    assert not (repo / "output").exists()


def test_existing_output_is_refused_without_changing_files(source_fixture):
    _, setup, _ = source_fixture
    repo, _, _, source = setup()
    export(repo, repo / "output")
    before = {p.name: p.read_bytes() for p in (repo / "output").iterdir()}
    source_before = source.read_bytes()
    with pytest.raises(FileExistsError):
        export(repo, repo / "output")
    assert {p.name: p.read_bytes() for p in (repo / "output").iterdir()} == before
    assert source.read_bytes() == source_before


def test_cli_failure_returns_nonzero_without_success_json(source_fixture, monkeypatch, capsys):
    _, setup, _ = source_fixture
    repo, _, _, _ = setup(wrong_hash=True)
    monkeypatch.setattr(sys, "argv", [
        "prepare_dataset_sample.py", "--repo", str(repo),
        "--output", str(repo / "output"), "--source-ref", "fixture-ref",
    ])
    assert sample.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "FAILED:" in captured.err
    assert not (repo / "output").exists()
