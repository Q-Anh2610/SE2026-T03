"""Chạy pipeline preview và persistence PostgreSQL tùy chọn."""

import argparse
import json
import sys
from pathlib import Path

from .db_writer import DatabaseWriter
from .pipeline import run_batch


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Giá trị phải lớn hơn 0.")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Tải preview và tùy chọn ghi metadata PostgreSQL."
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/objaverse_200.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/objaverse/previews"),
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--previous-report", type=Path)
    parser.add_argument("--max-attempts", type=positive_int, default=3)
    parser.add_argument("--limit", type=positive_int)
    parser.add_argument(
        "--persist-db",
        action="store_true",
        help="Ghi metadata vào PostgreSQL được cấu hình trong .env.",
    )

    args = parser.parse_args(argv)

    if args.report.exists():
        parser.error("Báo cáo đã tồn tại. Hãy chọn tên file mới.")

    options = {
        "manifest_path": args.manifest,
        "output_dir": args.output_dir,
        "report_path": args.report,
        "max_attempts": args.max_attempts,
        "limit": args.limit,
        "previous_report_path": args.previous_report,
    }

    try:
        if args.persist_db:
            # Các module DB hiện dùng import app.*.
            # Bổ sung backend vào đường dẫn khi chạy CLI từ gốc repo.
            backend_path = str(Path(__file__).resolve().parents[2])
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)

            with DatabaseWriter() as writer:
                report = run_batch(
                    **options,
                    persist_asset=writer,
                )
        else:
            report = run_batch(**options)

    except (OSError, ValueError) as exc:
        print(f"Không chạy được batch: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))

    if args.persist_db:
        saved = sum(
            item.get("database_status") == "saved"
            for item in report["results"]
        )
        print(f"Database saved: {saved}")

    print(f"Báo cáo: {args.report.as_posix()}")

    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())