import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import EvaluationError


@dataclass(frozen=True)
class ProductSearchResult:
    asset_ids: list[str]
    versions: dict[str, str]


class ProductSearch(Protocol):
    """Seam for calling the product search API/service; no retrieval logic lives here."""

    def search(self, query: str, *, filters: dict[str, object], limit: int) -> ProductSearchResult:
        """Run one text query and return ranked product asset IDs."""


class HttpProductSearch:
    """Thin adapter for the product's POST /api/v1/search/text endpoint."""

    def __init__(self, url: str, timeout_seconds: float = 30) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, *, filters: dict[str, object], limit: int) -> ProductSearchResult:
        body = json.dumps(
            {"query": query, "filters": filters, "page": 1, "limit": limit}
        ).encode("utf-8")
        request = Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise EvaluationError(f"Search API trả HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise EvaluationError(f"Không gọi được Search API '{self.url}': {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvaluationError("Search API trả về JSON không hợp lệ.") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise EvaluationError("Response Search API không có mảng 'results' hợp lệ.")
        asset_ids: list[str] = []
        for rank, result in enumerate(payload["results"], start=1):
            asset = result.get("asset") if isinstance(result, dict) else None
            asset_id = asset.get("asset_id") if isinstance(asset, dict) else None
            if not isinstance(asset_id, str) or not asset_id:
                raise EvaluationError(f"Search API trả result hạng {rank} thiếu asset.asset_id.")
            asset_ids.append(asset_id)
        versions = payload.get("versions")
        if not isinstance(versions, dict):
            versions = {}
        return ProductSearchResult(asset_ids=asset_ids, versions={str(k): str(v) for k, v in versions.items()})
