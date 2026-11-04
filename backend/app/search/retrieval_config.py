"""Cấu hình có version cho CLIP text retrieval baseline."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.text_search import TEXT_CANDIDATE_LIMIT


TEXT_RETRIEVAL_CONFIG_VERSION = "clip-text-exact-all-filtered-v1"
SCORE_ROUNDOFF_TOLERANCE = 1e-6


class RetrievalConfig(BaseModel):
    """Chỉ nhận các policy đang được implementation hỗ trợ; không bỏ qua options."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["clip-text-retrieval-config-v1"] = "clip-text-retrieval-config-v1"
    config_version: str = f"{TEXT_RETRIEVAL_CONFIG_VERSION}-k200"
    candidate_limit: int = Field(default=TEXT_CANDIDATE_LIMIT, ge=1, le=TEXT_CANDIDATE_LIMIT, strict=True)
    strategy: Literal["exact_all_filtered_points"] = "exact_all_filtered_points"
    exact: Literal[True] = True
    score_threshold: None = None
    score_roundoff_tolerance: Literal[1e-6] = SCORE_ROUNDOFF_TOLERANCE
    ordering: tuple[Literal["score_desc"], Literal["asset_id_asc"]] = ("score_desc", "asset_id_asc")
    deduplication: Literal["max_score_per_asset"] = "max_score_per_asset"
    query_trim: Literal[True] = True
    query_min_characters: Literal[1] = 1
    query_max_characters: Literal[500] = 500
    text_token_policy: Literal["truncate"] = "truncate"
    text_token_limit_source: Literal["model.config.text_config.max_position_embeddings"] = "model.config.text_config.max_position_embeddings"

    @model_validator(mode="after")
    def version_matches_parameters(self) -> Self:
        expected = f"{TEXT_RETRIEVAL_CONFIG_VERSION}-k{self.candidate_limit}"
        if self.config_version != expected:
            raise ValueError("config_version không khớp retrieval policy/candidate_limit.")
        return self

    @classmethod
    def for_limit(cls, candidate_limit: int) -> Self:
        return cls(
            candidate_limit=candidate_limit,
            config_version=f"{TEXT_RETRIEVAL_CONFIG_VERSION}-k{candidate_limit}",
        )
