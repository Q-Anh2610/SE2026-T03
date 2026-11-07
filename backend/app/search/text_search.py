"""Text-to-preview CLIP retrieval; public interface W3 được giữ nguyên."""

from app.schemas.text_search import (
    LiveTextSearchRequest, TEXT_CANDIDATE_LIMIT, TextSearchCandidates, TextSearchFilters,
)
from app.search.qdrant_store import QdrantStore
from app.search.retrieval_config import (
    RetrievalConfig, SCORE_ROUNDOFF_TOLERANCE, TEXT_RETRIEVAL_CONFIG_VERSION,
)
from app.search.vector_search import SearchUnavailableError, search_by_vector


class TextSearchService:
    """Encoder/store được caller nạp một lần, không ghi event hoặc rebuild."""

    def __init__(self, encoder, store: QdrantStore) -> None:
        self.encoder = encoder
        self.store = store

    def search_text(self, query: str, filters: TextSearchFilters, *,
                    candidate_limit: int = TEXT_CANDIDATE_LIMIT) -> TextSearchCandidates:
        if (isinstance(candidate_limit, bool) or not isinstance(candidate_limit, int)
                or not 1 <= candidate_limit <= TEXT_CANDIDATE_LIMIT):
            raise ValueError("candidate_limit phải là số nguyên từ 1 đến 200.")
        retrieval = RetrievalConfig.for_limit(candidate_limit)
        request = LiveTextSearchRequest(query=query, filters=filters)
        return search_by_vector(self.encoder, self.store,
                                lambda: self.encoder.encode_text(request.query),
                                request.filters, retrieval)
