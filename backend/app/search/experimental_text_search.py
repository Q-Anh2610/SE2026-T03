"""Service E5/CLIP/RRF thử nghiệm #91; không nối HTTP, DB hoặc đổi default."""

from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
from typing import Literal

import numpy as np

from app.embedding.clip_encoder import (
    MODEL_ID as CLIP_MODEL, MODEL_REVISION as CLIP_REVISION,
    PREPROCESSING_VERSION as CLIP_PREPROCESSING,
)
from app.schemas.text_search import LiveTextSearchRequest, TextSearchFilters, TextSearchHit
from app.search.e5_index import (
    audit_metadata_index, digest, json_bytes,
    load_e5_index_manifest, read_member,
)
from app.search.image_index_manifest import ImageIndexManifest
from app.search.index_manifest import IndexManifest, _portable_path
from app.search.retrieval_config import RetrievalConfig
from app.search.rrf import CLIP_SOURCE, E5_SOURCE, RRFConfig, RRFHit, reciprocal_rank_fusion
from app.search.smoke import audit_index
from app.search.text_search import TextSearchService
from app.search.vector_search import SearchUnavailableError, _INDEX_ERRORS, search_by_vector


SOURCE_WINDOW = 200
AUDIT_POLICY = "exact-pre-post-local-cosine-transition-v1"


def _fingerprint(source, records):
    raw = json_bytes(sorted(records, key=lambda row: row["point_id"]))
    # Existing CLIP and E5 audit formats differ by the final LF.
    return digest(raw if source.source == E5_SOURCE else raw[:-1])


def _prepare_query_audit(source):
    """Predict the exact local cosine transition on copies, never round hashes.

    Qdrant local normalizes its matrix in place on each nonempty cosine query:
    float32 for a new memory collection, float64 after loading persisted lists.
    Remote queries leave the observable stored vectors unchanged.
    """
    try:
        options = source.client.init_options
        local = options.get("location") == ":memory:" or options.get("path") is not None
        if not local:
            return source.current_audit
        points, offset = source.client.scroll(source.store.collection_name, limit=256,
                                              with_payload=True, with_vectors=True)
        if offset is not None or len(points) != SOURCE_WINDOW:
            raise ValueError("Index changed during query preparation.")
        records = [{"point_id": str(p.id), "payload": p.payload, "vector": p.vector} for p in points]
        if _fingerprint(source, records) != source.current_audit["point_payload_vector_sha256"]:
            raise ValueError("Index changed during query preparation.")
        dtype = np.float64 if options.get("path") is not None else np.float32
        name = source.store.vector_name
        vectors = np.array([r["vector"][name] for r in records], dtype=dtype)
        vectors /= np.linalg.norm(vectors, axis=-1)[:, np.newaxis]
        predicted = [{**r, "vector": {name: v.tolist()}} for r, v in zip(records, vectors, strict=True)]
        return {**source.current_audit, "point_payload_vector_sha256": _fingerprint(source, predicted)}
    except _INDEX_ERRORS:
        raise SearchUnavailableError("index_changed_before_query") from None


def _finish_query_audit(source, result, predicted):
    try:
        # Shared retrieval skips query_points when the filtered count is zero.
        expected = predicted if result.hits else source.current_audit
        actual = source._audit()
        if actual != expected:
            raise ValueError("Unexpected index transition during query.")
        source.current_audit = actual
    except _INDEX_ERRORS:
        raise SearchUnavailableError("index_changed_during_query") from None


def _limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= SOURCE_WINDOW:
        raise ValueError("candidate_limit cần integer 1–200.")
    return value


@dataclass(frozen=True)
class E5RetrievalConfig:
    candidate_limit: int
    exact: bool = True
    score_threshold: None = None
    score_roundoff_tolerance: float = 1e-6

    def __post_init__(self):
        _limit(self.candidate_limit)
        if self.exact is not True or self.score_threshold is not None or self.score_roundoff_tolerance != 1e-6:
            raise ValueError("Chỉ hỗ trợ exact cosine, không threshold, tolerance 1e-6.")

    @property
    def config_version(self) -> str:
        return f"e5-metadata-exact-all-filtered-maskmean512-l2-v1-k{self.candidate_limit}"


@dataclass(frozen=True)
class RankedCandidate:
    asset_id: str
    rank: int
    score: float


