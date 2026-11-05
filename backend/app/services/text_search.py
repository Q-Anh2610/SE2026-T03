"""Điều phối HTTP/DB cho #65; không triển khai encoder hoặc retrieval của #60."""

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models import Asset
from app.schemas.api import Pagination, SearchResult
from app.schemas.text_search import (
    LiveTextSearchRequest, LiveTextSearchResponse, TextSearchCandidates, TextSearchFilters,
)
from app.services.assets import asset_metadata
from app.services.search_events import persist_text_search_event


class SearchUnavailable(RuntimeError):
    """Adapter #60 raise khi dependency/index thiếu hoặc không tương thích."""


class TextSearchService(Protocol):
    def search_text(
        self, query: str, filters: TextSearchFilters, *, candidate_limit: int = 200,
    ) -> TextSearchCandidates: ...


def unavailable():
    return api_error(503, "SEARCH_UNAVAILABLE", "Dịch vụ tìm kiếm chưa sẵn sàng. Vui lòng thử lại sau.")


def matches_database_filters(asset: Asset, filters: TextSearchFilters) -> bool:
    """Kiểm tra phòng vệ payload index cũ/sai; không âm thầm lọc mất candidate."""
    for field in ("category", "license"):
        value = getattr(filters, field)
        if value is not None and getattr(asset, field) != value:
            return False
    if filters.format is not None and filters.format not in asset.formats:
        return False
    if filters.face_count_min is not None and (asset.face_count is None or asset.face_count < filters.face_count_min):
        return False
    if filters.face_count_max is not None and (asset.face_count is None or asset.face_count > filters.face_count_max):
        return False
    return True


def execute_text_search(
    session: Session, request: LiveTextSearchRequest, candidates: TextSearchCandidates,
) -> LiveTextSearchResponse:
    ids = [hit.asset_id for hit in candidates.hits]
    assets = {} if not ids else {
        asset.asset_id: asset for asset in session.scalars(select(Asset).where(Asset.asset_id.in_(ids)))
    }
    if len(assets) != len(ids) or any(not matches_database_filters(asset, request.filters) for asset in assets.values()):
        raise unavailable()

    total = len(ids)
    pages = (total + request.limit - 1) // request.limit
    offset = (request.page - 1) * request.limit
    selected = candidates.hits[offset:offset + request.limit] if offset < total else []
    # Kiểm tra mapping + response trước commit. UUID tạm chỉ tồn tại nội bộ,
    # sau commit thay đúng hai trường ID bằng UUID do persistence cấp.
    response = LiveTextSearchResponse(
        query_id=UUID(int=0), search_event_id=UUID(int=0), query=request.query,
        results=[SearchResult(
            rank=rank, asset=asset_metadata(assets[hit.asset_id]), score=hit.score,
            retrieval_sources=["clip_text_to_preview"],
            explanation="Xếp hạng theo tương đồng cosine giữa văn bản và ảnh preview bằng CLIP.",
        ) for rank, hit in enumerate(selected, 1)],
        versions=candidates.versions,
        pagination=Pagination(page=request.page, limit=request.limit, total=total, pages=pages,
                              has_next=request.page < pages), mock=False,
    )
    response.model_dump_json()  # Serialization cũng phải hợp lệ trước khi ghi event.
    identifier = persist_text_search_event(session, request, candidates.versions)
    return response.model_copy(update={"query_id": identifier, "search_event_id": identifier})
