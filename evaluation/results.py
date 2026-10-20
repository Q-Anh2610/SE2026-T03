import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import EvaluationError


def make_run(config: dict[str, Any], config_path: Path, benchmark: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "seed": config["seed"],
            "config_path": str(config_path),
            "config": config,
            "search_versions": benchmark["search_versions"],
        },
        "records": benchmark["records"],
    }


def read_run(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvaluationError(f"Không tìm thấy file kết quả '{path}'.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"File kết quả '{path}' không phải JSON UTF-8 hợp lệ.") from exc
    if not isinstance(payload, dict):
        raise EvaluationError(f"File kết quả '{path}' phải chứa object JSON.")
    return payload


def write_run(payload: dict[str, Any], output: Path) -> Path:
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise EvaluationError(f"Không ghi được kết quả vào '{output}': {exc}") from exc
    return output
