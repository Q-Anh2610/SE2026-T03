"""Exact cosine retrieval chung cho text và image; chỉ đọc index."""

from dataclasses import asdict
from math import isclose, isfinite, sqrt
from collections.abc import Callable

from grpc import RpcError
from pydantic import ValidationError
from qdrant_client import models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.schemas.text_search import (
    SearchExecutionVersions,
    TextSearchCandidates,
    TextSearchFilters,
    TextSearchHit,
)
from app.search.filters import build_qdrant_filter
from app.search.qdrant_store import QdrantStore

_INDEX_ERRORS = (
    UnexpectedResponse, ResponseHandlingException, RpcError,
    OSError, ValueError, RuntimeError,
)


class SearchUnavailableError(RuntimeError):
    """API có thể map sang 503; reason dùng chẩn đoán, message không chứa secrets."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__("Dịch vụ tìm kiếm chưa sẵn sàng.")


def search_by_vector(encoder, store: QdrantStore, encode_query: Callable[[], list[float]],
                     filters: TextSearchFilters, retrieval) -> TextSearchCandidates:
    candidate_limit = retrieval.candidate_limit
    query_filter = build_qdrant_filter(filters)
    config = store.config
    actual = (
        encoder.model_id, encoder.revision,
        encoder.dimension, encoder.preprocessing_version,
    )
    expected = (
        config.model_id, config.model_revision,
        config.dimension, config.preprocessing_version,
    )
    if actual != expected:
        raise SearchUnavailableError("incompatible_encoder")

    try:
        versions = SearchExecutionVersions(
            model_version=f"{config.model_id}@{config.model_revision}",
            index_version=config.index_version,
            config_version=retrieval.config_version,
            dataset_snapshot=config.dataset_snapshot,
        )
    except ValidationError:
        raise SearchUnavailableError("invalid_index_versions") from None

    try:
        store.validate_collection()
    except _INDEX_ERRORS:
        raise SearchUnavailableError("index_unavailable_or_incompatible") from None

    try:
        vector = encode_query()
    except SearchUnavailableError:
        raise
    except (OSError, RuntimeError, ValueError):
        raise SearchUnavailableError("encoder_unavailable") from None

    if (
        not isinstance(vector, list)
        or len(vector) != config.dimension
        or any(
            isinstance(value, bool)
            or not isinstance(value, (float, int))
            or not isfinite(value)
            for value in vector
        )
        or not isclose(
            sqrt(sum(value * value for value in vector)),
            1.0, rel_tol=0.0, abs_tol=1e-5,
        )
    ):
        raise SearchUnavailableError("invalid_query_vector")

    try:
        point_count = store.client.count(
            collection_name=store.collection_name,
            count_filter=query_filter,
            exact=True,
        ).count
        points = []
        if point_count:
            points = store.client.query_points(
                collection_name=store.collection_name,
                query=vector,
                using=store.vector_name,
                query_filter=query_filter,
                search_params=models.SearchParams(exact=retrieval.exact),
                limit=point_count,
                score_threshold=retrieval.score_threshold,
                with_payload=True,
                with_vectors=False,
            ).points
    except _INDEX_ERRORS:
        raise SearchUnavailableError("qdrant_unavailable") from None

    if len(points) != point_count:
        raise SearchUnavailableError("index_changed_or_incomplete")

    expected_payload_index = {**asdict(config), "distance": "Cosine"}
    best: dict[str, TextSearchHit] = {}
    for point in points:
        payload = point.payload
        if (
            not isinstance(payload, dict)
            or payload.get("_index") != expected_payload_index
            or payload.get("model_version") != versions.model_version
            or payload.get("index_version") != versions.index_version
        ):
            raise SearchUnavailableError("incompatible_point_payload")

        score = point.score
        if (
            isinstance(score, bool)
            or not isinstance(score, (float, int))
            or not isfinite(score)
            or not (
                -1 - retrieval.score_roundoff_tolerance
                <= score <= 1 + retrieval.score_roundoff_tolerance
            )
        ):
            raise SearchUnavailableError("invalid_cosine_score")

        try:
            # Chỉ chặn sai số float sát biên cosine, không hiệu chỉnh score.
            hit = TextSearchHit(
                asset_id=payload.get("asset_id"),
                score=max(-1.0, min(1.0, score)),
            )
        except ValidationError:
            raise SearchUnavailableError("invalid_asset_id") from None

        previous = best.get(hit.asset_id)
        if previous is None or hit.score > previous.score:
            best[hit.asset_id] = hit

    hits = sorted(best.values(), key=lambda hit: (-hit.score, hit.asset_id))
    return TextSearchCandidates(hits=hits[:candidate_limit], versions=versions)
