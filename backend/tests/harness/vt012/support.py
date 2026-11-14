"""Fault adapter quanh Qdrant local thật; không gọi dịch vụ/model bên ngoài."""

from copy import deepcopy

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.search.qdrant_store import IndexConfig, QdrantStore


def config():
    return IndexConfig(
        model_id="vt012-synthetic",
        model_revision="fixture-v1",
        dimension=3,
        preprocessing_version="fixture-l2-v1",
        dataset_snapshot="vt012-self-created-v1",
        index_version="vt012-test-v1",
    )


def embedding(asset_id="vt012-chair"):
    return {
        "asset_id": asset_id,
        "metadata": {"asset_id": asset_id, "name": "Synthetic chair", "license": None},
        "vector": [1.0, 0.0, 0.0],
    }


def http_error(code):
    return UnexpectedResponse(code, "Injected", b"{}", httpx.Headers())


def timeout_error():
    return ResponseHandlingException(httpx.ReadTimeout("injected response loss"))


class FaultClient:
    """Mỗi phần tử fault mô tả kết quả một lần gọi upsert.

    before: timeout trước ghi; after: ghi hết rồi mất phản hồi;
    partial: ghi point đầu rồi mất phản hồi; None: chạy bình thường.
    Exception: ném lỗi chỉ định trước ghi. Collection được tạo qua client thật.
    """

    def __init__(self, faults=()):
        self.real = QdrantClient(location=":memory:")
        self.faults = list(faults)
        self.calls = []
        self.events = []

    def __getattr__(self, name):
        return getattr(self.real, name)

    def upsert(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        self.events.append("UPSERT")
        fault = self.faults.pop(0) if self.faults else None
        if isinstance(fault, Exception):
            self.events.append("ERROR")
            raise fault
        if fault == "before":
            self.events.append("TIMEOUT_BEFORE_WRITE")
            raise timeout_error()
        if fault == "partial":
            self.real.upsert(**{**kwargs, "points": kwargs["points"][:1]})
            self.events.append("PARTIAL_WRITE_RESPONSE_LOST")
            raise timeout_error()
        operation = self.real.upsert(**kwargs)
        if fault == "after":
            self.events.append("WRITE_DONE_RESPONSE_LOST")
            raise timeout_error()
        self.events.append("COMPLETED")
        return operation

    def snapshot(self, collection_name):
        points, _ = self.real.scroll(collection_name, limit=1000, with_vectors=True)
        return sorted(
            [point.model_dump(mode="json") for point in points], key=lambda item: item["id"]
        )


def make_store(faults=(), **kwargs):
    client = FaultClient(faults)
    try:
        store = QdrantStore(
            client,
            collection_name="vt012_assets",
            config=config(),
            **kwargs,
        )
    except Exception:
        client.close()
        raise
    return store, client
