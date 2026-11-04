"""Chuyển filters của contract text search thành điều kiện Qdrant."""

from collections.abc import Mapping

from qdrant_client import models

from app.schemas.text_search import TextSearchFilters


def build_qdrant_filter(
    filters: TextSearchFilters | Mapping[str, object],
) -> models.Filter | None:
    """Validate trước khi tạo filters AND để truyền vào truy vấn Qdrant.

    Không có điều kiện thì trả None, giữ cả asset thiếu metadata. Khi có
    điều kiện, match/range của Qdrant loại metadata thiếu hoặc null tương ứng.
    """
    raw = filters.model_dump() if isinstance(filters, TextSearchFilters) else filters
    validated = TextSearchFilters.model_validate(raw)
    conditions: list[models.FieldCondition] = []

    for field, payload_key in (
        ("category", "category"),
        ("license", "license"),
        ("format", "formats"),
    ):
        value = getattr(validated, field)
        if value is not None:
            conditions.append(
                models.FieldCondition(
                    key=payload_key,
                    match=models.MatchValue(value=value),
                )
            )

    if validated.face_count_min is not None or validated.face_count_max is not None:
        conditions.append(
            models.FieldCondition(
                key="face_count",
                range=models.Range(
                    gte=validated.face_count_min,
                    lte=validated.face_count_max,
                ),
            )
        )

    return models.Filter(must=conditions) if conditions else None
