"""Image-to-preview retrieval; nhận bytes, không phụ thuộc upload HTTP."""

from io import BytesIO
import warnings
from typing import Literal, Self

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.text_search import TextSearchCandidates, TextSearchFilters
from app.search.qdrant_store import QdrantStore
from app.search.vector_search import SearchUnavailableError, search_by_vector


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096
IMAGE_RETRIEVAL_CONFIG_VERSION = "image-exact-all-filtered-rgb-v1"


class InvalidQueryImageError(ValueError):
    """Mã lỗi an toàn để TV1 mapping HTTP 400 ở #80."""

    def __init__(self, code: str):
        self.code = code
        super().__init__("Ảnh truy vấn không hợp lệ.")


class ImageRetrievalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["image-retrieval-config-v1"] = "image-retrieval-config-v1"
    config_version: str = f"{IMAGE_RETRIEVAL_CONFIG_VERSION}-k200"
    candidate_limit: int = Field(default=200, strict=True, ge=1, le=200)
    strategy: Literal["exact_all_filtered_points"] = "exact_all_filtered_points"
    exact: Literal[True] = True
    score_threshold: None = None
    score_roundoff_tolerance: Literal[1e-6] = 1e-6
    ordering: tuple[Literal["score_desc"], Literal["asset_id_asc"]] = ("score_desc", "asset_id_asc")
    deduplication: Literal["max_score_per_asset"] = "max_score_per_asset"
    image_formats: tuple[Literal["JPEG"], Literal["PNG"]] = ("JPEG", "PNG")
    max_image_bytes: Literal[5242880] = MAX_IMAGE_BYTES
    max_image_dimension: Literal[4096] = MAX_IMAGE_DIMENSION
    image_color_mode: Literal["RGB"] = "RGB"
    frame_policy: Literal["first"] = "first"
    exif_orientation: Literal["stored_pixels"] = "stored_pixels"

    @model_validator(mode="after")
    def version_matches_parameters(self) -> Self:
        if self.config_version != f"{IMAGE_RETRIEVAL_CONFIG_VERSION}-k{self.candidate_limit}":
            raise ValueError("config_version không khớp candidate_limit.")
        return self

    @classmethod
    def for_limit(cls, candidate_limit: int) -> Self:
        return cls(candidate_limit=candidate_limit,
                   config_version=f"{IMAGE_RETRIEVAL_CONFIG_VERSION}-k{candidate_limit}")


def decode_query_image(content: bytes) -> Image.Image:
    """RGB copy của frame đầu, không tự xoay EXIF; caller đóng ảnh trả về."""
    if not isinstance(content, bytes) or not content:
        raise InvalidQueryImageError("INVALID_IMAGE")
    if len(content) > MAX_IMAGE_BYTES:
        raise InvalidQueryImageError("IMAGE_TOO_LARGE")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format not in {"JPEG", "PNG"}:
                    raise InvalidQueryImageError("UNSUPPORTED_IMAGE")
                if max(image.size) > MAX_IMAGE_DIMENSION:
                    raise InvalidQueryImageError("IMAGE_DIMENSIONS_EXCEEDED")
                image.verify()
            with Image.open(BytesIO(content), formats=["JPEG", "PNG"]) as image:
                image.load()
                return image.convert("RGB")
    except InvalidQueryImageError:
        raise
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise InvalidQueryImageError("INVALID_IMAGE") from None


class ImageSearchService:
    """Tái sử dụng encoder/store; filters/dedup/tie-break dùng cùng W3.

    Interface đề xuất #76 → #80, chưa tạo HTTP response hoặc search event.
    """

    def __init__(self, encoder, store: QdrantStore):
        self.encoder = encoder
        self.store = store

    def search_image(self, image_bytes: bytes, filters: TextSearchFilters, *,
                     candidate_limit: int = 200) -> TextSearchCandidates:
        if (isinstance(candidate_limit, bool) or not isinstance(candidate_limit, int)
                or not 1 <= candidate_limit <= 200):
            raise ValueError("candidate_limit phải là số nguyên từ 1 đến 200.")
        retrieval = ImageRetrievalConfig.for_limit(candidate_limit)
        filters = TextSearchFilters.model_validate(
            filters.model_dump() if isinstance(filters, TextSearchFilters) else filters)
        with decode_query_image(image_bytes) as image:
            def encode_query():
                vectors = self.encoder.encode_images([image], batch_size=1)
                if not isinstance(vectors, list) or len(vectors) != 1:
                    raise SearchUnavailableError("invalid_query_vector")
                return vectors[0]
            return search_by_vector(self.encoder, self.store, encode_query, filters, retrieval)