@dataclass(frozen=True)
class SourceProvenance:
    source: str
    model_id: str
    model_revision: str
    index_version: str
    config_version: str
    dataset_snapshot: str
    source_manifest_sha256: str
    index_manifest_ref: str
    index_manifest_sha256: str
    collection: str
    vector_name: str
    candidate_limit: int
    corpus_sha256: str | None = None
    recipe_version: str | None = None
    corpus_manifest_sha256: str | None = None
    audit_policy: str = AUDIT_POLICY


@dataclass(frozen=True)
class SourceRanking:
    source: str
    hits: tuple[RankedCandidate, ...]
    filters: dict
    provenance: SourceProvenance
    score_type: Literal["cosine"] = "cosine"


@dataclass(frozen=True)
class FusionSearchResult:
    hits: tuple[RRFHit, ...]
    config_version: str
    filters: dict
    parameters: dict
    candidate_snapshot: str
    source_manifest_sha256: str
    candidate_ids_sha256: str
    corpus_sha256: str
    recipe_version: str
    sources: tuple[SourceProvenance, ...]
    raw_rankings: tuple[SourceRanking, ...]
    score_type: Literal["rrf"] = "rrf"


def _ranking(result, filters, provenance) -> SourceRanking:
    expected = {
        "model_version": f"{provenance.model_id}@{provenance.model_revision}",
        "index_version": provenance.index_version,
        "config_version": provenance.config_version,
        "dataset_snapshot": provenance.dataset_snapshot,
    }
    if result.versions.model_dump() != expected:
        raise SearchUnavailableError("incompatible_source_result_versions")
    return SourceRanking(
        source=provenance.source,
        hits=tuple(RankedCandidate(hit.asset_id, rank, hit.score)
                   for rank, hit in enumerate(result.hits, 1)),
        filters=filters.model_dump(exclude_none=True), provenance=provenance,
    )


class E5MetadataSearchService:
    """Caller quản lý client/encoder một lần; service chỉ đọc index đã có.

    Dataset nhỏ cố định 200: audit trước mỗi request để không fusion metadata
    hoặc vector bị thay tại chỗ. Chi phí audit nằm trong thời gian service.
    """

    source = E5_SOURCE

    def __init__(self, encoder, client, root: Path, *, manifest_ref="e5/index-manifest.json"):
        _portable_path(manifest_ref)
        self.encoder, self.client, self.root = encoder, client, Path(root)
        self.manifest_ref = manifest_ref
        try:
            self.manifest = load_e5_index_manifest(self.root / "index-manifest.json")
            self.manifest_sha256 = digest(read_member(self.root, "index-manifest.json"))
            corpus = self.manifest.verify_inputs(self.root)
            self.metadata = corpus.metadata
            self.asset_ids = tuple(row["asset_id"] for row in corpus.rows)
            self.store = self.manifest.make_store(client)
            self.baseline = self._audit()
            self.current_audit = self.baseline.copy()
        except _INDEX_ERRORS:
            raise SearchUnavailableError("e5_index_unavailable_or_incompatible") from None

    @property
    def snapshot(self):
        return self.store.config.dataset_snapshot

    @property
    def source_hash(self):
        return self.manifest.source_manifest_sha256

    def _audit(self):
        self.manifest.check_encoder(self.encoder)
        if digest(read_member(self.root, "index-manifest.json")) != self.manifest_sha256:
            raise ValueError("Index manifest changed.")
        return audit_metadata_index(self.manifest, self.client, self.root)

    def assert_ready(self):
        try:
            if self._audit() != self.current_audit:
                raise ValueError("Index fingerprint changed.")
        except _INDEX_ERRORS:
            raise SearchUnavailableError("e5_index_unavailable_or_incompatible") from None

    def provenance(self, limit):
        config = self.store.config
        return SourceProvenance(
            self.source, config.model_id, config.model_revision, config.index_version,
            E5RetrievalConfig(limit).config_version, self.snapshot, self.source_hash,
            self.manifest_ref, self.manifest_sha256, self.store.collection_name,
            self.store.vector_name, limit, self.manifest.corpus_sha256,
            self.manifest.recipe_version, self.manifest.corpus_manifest_sha256,
        )

    def search_text(self, query: str, filters: TextSearchFilters | dict, *, candidate_limit=SOURCE_WINDOW):
        limit = _limit(candidate_limit)
        request = LiveTextSearchRequest(query=query, filters=filters)
        self.assert_ready()
        predicted = _prepare_query_audit(self)
        result = search_by_vector(self.encoder, self.store,
            lambda: self.encoder.encode_text(request.query), request.filters, E5RetrievalConfig(limit))
        _finish_query_audit(self, result, predicted)
        return _ranking(result, request.filters, self.provenance(limit))


