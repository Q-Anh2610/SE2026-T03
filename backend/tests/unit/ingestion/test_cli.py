"""Kiểm thử CLI ingestion, không gọi mạng hoặc database."""

import json

import pytest

from backend.app.ingestion import cli


def test_cli_passes_arguments_and_reports_success(
    tmp_path, monkeypatch, capsys
):
    manifest = tmp_path / "manifest.json"
    output_dir = tmp_path / "previews"
    previous_report = tmp_path / "previous.json"
    report_path = tmp_path / "report.json"
    received = {}

    summary = {
        "input_count": 5,
        "succeeded": 3,
        "failed": 0,
        "skipped": 2,
    }

    def fake_run_batch(**kwargs):
        received.update(kwargs)
        return {"summary": summary}

    monkeypatch.setattr(cli, "run_batch", fake_run_batch)

    exit_code = cli.main([
        "--manifest", str(manifest),
        "--output-dir", str(output_dir),
        "--report", str(report_path),
        "--previous-report", str(previous_report),
        "--max-attempts", "2",
        "--limit", "5",
    ])

    assert exit_code == 0
    assert received == {
        "manifest_path": manifest,
        "output_dir": output_dir,
        "report_path": report_path,
        "max_attempts": 2,
        "limit": 5,
        "previous_report_path": previous_report,
    }

    output = capsys.readouterr()
    summary_text, _, _ = output.out.partition("\nBáo cáo:")
    assert json.loads(summary_text) == summary


def test_cli_returns_failure_when_batch_has_failed_assets(
    tmp_path, monkeypatch
):
    def fake_run_batch(**kwargs):
        return {
            "summary": {
                "input_count": 2,
                "succeeded": 1,
                "failed": 1,
                "skipped": 0,
            }
        }

    monkeypatch.setattr(cli, "run_batch", fake_run_batch)

    exit_code = cli.main([
        "--report", str(tmp_path / "report.json"),
    ])

    assert exit_code == 1


def test_cli_refuses_to_overwrite_existing_report(
    tmp_path, monkeypatch
):
    report_path = tmp_path / "existing.json"
    report_path.write_text("existing report", encoding="utf-8")

    def unexpected_run(**kwargs):
        pytest.fail("Không được chạy batch khi báo cáo đã tồn tại.")

    monkeypatch.setattr(cli, "run_batch", unexpected_run)

    with pytest.raises(SystemExit) as caught:
        cli.main(["--report", str(report_path)])

    assert caught.value.code == 2
    assert report_path.read_text(encoding="utf-8") == "existing report"


def test_cli_reports_input_error(
    tmp_path, monkeypatch, capsys
):
    def fake_run_batch(**kwargs):
        raise ValueError("Manifest không hợp lệ.")

    monkeypatch.setattr(cli, "run_batch", fake_run_batch)

    exit_code = cli.main([
        "--report", str(tmp_path / "report.json"),
    ])

    assert exit_code == 1
    assert "Manifest không hợp lệ." in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments",
    [
        ["--max-attempts", "0"],
        ["--limit", "-1"],
    ],
)
def test_cli_rejects_invalid_positive_arguments(
    tmp_path, monkeypatch, arguments
):
    def unexpected_run(**kwargs):
        pytest.fail("Không được chạy batch với tham số không hợp lệ.")

    monkeypatch.setattr(cli, "run_batch", unexpected_run)

    with pytest.raises(SystemExit) as caught:
        cli.main([
            "--report", str(tmp_path / "report.json"),
            *arguments,
        ])

    assert caught.value.code == 2