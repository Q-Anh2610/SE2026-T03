"""Fixtures cho contract/UI, không dùng để đánh giá semantic search hoặc lưu DB."""

from collections import OrderedDict, deque
from datetime import datetime, timezone
import unicodedata
from uuid import uuid4

from app.core.errors import api_error
from app.schemas.api import AssetFilters, AssetMetadata, FeedbackRequest, FeedbackResponse, Pagination, SearchResponse, SearchResult, Versions


def fixtures() -> list[AssetMetadata]:
    descriptions = [
        ("mock-chair-01", "Ghế gỗ đơn giản", "Nội thất", ["ghế", "gỗ", "chair", "wood"]),
        ("mock-chair-02", "Ghế thư giãn", "Nội thất", ["ghế", "vải", "chair", "lounge"]),
        ("mock-table-01", "Bàn gỗ tròn", "Nội thất", ["bàn", "gỗ", "table", "wood"]),
        ("mock-lamp-01", "Đèn bàn", "Đồ gia dụng", ["đèn", "lamp", "light"]),
        ("mock-vase-01", "Bình hoa", "Đồ gia dụng", ["bình", "hoa", "vase"]),
        ("mock-box-01", "Thùng gỗ", "Game props", ["thùng", "gỗ", "crate", "wood", "box"]),
    ]
    return [AssetMetadata(
        asset_id=identifier, name=name, category=category, tags=tags,
        description="Bản ghi minh họa tự tạo; không có file asset 3D thật.",
        formats=["glb"], face_count=None, thumbnail_url=None, source="fixture",
        source_url=None, author=None, license=None,
    ) for identifier, name, category, tags in descriptions]


def normalized(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFD", value.lower()) if not unicodedata.combining(char)).replace("đ", "d")


def matches(asset: AssetMetadata, filters: AssetFilters) -> bool:
    for key in ("category", "license"):
        expected = getattr(filters, key)
        if expected is not None and getattr(asset, key) != expected:
            return False
    if filters.format is not None and filters.format not in asset.formats:
        return False
    if filters.face_count_min is not None:
        if asset.face_count is None or asset.face_count < filters.face_count_min:
            return False
    if filters.face_count_max is not None:
        if asset.face_count is None or asset.face_count > filters.face_count_max:
            return False
    return True


def page_of(items: list, page: int, limit: int) -> tuple[list, Pagination]:
    total = len(items)
    return items[(page - 1) * limit:page * limit], Pagination(
        page=page, limit=limit, total=total, pages=(total + limit - 1) // limit,
        has_next=page * limit < total,
    )


class MockStore:
    def __init__(self):
        self.assets = fixtures()
        self.events: OrderedDict[str, SearchResponse] = OrderedDict()
        self.feedbacks: deque[FeedbackResponse] = deque(maxlen=1000)

    def asset(self, asset_id: str) -> AssetMetadata:
        for asset in self.assets:
            if asset.asset_id == asset_id:
                return asset
        raise api_error(404, "ASSET_NOT_FOUND", "Không tìm thấy asset.")

    def filtered(self, filters: AssetFilters) -> list[AssetMetadata]:
        return [asset for asset in self.assets if matches(asset, filters)]

    def search(self, query: str, filters: AssetFilters, page: int, limit: int, *, image: bool = False) -> SearchResponse:
        selected = self.filtered(filters)
        if not image:
            tokens = normalized(query).split()
            selected = [asset for asset in selected if all(
                token in normalized(" ".join([asset.name, asset.category or "", *asset.tags, *asset.formats]))
                for token in tokens
            )]
        selected, pagination = page_of(selected, page, limit)
        event_id = "mock-event-" + str(uuid4())
        result = SearchResponse(
            query_id="mock-query-" + str(uuid4()), search_event_id=event_id,
            query=query, versions=Versions(), pagination=pagination,
            results=[SearchResult(
                rank=index, asset=asset,
                retrieval_sources=["mock_preview_fixture" if image else "mock_metadata"],
                explanation=("Kết quả mock cố định; chưa chạy image encoder." if image else "Minh họa khớp từ khóa metadata; chưa chạy semantic search."),
                score=None,
            ) for index, asset in enumerate(selected, start=1)],
        )
        self.events[event_id] = result.model_copy(deep=True)
        if len(self.events) > 256:
            self.events.popitem(last=False)
        return result

    def feedback(self, value: FeedbackRequest) -> FeedbackResponse:
        if value.search_event_id not in self.events:
            raise api_error(404, "SEARCH_EVENT_NOT_FOUND", "Không tìm thấy truy vấn mock; hãy tìm kiếm lại.")
        self.asset(value.asset_id)
        if value.asset_id not in {result.asset.asset_id for result in self.events[value.search_event_id].results}:
            raise api_error(400, "EVENT_ASSET_MISMATCH", "Asset không thuộc kết quả của truy vấn này.")
        recorded = FeedbackResponse(
            feedback_id="mock-feedback-" + str(uuid4()),
            **value.model_dump(), created_at=datetime.now(timezone.utc),
        )
        self.feedbacks.append(recorded)
        return recorded
