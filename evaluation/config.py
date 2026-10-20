import json
from pathlib import Path
from typing import Any

from .errors import ConfigError

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


def resolve_config_path(value: str | Path) -> Path:
    path = Path(value)
    candidates = [path] if path.is_absolute() else [Path.cwd() / path, CONFIGS_DIR / path]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    tried = ", ".join(str(candidate) for candidate in candidates)
    raise ConfigError(f"Không tìm thấy config '{value}'. Đã kiểm tra: {tried}")


def load_config(value: str | Path) -> tuple[dict[str, Any], Path]:
    path = resolve_config_path(value)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ConfigError(f"Config '{path}' phải được mã hóa UTF-8.") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"Config '{path}' sai cú pháp JSON tại dòng {exc.lineno}, cột {exc.colno}: {exc.msg}."
        ) from exc
    if not isinstance(config, dict):
        raise ConfigError(f"Config '{path}' phải là một object JSON.")

    required = {
        "version": int,
        "dataset_path": str,
        "search_api_url": str,
        "limit": int,
        "seed": int,
        "timeout_seconds": (int, float),
        "filters": dict,
    }
    for key, expected_type in required.items():
        if key not in config:
            raise ConfigError(f"Config '{path}' thiếu trường bắt buộc '{key}'.")
        if isinstance(config[key], bool) or not isinstance(config[key], expected_type):
            expected = "số" if isinstance(expected_type, tuple) else expected_type.__name__
            raise ConfigError(f"Trường '{key}' trong config '{path}' phải có kiểu {expected}.")
    if config["version"] != 1:
        raise ConfigError(f"Config '{path}' có version={config['version']}; hiện chỉ hỗ trợ version 1.")
    if not 1 <= config["limit"] <= 1000:
        raise ConfigError(f"Trường 'limit' trong config '{path}' phải nằm trong khoảng 1..1000.")
    if config["timeout_seconds"] <= 0:
        raise ConfigError(f"Trường 'timeout_seconds' trong config '{path}' phải lớn hơn 0.")
    if not config["search_api_url"].startswith(("http://", "https://")):
        raise ConfigError(f"Trường 'search_api_url' trong config '{path}' phải là URL HTTP(S).")
    return config, path


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPOSITORY_ROOT / path).resolve()
