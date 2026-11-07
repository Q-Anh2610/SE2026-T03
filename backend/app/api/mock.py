"""Mock endpoints cho frontend; không gọi DB/Qdrant hay encoder."""

import hashlib
from typing import Annotated

from fastapi import APIRouter, Body, File, Form, Query, Request, UploadFile
from pydantic import ValidationError

from app.api.examples import ASSET_EXAMPLE, FEEDBACK_EXAMPLE, IMAGE_SEARCH_EXAMPLE, PAGINATION_EXAMPLE, SEARCH_EXAMPLE, response_example
from app.api.image_upload import read_validated_image
from app.core.errors import api_error
from app.schemas.api import AssetDetailResponse, AssetFilters, AssetListQuery, AssetListResponse, ErrorResponse, FeedbackRequest, FeedbackResponse, SearchResponse, TextSearchRequest
from app.services.mock_api import MockStore, page_of

ERROR_RESPONSES = {
    status: {"model": ErrorResponse, **response_example({"error": {
        "code": code, "message": message, "details": [],
    }})}
    for status, code, message in [
        (400, "INVALID_REQUEST", "Yêu cầu không hợp lệ."),
        (404, "ASSET_NOT_FOUND", "Không tìm thấy tài nguyên."),
        (500, "INTERNAL_ERROR", "Lỗi máy chủ. Vui lòng thử lại sau."),
    ]
}
router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)
image_router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)
text_router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)
list_router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


def store(request: Request) -> MockStore:
    return request.app.state.mock_store


@list_router.get("/assets", response_model=AssetListResponse, tags=["assets"], summary="[Mock] Danh sách asset",
            responses={200: response_example({"items": [ASSET_EXAMPLE], "pagination": PAGINATION_EXAMPLE, "mock": True})})
async def list_assets(request: Request, params: Annotated[AssetListQuery, Query()]):
    selected = store(request).filtered(AssetFilters.model_validate(params.model_dump(exclude={"page", "limit"})))
    items, pagination = page_of(selected, params.page, params.limit)
    return AssetListResponse(items=items, pagination=pagination, mock=True)


@list_router.get("/assets/{asset_id}", response_model=AssetDetailResponse, tags=["assets"], summary="[Mock] Chi tiết asset",
            responses={200: response_example({"asset": ASSET_EXAMPLE, "mock": True})})
async def get_asset(request: Request, asset_id: str):
    return AssetDetailResponse(asset=store(request).asset(asset_id), mock=True)


@text_router.post("/search/text", response_model=SearchResponse, tags=["search"], summary="[Mock] Tìm kiếm văn bản",
             responses={200: response_example(SEARCH_EXAMPLE)})
async def search_text(request: Request, value: Annotated[TextSearchRequest, Body(openapi_examples={
    "text": {"summary": "Tìm ghế gỗ", "value": {"query": "ghế gỗ", "filters": {}, "page": 1, "limit": 12}},
})]):
    return store(request).search(value.query, value.filters, value.page, value.limit)


@image_router.post("/search/image", response_model=SearchResponse, tags=["search"], summary="[Mock] Upload ảnh preview",
             description="JPEG/PNG decode được, tối đa 5 MiB, mỗi chiều tối đa 4096 pixel. Chỉ trả fixture cố định; chưa tìm theo nội dung ảnh.",
             openapi_extra={"requestBody": {"content": {"multipart/form-data": {
                 "example": {"image": "(chọn file JPEG/PNG)", "filters": '{"category":"Nội thất"}', "page": 1, "limit": 12},
             }}}},
             responses={
                 200: response_example(IMAGE_SEARCH_EXAMPLE),
                 400: {
                     "model": ErrorResponse,
                     "description": (
                         "INVALID_REQUEST, INVALID_FILTERS, IMAGE_TOO_LARGE, UNSUPPORTED_IMAGE, "
                         "IMAGE_DIMENSIONS_EXCEEDED hoặc INVALID_IMAGE."
                     ),
                     **response_example({"error": {
                         "code": "INVALID_IMAGE", "message": "Không đọc được nội dung ảnh.", "details": [],
                     }}),
                 },
             })
async def search_image(
    request: Request,
    image: Annotated[UploadFile, File(description="File JPEG hoặc PNG; không nhận URL ảnh")],
    filters: Annotated[str, Form(description='JSON string, ví dụ {"category":"Nội thất"}')] = "{}",
    page: Annotated[int, Form(ge=1)] = 1,
    limit: Annotated[int, Form(ge=1, le=50)] = 12,
):
    try:
        try:
            parsed = AssetFilters.model_validate_json(filters)
        except ValidationError:
            raise api_error(400, "INVALID_FILTERS", "Bộ lọc JSON không hợp lệ.") from None
        content = await read_validated_image(image)
        reference = "mock-image:" + hashlib.sha256(content).hexdigest()
        return store(request).search(reference, parsed, page, limit, image=True)
    finally:
        await image.close()


@router.post("/feedback", response_model=FeedbackResponse, status_code=201, tags=["feedback"],
             summary="[Mock] Ghi nhận phản hồi trong RAM",
             description="Dùng event ID từ search response của tiến trình hiện tại. Không lưu PostgreSQL; restart sẽ mất feedback.",
             responses={201: response_example(FEEDBACK_EXAMPLE)})
async def send_feedback(request: Request, value: Annotated[FeedbackRequest, Body(openapi_examples={
    "relevant": {"summary": "Thay event ID bằng kết quả search vừa chạy", "value": {
        "search_event_id": "mock-event-example", "asset_id": "mock-chair-01", "relevance": True,
    }},
})]):
    return store(request).feedback(value)
