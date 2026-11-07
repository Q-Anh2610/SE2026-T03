"""Nạp CLIP và manifest ảnh của #76 một lần trong vòng đời app."""

import logging

from app.services.text_search import SearchUnavailable
from app.services.text_search_runtime import LockedSearchAdapter, load_encoder, open_client

logger = logging.getLogger(__name__)


class CLIPImageSearchAdapter(LockedSearchAdapter):
    def search_image(self, image_bytes, filters, *, candidate_limit=200):
        from app.search.image_search import SearchUnavailableError

        with self.lock:
            if self.closed:
                raise SearchUnavailable("closed")
            try:
                return self.service.search_image(image_bytes, filters, candidate_limit=candidate_limit)
            except SearchUnavailableError:
                raise SearchUnavailable("retrieval_unavailable") from None


def build_image_search_service(settings):
    if settings.image_index_manifest is None and settings.image_index_root is None:
        return None
    client = None
    try:
        from app.search.image_index_manifest import load_image_index_manifest
        from app.search.image_search import ImageSearchService

        if settings.image_index_manifest is None or settings.image_index_root is None:
            raise ValueError("Configure both image manifest and handoff root.")
        manifest = load_image_index_manifest(settings.image_index_manifest)
        manifest.verify_input_hashes(settings.image_index_root)
        if manifest.as_index_config().model_id != "openai/clip-vit-base-patch32":
            raise ValueError("Image HTTP baseline requires CLIP.")
        # Index vectors độc lập cutoff. API yêu cầu k200 và kiểm versions của
        # kết quả thực, kể cả manifest smoke của Chi được dựng với k10.
        client = open_client(settings.model_copy(update={
            "text_qdrant_url": settings.image_qdrant_url,
            "text_qdrant_local_path": settings.image_qdrant_local_path,
            "text_qdrant_api_key": settings.image_qdrant_api_key,
        }))
        store = manifest.make_store(client)
        store.validate_collection()
        if client.count(manifest.collection, exact=True).count != manifest.point_count:
            raise ValueError("Image index count mismatch.")
        encoder = load_encoder()
        manifest.check_encoder(encoder)
        return CLIPImageSearchAdapter(ImageSearchService(encoder, store), client)
    except Exception as exc:
        if client is not None:
            client.close()
        logger.error("Image search bootstrap unavailable: %s", type(exc).__name__)
        return None