class CLIPTextSource:
    """Adapter thử nghiệm gọi nguyên TextSearchService W3.

    Nhận manifest text hoặc manifest preview CLIP đã pin. Vector preview CLIP
    dùng được cho query text cùng model; retrieval policy text được ghi riêng
    với policy image đã ghi trong manifest gốc. Không tạo manifest/index giả.
    """

    source = CLIP_SOURCE

    def __init__(self, encoder, client, root: Path, *, input_root: Path | None = None,
                 manifest_ref="clip/index-manifest.json"):
        _portable_path(manifest_ref)
        self.encoder, self.client, self.root = encoder, client, Path(root)
        self.input_root = Path(input_root) if input_root is not None else self.root
        self.manifest_ref = manifest_ref
        try:
            raw = read_member(self.root, "index-manifest.json")
            document = json.loads(raw)
            if not isinstance(document, dict):
                raise ValueError("Index manifest must be an object.")
            schema = document.get("schema_version")
            if schema == "clip-text-index-manifest-v1":
                self.manifest = IndexManifest.model_validate_json(raw)
            elif schema == "image-index-manifest-v1":
                self.manifest = ImageIndexManifest.model_validate_json(raw)
            else:
                raise ValueError("Unsupported CLIP index manifest.")
            config = self.manifest.as_index_config()
            if ((config.model_id, config.model_revision, config.dimension, config.preprocessing_version)
                    != (CLIP_MODEL, CLIP_REVISION, 512, CLIP_PREPROCESSING)
                    or self.manifest.asset_count != SOURCE_WINDOW):
                raise ValueError("Need pinned CLIP on candidate 200.")
            self.manifest_sha256 = digest(raw)
            self.manifest.verify_input_hashes(self.input_root)
            source = json.loads(read_member(self.input_root, self.manifest.source_manifest).decode("utf-8-sig"))
            ready = json.loads(read_member(self.input_root, self.manifest.ready_manifest).decode("utf-8-sig"))
            if not isinstance(source, list) or len(source) != SOURCE_WINDOW:
                raise ValueError("Need 200 source assets.")
            self.metadata = {}
            for row in source:
                if not isinstance(row, dict):
                    raise ValueError("Source record must be an object.")
                aid = TextSearchHit(asset_id=row.get("asset_id"), score=0).asset_id
                if aid in self.metadata:
                    raise ValueError("Duplicate source asset.")
                self.metadata[aid] = row
            if not isinstance(ready, list) or len(ready) != SOURCE_WINDOW:
                raise ValueError("Ready/source metadata mismatch.")
            seen_ready = set()
            for row in ready:
                if not isinstance(row, dict) or not isinstance(row.get("metadata"), dict):
                    raise ValueError("Invalid ready record.")
                aid = TextSearchHit(asset_id=row["metadata"].get("asset_id"), score=0).asset_id
                if aid in seen_ready or row["metadata"] != self.metadata.get(aid):
                    raise ValueError("Ready/source metadata mismatch.")
                seen_ready.add(aid)
            self.asset_ids = tuple(sorted(self.metadata))
            self.store = self.manifest.make_store(client)
            self.service = TextSearchService(encoder, self.store)
            self.baseline = self._audit()
            self.current_audit = self.baseline.copy()
        except _INDEX_ERRORS:
            raise SearchUnavailableError("clip_index_unavailable_or_incompatible") from None

    @property
    def snapshot(self):
        return self.store.config.dataset_snapshot

    @property
    def source_hash(self):
        return self.manifest.source_manifest_sha256

    def _audit(self):
        self.manifest.check_encoder(self.encoder)
        if self.encoder.model.config.text_config.max_position_embeddings != 77:
            raise ValueError("CLIP text token policy mismatch.")
        if digest(read_member(self.root, "index-manifest.json")) != self.manifest_sha256:
            raise ValueError("Index manifest changed.")
        self.manifest.verify_input_hashes(self.input_root)
        return audit_index(self.store, self.metadata)

    def assert_ready(self):
        try:
            if self._audit() != self.current_audit:
                raise ValueError("Index fingerprint changed.")
        except _INDEX_ERRORS:
            raise SearchUnavailableError("clip_index_unavailable_or_incompatible") from None

    def provenance(self, limit):
        config = self.store.config
        return SourceProvenance(self.source, config.model_id, config.model_revision,
            config.index_version, RetrievalConfig.for_limit(limit).config_version,
            self.snapshot, self.source_hash, self.manifest_ref, self.manifest_sha256,
            self.store.collection_name, self.store.vector_name, limit)

    def search_text(self, query: str, filters: TextSearchFilters | dict, *, candidate_limit=SOURCE_WINDOW):
        limit = _limit(candidate_limit)
        request = LiveTextSearchRequest(query=query, filters=filters)
        self.assert_ready()
        predicted = _prepare_query_audit(self)
        result = self.service.search_text(request.query, request.filters, candidate_limit=limit)
        _finish_query_audit(self, result, predicted)
        return _ranking(result, request.filters, self.provenance(limit))


