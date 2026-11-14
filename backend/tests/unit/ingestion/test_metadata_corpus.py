"""Tests for the draft metadata corpus exporter."""

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / "scripts/build_metadata_corpus.py"
SPEC = importlib.util.spec_from_file_location("metadata_corpus", SCRIPT)
corpus = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(corpus)


def test_passage_field_order_whitespace_and_tags():
    asset = {
        "name": "  Wooden\tChair ",
        "description": "A chair.\r\n Solid wood.",
        "tags": [" oak ", "oak", "", " modern\tchair ", "Oak"],
        "category": " furniture-home ",
        "license": "must-not-appear",
        "asset_id": "must-not-appear",
    }

    assert corpus.make_passage(asset) == (
        "Wooden Chair\n"
        "A chair. Solid wood.\n"
        "oak, modern chair, Oak\n"
        "furniture-home"
    )


def test_passage_omits_missing_null_and_empty_fields():
    assert corpus.make_passage({
        "name": " Chair ",
        "description": None,
        "tags": ["", " \t"],
        "category": " ",
    }) == "Chair"

    assert corpus.make_passage({}) == ""


@pytest.mark.parametrize("asset", [
    {"name": 123},
    {"description": []},
    {"category": {}},
    {"tags": "chair"},
    {"tags": [None]},
    {"tags": [123]},
])
def test_passage_rejects_invalid_field_types(asset):
    with pytest.raises(ValueError):
        corpus.make_passage(asset)


@pytest.fixture
def run_export(tmp_path, monkeypatch):
    """Use isolated metadata and a stub Git reader; no real repo changes."""
    records = [
        {"asset_id": f"asset_{number:03d}", "name": f"Chair {number}"}
        for number in range(200)
    ]

    def run(source=None, checkout=None, expected_hash=None):
        source = records if source is None else source
        source_bytes = json.dumps(
            source, ensure_ascii=False
        ).encode("utf-8")
        source_hash = hashlib.sha256(source_bytes).hexdigest()

        source_path = tmp_path / corpus.SOURCE_PATH
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            json.dumps(source if checkout is None else checkout),
            encoding="utf-8",
        )

        def fake_git(repo, *args):
            if args == ("show", f"HEAD:{corpus.SOURCE_PATH}"):
                return source_bytes
            if args == ("rev-parse", "HEAD"):
                return b"fixture-commit\n"
            raise AssertionError(f"Unexpected Git command: {args}")

        output = tmp_path / "output"
        monkeypatch.setattr(corpus, "git", fake_git)
        monkeypatch.setattr(
            corpus,
            "EXPECTED_SOURCE_SHA256",
            source_hash if expected_hash is None else expected_hash,
        )
        monkeypatch.setattr(sys, "argv", [
            "build_metadata_corpus.py",
            "--repo", str(tmp_path),
            "--output", str(output),
        ])

        corpus.main()
        return output

    return records, run


def test_export_preserves_all_ids_and_records_hash(run_export):
    records, run = run_export
    output = run(source=list(reversed(records)))

    raw = (output / "corpus.jsonl").read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    manifest = json.loads(
        (output / "manifest.json").read_text(encoding="utf-8")
    )

    expected_ids = sorted(record["asset_id"] for record in records)
    assert [row["asset_id"] for row in rows] == expected_ids
    assert len(rows) == len({row["asset_id"] for row in rows}) == 200
    assert all(row["passage"] for row in rows)
    assert all(set(row) == {"asset_id", "passage"} for row in rows)

    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    assert manifest["corpus_sha256"] == hashlib.sha256(raw).hexdigest()
    assert manifest["asset_ids"] == expected_ids
    assert manifest["asset_count"] == 200
    assert manifest["nonempty_passage_count"] == 200
    assert manifest["prefix_in_corpus"] is False
    assert manifest["status"] == "recipe_confirmed"


def test_export_is_independent_of_input_order(run_export):
    records, run = run_export
    output = run(source=records)
    first_bytes = (output / "corpus.jsonl").read_bytes()

    output = run(source=list(reversed(records)))
    assert (output / "corpus.jsonl").read_bytes() == first_bytes


def test_export_rejects_wrong_source_hash(run_export):
    _, run = run_export
    with pytest.raises(ValueError, match="Unexpected source manifest hash"):
        run(expected_hash="0" * 64)


def test_export_rejects_changed_checkout_metadata(run_export):
    records, run = run_export
    checkout = copy.deepcopy(records)
    checkout[0]["name"] = "Changed locally"

    with pytest.raises(ValueError, match="Checkout metadata differs"):
        run(checkout=checkout)


def test_export_rejects_wrong_record_count(run_export):
    records, run = run_export
    with pytest.raises(ValueError, match="exactly 200"):
        run(source=records[:-1])


def test_export_rejects_duplicate_ids(run_export):
    records, run = run_export
    changed = copy.deepcopy(records)
    changed[1]["asset_id"] = changed[0]["asset_id"]

    with pytest.raises(ValueError, match="Duplicate asset_id"):
        run(source=changed)


def test_export_rejects_invalid_id(run_export):
    records, run = run_export
    changed = copy.deepcopy(records)
    changed[0]["asset_id"] = " asset_000 "

    with pytest.raises(ValueError, match="Invalid asset_id"):
        run(source=changed)


def test_export_rejects_empty_passage(run_export):
    records, run = run_export
    changed = copy.deepcopy(records)
    changed[0] = {"asset_id": "asset_000", "name": " \t"}

    with pytest.raises(ValueError, match="Empty passage"):
        run(source=changed)