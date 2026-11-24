"""Upload #79 → retrieval #76 → metadata PostgreSQL và event ảnh durable."""

from collections.abc import Iterator
from dataclasses import dataclass
from hashlib import sha256
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.image_upload import read_validated_image
from app.api.text_search import ERRORS, EXAMPLE
from app.api.examples import response_example
from app.core.errors import api_error
from app.core.request_logging import log_request_error
from app.db.dependencies import get_db_session
from app.schemas.image_search import LiveImageSearchRequest, LiveImageSearchResponse
from app.schemas.text_search import TextSearchCandidates, TextSearchFilters
from app.search.image_search import InvalidQueryImageError
from app.services.text_search import SearchUnavailable, execute_search, unavailable
from app.services.search_explanation import clip_explanation

logger = logging.getLogger(__name__)
IMAGE_EXAMPLE = {
    **EXAMPLE, "query": "sha256:" + "0" * 64,
    "results": [{
        **EXAMPLE["results"][0], "retrieval_sources": ["clip_image_to_preview"],
        "explanation": clip_explanation("clip_image_to_preview"),
    }],
}
router = APIRouter(prefix="/api/v1", responses=ERRORS)


@dataclass(frozen=True)
class ImageInput:
    content: bytes
    value: LiveImageSearchRequest


async def image_parameters(
    image: Annotated[UploadFile, File(description="JPEG/PNG, tối đa 5 MiB và 4096 px mỗi chiều")],
    filters: Annotated[str, Form(description="Chuỗi JSON filters AND")] = "{}",
    page: Annotated[int, Form(ge=1)] = 1,
    limit: Annotated[int, Form(ge=1, le=50)] = 12,
) -> ImageInput:
    try:
        try:
            parsed = TextSearchFilters.model_validate_json(filters)
        except ValidationError:
            raise api_error(400, "INVALID_FILTERS", "Bộ lọc JSON không hợp lệ.") from None
        content = await read_validated_image(image)
        value = LiveImageSearchRequest(
            query_image_ref="sha256:" + sha256(content).hexdigest(),
            filters=parsed, page=page, limit=limit,
        )
        return ImageInput(content, value)
    finally:
        await image.close()


def image_candidates(
    request: Request, image: Annotated[ImageInput, Depends(image_parameters)],
) -> TextSearchCandidates:
    service = request.app.state.image_search_service
    if service is None:
        raise unavailable()
    try:
        result = service.search_image(image.content, image.value.filters.model_copy(deep=True), candidate_limit=200)
        return TextSearchCandidates.model_validate(result.model_dump() if isinstance(result, TextSearchCandidates) else result)
    except InvalidQueryImageError as exc:
        messages = {
            "INVALID_IMAGE": "Không đọc được nội dung ảnh.",
            "UNSUPPORTED_IMAGE": "Chỉ hỗ trợ ảnh JPEG hoặc PNG.",
            "IMAGE_TOO_LARGE": "Ảnh vượt giới hạn 5 MiB.",
            "IMAGE_DIMENSIONS_EXCEEDED": "Mỗi chiều ảnh không được vượt 4096 pixel.",
        }
        if exc.code in messages:
            raise api_error(400, exc.code, messages[exc.code]) from None
        raise api_error(500, "INTERNAL_ERROR", "Lỗi máy chủ. Vui lòng thử lại sau.") from None
    except SearchUnavailable:
        raise unavailable() from None
    except Exception:
        log_request_error(logger, "Image retrieval failed", stage="image_retrieval")
        raise api_error(500, "INTERNAL_ERROR", "Lỗi máy chủ. Vui lòng thử lại sau.") from None


def image_session(request: Request, candidates: Annotated[TextSearchCandidates, Depends(image_candidates)]) -> Iterator[Session]:
    yield from get_db_session(request)


@router.post(
    "/search/image", response_model=LiveImageSearchResponse, tags=["search"],
    summary="Tìm asset bằng ảnh qua CLIP",
    description="CLIP image-to-preview; score_type=cosine trong [-1,1], không phải phần trăm chính xác. JPEG/PNG tối đa 5 MiB và 4096 px mỗi chiều. Filters AND, cửa sổ 200 ứng viên. Query là SHA-256 bytes ảnh gốc; event được commit trước HTTP 200. Ví dụ dùng dữ liệu minh họa.",
    responses={
        200: response_example(IMAGE_EXAMPLE),
        400: {"description": "INVALID_REQUEST, INVALID_FILTERS, INVALID_IMAGE, UNSUPPORTED_IMAGE, IMAGE_TOO_LARGE, IMAGE_DIMENSIONS_EXCEEDED.", **ERRORS[400]},
    },
)
def search_image(
    image: Annotated[ImageInput, Depends(image_parameters)],
    candidates: Annotated[TextSearchCandidates, Depends(image_candidates)],
    session: Annotated[Session, Depends(image_session)],
):
    return execute_search(session, image.value, candidates)