class ExperimentalFusionService:
    """Hai nguồn cùng snapshot/filters; không fallback khi một nguồn unavailable."""

    def __init__(self, clip: CLIPTextSource, e5: E5MetadataSearchService):
        self.clip, self.e5 = clip, e5
        self._same_inputs()

    def _same_inputs(self):
        if (self.clip.source != CLIP_SOURCE or self.e5.source != E5_SOURCE
                or (self.clip.snapshot, self.clip.source_hash, self.clip.asset_ids)
                != (self.e5.snapshot, self.e5.source_hash, self.e5.asset_ids)
                or self.clip.metadata != self.e5.metadata):
            raise SearchUnavailableError("fusion_candidate_snapshot_mismatch")

    def _checked_ids(self, source, result, filters):
        if (not isinstance(result, SourceRanking) or result.source != source.source
                or result.score_type != "cosine" or result.filters != filters
                or result.provenance != source.provenance(SOURCE_WINDOW)
                or len(result.hits) > SOURCE_WINDOW):
            raise SearchUnavailableError("invalid_source_ranking")
        ids = []
        for position, hit in enumerate(result.hits, 1):
            if (not isinstance(hit, RankedCandidate) or type(hit.rank) is not int or hit.rank != position
                    or isinstance(hit.score, bool) or not isinstance(hit.score, (int, float))
                    or not isfinite(hit.score) or not -1 <= hit.score <= 1
                    or hit.asset_id not in source.asset_ids):
                raise SearchUnavailableError("invalid_source_ranking")
            ids.append(hit.asset_id)
        if list(result.hits) != sorted(result.hits, key=lambda hit: (-hit.score, hit.asset_id)):
            raise SearchUnavailableError("invalid_source_ordering")
        return ids

    def search_text(self, query: str, filters: TextSearchFilters | dict, *, config: RRFConfig):
        if not isinstance(config, RRFConfig):
            raise TypeError("config cần RRFConfig tường minh.")
        request = LiveTextSearchRequest(query=query, filters=filters)
        self._same_inputs()
        actual_filters = request.filters.model_dump(exclude_none=True)
        # Retrieve đủ 200 trước dedup/cắt cửa sổ fusion. Policy này vào version.
        clip = self.clip.search_text(request.query, request.filters, candidate_limit=SOURCE_WINDOW)
        e5 = self.e5.search_text(request.query, request.filters, candidate_limit=SOURCE_WINDOW)
        clip_ids = self._checked_ids(self.clip, clip, actual_filters)
        e5_ids = self._checked_ids(self.e5, e5, actual_filters)
        fused = reciprocal_rank_fusion(clip_ids, e5_ids, config=config)
        parameters = {**config.parameters(), "rrf_config_version": fused.config_version,
                      "source_retrieval_window": SOURCE_WINDOW,
                      "clip_config_version": clip.provenance.config_version,
                      "e5_config_version": e5.provenance.config_version,
                      "audit_policy": AUDIT_POLICY,
                      "orchestration_policy": "audit-both-same-inputs-all200-before-fusion-v2"}
        version = "experimental-fusion-v1-" + digest(json_bytes(parameters))[:16]
        return FusionSearchResult(fused.hits, version, actual_filters, parameters,
            self.e5.snapshot, self.e5.source_hash, digest(json_bytes(list(self.e5.asset_ids))),
            self.e5.manifest.corpus_sha256, self.e5.manifest.recipe_version,
            (clip.provenance, e5.provenance), (clip, e5))
