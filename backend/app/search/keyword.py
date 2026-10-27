"""Keyword baseline dựa trên token metadata, không dùng vector."""

from collections.abc import Mapping, Sequence
from copy import deepcopy
import re
from typing import Any
import unicodedata


KEYWORD_CONFIG_VERSION = "keyword-token-overlap-v1"


def tokenize(text: str) -> frozenset[str]:
    """Chuẩn hóa Unicode/chữ hoa; giữ dấu và tách theo từ."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return frozenset(re.findall(r"[^\W_]+", normalized))


class KeywordBaseline:
    config_version = KEYWORD_CONFIG_VERSION

    def __init__(self, assets: Sequence[Mapping[str, Any]]) -> None:
        self._documents: dict[
            str, tuple[dict[str, Any], frozenset[str]]
        ] = {}

        for asset in assets:
            asset_id = asset.get("asset_id")
            if (
                not isinstance(asset_id, str)
                or not asset_id.strip()
                or asset_id != asset_id.strip()
            ):
                raise ValueError("asset_id không hợp lệ.")

            # Giữ bản ghi đầu tiên khi đầu vào có ID trùng.
            if asset_id in self._documents:
                continue

            tags = asset.get("tags")
            if tags is None:
                tags = []

            if (
                not isinstance(tags, list)
                or any(not isinstance(tag, str) for tag in tags)
            ):
                raise ValueError("tags phải là danh sách chuỗi hoặc null.")

            fields = [
                asset.get("name"),
                asset.get("description"),
                *tags,
            ]
            if any(
                value is not None and not isinstance(value, str)
                for value in fields
            ):
                raise ValueError("Tên và mô tả phải là chuỗi hoặc null.")

            text = " ".join(value for value in fields if value is not None)
            self._documents[asset_id] = (
                deepcopy(dict(asset)),
                tokenize(text),
            )

    def search(
        self,
        query: str,
        *,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        """Trả kết quả nội bộ; chưa tạo search event hoặc gọi HTTP API."""
        if not isinstance(query, str):
            raise ValueError("query phải là chuỗi.")

        query = query.strip()
        if not 1 <= len(query) <= 500:
            raise ValueError("query phải có từ 1 đến 500 ký tự.")

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 50
        ):
            raise ValueError("limit phải là số nguyên từ 1 đến 50.")

        query_tokens = tokenize(query)
        candidates: list[tuple[int, str, list[str]]] = []

        for asset_id, (_, document_tokens) in self._documents.items():
            matched = sorted(query_tokens & document_tokens)
            if matched:
                candidates.append((len(matched), asset_id, matched))

        candidates.sort(key=lambda item: (-item[0], item[1]))

        results: list[dict[str, Any]] = []
        for rank, (score, asset_id, matched) in enumerate(
            candidates[:limit],
            start=1,
        ):
            metadata, _ = self._documents[asset_id]
            results.append(
                {
                    "rank": rank,
                    "asset": deepcopy(metadata),
                    "score": score,
                    "retrieval_sources": ["keyword_metadata"],
                    "explanation": "Khớp từ khóa: " + ", ".join(matched),
                }
            )

        return results