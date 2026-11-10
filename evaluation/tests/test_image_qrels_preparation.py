"""Synthetic label fixtures only; these tests do not create benchmark judgments."""

import csv
import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/prepare_image_qrels_v1.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
pytestmark = pytest.mark.skipif(not POWERSHELL, reason="PowerShell is required")


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def inputs(tmp_path):
    pairs = [
        {"query_id": f"synthetic-q{q}", "asset_id": f"synthetic-a{a}"}
        for q in range(20) for a in range(200)
    ]
    labels = []
    for name in ("Doan Thi Minh Khue", "Trinh Thi Thu Huyen"):
        labels.append([
            dict(pair, annotator=name, relevance="2", evidence_note="Synthetic test fixture",
                 annotated_at_utc="2026-11-07T09:00:00Z")
            for pair in pairs
        ])
    return tmp_path, pairs, labels


def run_script(inputs):
    directory, pairs, labels = inputs
    for filename, rows in zip(("pairs.csv", "khue.csv", "huyen.csv"), (pairs, *labels)):
        write_csv(directory / filename, rows)
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(SCRIPT),
         "-CandidatePairsPath", str(directory / "pairs.csv"),
         "-KhueLabelsPath", str(directory / "khue.csv"),
         "-HuyenLabelsPath", str(directory / "huyen.csv"),
         "-OutputPath", str(directory / "result.csv")],
        capture_output=True, text=True, timeout=30,
    )
    return result, directory / "result.csv"


def test_disagreement_is_unresolved_and_not_zero(inputs):
    inputs[2][1][0]["relevance"] = "0"
    result, output = run_script(inputs)
    assert result.returncode == 0, result.stderr
    with output.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4000
    assert rows[0]["adjudication_status"] == "Unresolved"
    assert rows[0]["relevance"] == ""
    assert rows[1]["adjudication_status"] == "Agreed"
    assert rows[1]["relevance"] == "2"
    assert "1 disagreements" in result.stdout


@pytest.mark.parametrize(("invalid", "message"), [
    ("duplicate_pair", "duplicate candidate pair"),
    ("foreign_label", "outside the candidate pool"),
    ("wrong_annotator", "misattributed label"),
    ("bad_time", "Invalid UTC timestamp"),
    ("non_utc", "Invalid UTC timestamp"),
    ("incomplete", "4,000 complete labels"),
])
def test_invalid_inputs_do_not_produce_qrels(inputs, invalid, message):
    _, pairs, labels = inputs
    if invalid == "duplicate_pair":
        pairs[-1] = pairs[0].copy()
    elif invalid == "foreign_label":
        labels[0][-1]["asset_id"] = "outside-pool"
    elif invalid == "wrong_annotator":
        labels[0][-1]["annotator"] = "Trinh Thi Thu Huyen"
    elif invalid == "bad_time":
        labels[0][-1]["annotated_at_utc"] = "not-a-timeZ"
    elif invalid == "non_utc":
        labels[0][-1]["annotated_at_utc"] = "2026-11-07T16:00:00+07:00"
    else:
        labels[0].pop()
    result, output = run_script(inputs)
    assert result.returncode != 0
    assert message in result.stderr
    assert not output.exists()


def test_existing_adjudication_is_preserved(inputs):
    output = inputs[0] / "result.csv"
    output.write_text("existing adjudication", encoding="utf-8")
    result, _ = run_script(inputs)
    assert result.returncode != 0
    assert "Output already exists" in result.stderr
    assert output.read_text(encoding="utf-8") == "existing adjudication"
