"""Chạy từ backend/: python -m app.export_openapi."""

import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app


def contract_app():
    return create_app(Settings(
        _env_file=None, name="3D Asset Semantic Search API", env="development",
        debug=False, mock_api_enabled=True, asset_list_source="database", cors_origins=[],
    ))


def main() -> None:
    destination = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"
    destination.write_text(
        json.dumps(contract_app().openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print("Exported docs/openapi.json")


if __name__ == "__main__":
    main()
