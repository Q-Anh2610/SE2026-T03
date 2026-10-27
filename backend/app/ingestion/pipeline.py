"""Điều phối tải preview theo manifest và xuất báo cáo local."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .cache import reusable_preview
from .downloader import PreviewDownloadError, download_preview_with_retry
from .source_adapter import SourceAdapter


def load_previous_results(report_path):
    """Đọc báo cáo cũ và lập bảng tra theo định danh asset."""
    if report_path is None:
        return {}

    report = json.loads(
        Path(report_path).read_text(encoding="utf-8")
    )

    if not isinstance(report, dict):
        raise ValueError("Báo cáo cũ phải là JSON object.")

    records = report.get("results")

    if not isinstance(records, list):
        raise ValueError("Báo cáo cũ phải có danh sách results.")

    previous_by_id = {}

    for item in records:
        if not isinstance(item, dict):
            continue

        if item.get("status") not in {"downloaded", "skipped"}:
            continue

        key = (
            item.get("asset_id"),
            item.get("source"),
            item.get("source_id"),
        )

        if not all(isinstance(value, str) and value for value in key):
            continue

        previous_by_id[key] = item

    return previous_by_id


def run_batch(
    manifest_path: str | Path,
    output_dir: str | Path,
    report_path: str | Path,
    *,
    max_attempts: int = 3,
    limit: int | None = None,
    previous_report_path: str | Path | None = None,
) -> dict:
    """Xử lý từng asset; tái sử dụng preview local đã kiểm tra."""
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit phải là số nguyên dương hoặc None.")

    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("max_attempts phải là số nguyên dương.")

    manifest_path = Path(manifest_path)
    report_path = Path(report_path)

    if manifest_path.resolve() == report_path.resolve():
        raise ValueError("Không được ghi báo cáo đè manifest nguồn.")

    if previous_report_path is not None:
        previous_report_path = Path(previous_report_path)

        if previous_report_path.resolve() == report_path.resolve():
            raise ValueError("Không được ghi đè báo cáo lần chạy trước.")

    started_at = datetime.now(timezone.utc).isoformat()

    # Hash trước khi xử lý để ghi nhận manifest đầu vào.
    manifest_sha256 = hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()

    adapter = SourceAdapter(manifest_path)
    raw_records = adapter.load_manifest()

    if limit is not None:
        raw_records = raw_records[:limit]

    valid_records, invalid_records = adapter.normalize_and_validate(
        raw_records
    )
    previous_by_id = load_previous_results(previous_report_path)
    results = []

    for invalid in invalid_records:
        results.append({
            "asset_id": invalid["asset_id"],
            "status": "failed",
            "stage": "validation",
            "attempts": 0,
            "error_type": "InvalidMetadata",
            "error_message": "; ".join(invalid["errors"]),
        })

    for asset in valid_records:
        result = {
            "asset_id": asset["asset_id"],
            "source": asset["source"],
            "source_id": asset["source_id"],
        }

        try:
            preview_url = asset["thumbnail_path"]

            if not isinstance(preview_url, str) or not preview_url.strip():
                raise ValueError("Asset không có URL preview.")

            key = (
                asset["asset_id"],
                asset["source"],
                asset["source_id"],
            )

            cached = reusable_preview(
                previous_by_id.get(key),
                preview_url,
                output_dir,
            )

            if cached is not None:
                result.update(
                    cached,
                    status="skipped",
                    stage="preview",
                    error_type=None,
                    error_message=None,
                )
            else:
                preview = download_preview_with_retry(
                    preview_url,
                    output_dir,
                    max_attempts=max_attempts,
                )

                result.update(
                    preview,
                    status="downloaded",
                    stage="preview",
                    error_type=None,
                    error_message=None,
                )

        except PreviewDownloadError as exc:
            result.update(
                status="failed",
                stage="preview",
                attempts=exc.attempts,
                error_type=type(exc.last_error).__name__,
                error_message=str(exc.last_error),
            )

        except ValueError as exc:
            result.update(
                status="failed",
                stage="validation",
                attempts=0,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        results.append(result)

    succeeded = sum(
        item["status"] == "downloaded" for item in results
    )
    failed = sum(
        item["status"] == "failed" for item in results
    )
    skipped = sum(
        item["status"] == "skipped" for item in results
    )

    report = {
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": manifest_path.as_posix(),
        "manifest_sha256": manifest_sha256,
        "config": {
            "max_attempts": max_attempts,
            "limit": limit,
            "previous_report_path": (
                previous_report_path.as_posix()
                if previous_report_path is not None
                else None
            ),
        },
        "persistence": "local_files_only",
        "summary": {
            "input_count": len(raw_records),
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
        },
        "results": results,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return report