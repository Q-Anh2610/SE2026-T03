"""Bootstrap #65: manifest + encoder pin revision + service #60, không build index."""

import logging
from threading import RLock

from app.core.config import Settings
from app.services.text_search import SearchUnavailable

logger = logging.getLogger(__name__)


class LockedSearchAdapter:
    """Serialize CPU/local-Qdrant và đóng client một lần khi shutdown."""

    def __init__(self, service, client):
        self.service = service
        self.client = client
        self.lock = RLock()
        self.closed = False

    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                self.client.close()


class CLIPTextSearchAdapter(LockedSearchAdapter):
    def search_text(self, query, filters, *, candidate_limit=200):
        from app.search.text_search import SearchUnavailableError

        with self.lock:
            if self.closed:
                raise SearchUnavailable("closed")
            try:
                return self.service.search_text(query, filters, candidate_limit=candidate_limit)
            except SearchUnavailableError:
                raise SearchUnavailable("retrieval_unavailable") from None


def load_encoder():
    # Import/model load chỉ khi thực sự cấu hình service, không trong health/import.
    from app.embedding.clip_encoder import CLIPEncoder
    return CLIPEncoder(device="cpu", local_files_only=True)


def open_client(settings: Settings):
    from qdrant_client import QdrantClient

    if settings.text_qdrant_local_path is not None:
        path = settings.text_qdrant_local_path.resolve()
        # Không tạo database local mới do người dùng trỏ nhầm thư mục.
        if not path.is_dir() or not (path / "meta.json").is_file():
            raise ValueError("Existing Qdrant local storage required.")
        return QdrantClient(path=str(path), force_disable_check_same_thread=True)
    from urllib.parse import urlsplit
    url = urlsplit(settings.text_qdrant_url)
    if url.scheme not in {"http", "https"} or not url.hostname or url.username is not None or url.password is not None:
        raise ValueError("Qdrant URL must be an HTTP(S) origin without credentials.")
    if url.path not in {"", "/"} or url.query or url.fragment:
        raise ValueError("Qdrant URL must be an origin.")
    return QdrantClient(url=settings.text_qdrant_url, timeout=5,
        api_key=settings.text_qdrant_api_key.get_secret_value() if settings.text_qdrant_api_key else None)


def build_text_search_service(settings: Settings):
    """Một lần lúc startup; config/cache/index lỗi giữ API liveness + search 503.

    Không tự tải weights, tạo collection, upsert hoặc ghi PostgreSQL. Muốn retry
    bootstrap sau khi bổ sung cấu hình/cache/index cần restart app.
    """
    if settings.text_index_manifest is None and settings.text_index_root is None:
        return None
    client = None
    try:
        from app.search.index_manifest import load_index_manifest
        from app.search.text_search import TextSearchService

        if settings.text_index_manifest is None or settings.text_index_root is None:
            raise ValueError("Configure both index manifest and handoff root.")
        manifest = load_index_manifest(settings.text_index_manifest)
        manifest.verify_input_hashes(settings.text_index_root)
        if manifest.retrieval_config.candidate_limit != 200:
            raise ValueError("HTTP API requires the top-200 retrieval config.")
        client = open_client(settings)
        store = manifest.make_store(client)
        store.validate_collection()
        if client.count(manifest.collection, exact=True).count != manifest.point_count:
            raise ValueError("Index point count differs from manifest.")
        encoder = load_encoder()
        manifest.check_encoder(encoder)
        return CLIPTextSearchAdapter(TextSearchService(encoder, store), client)
    except Exception as exc:
        if client is not None:
            client.close()
        logger.error("Text search bootstrap unavailable: %s", type(exc).__name__)
        return None
