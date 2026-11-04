"""Xuất JSON Schema bàn giao #63; không quảng cáo route retrieval đã hoạt động."""

import json
from pathlib import Path

from pydantic.json_schema import models_json_schema

from app.schemas.text_search import LiveTextSearchRequest, LiveTextSearchResponse, TextSearchCandidates


def contract_schema() -> dict:
    _, schema = models_json_schema([
        (LiveTextSearchRequest, "validation"), (LiveTextSearchResponse, "validation"),
        (TextSearchCandidates, "validation"),
    ], title="W3 live text search contract — Issue #63")
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}


def main() -> None:
    path = Path(__file__).resolve().parents[2] / "docs/contracts/text-search-w3.schema.json"
    path.write_text(json.dumps(contract_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Exported docs/contracts/text-search-w3.schema.json")


if __name__ == "__main__":
    main()
