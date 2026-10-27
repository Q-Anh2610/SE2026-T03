"""Lưu embeddings vào Qdrant với ID ổn định và kiểm tra phiên bản."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import isclose, isfinite, sqrt
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models


@dataclass(frozen=True)
class IndexConfig:
    model_id: str
    model_revision: str
    dimension: int
    preprocessing_version: str
    dataset_snapshot: str
    index_version: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.dimension, bool)
            or not isinstance(self.dimension, int)
            or self.dimension < 1
        ):
            raise ValueError("dimension phải là số nguyên dương.")

        for name, value in asdict(self).items():
            if name != "dimension":
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{name} phải là chuỗi không rỗng.")


class QdrantStore:
    def __init__(
        self,
        client: QdrantClient,
        *,
        collection_name: str,
        config: IndexConfig,
    ) -> None:
        if not collection_name.strip():
            raise ValueError("collection_name không được rỗng.")

        self.client = client
        self.collection_name = collection_name
        self.config = config
        self._versions = {
            **asdict(config),
            "distance": models.Distance.COSINE.value,
        }

        encoded = json.dumps(
            self._versions,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.vector_name = f"clip_{sha256(encoded).hexdigest()[:16]}"

    def ensure_collection(self) -> None:
        """Tạo collection mới hoặc kiểm tra collection hiện có."""
        if not self.client.collection_exists(self.collection_name):
            created = self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    self.vector_name: models.VectorParams(
                        size=self.config.dimension,
                        distance=models.Distance.COSINE,
                    )
                },
            )
            if not created:
                raise RuntimeError("Chưa tạo được collection Qdrant.")
            return

        info = self.client.get_collection(self.collection_name)
        vectors = info.config.params.vectors

        if not isinstance(vectors, dict) or set(vectors) != {
            self.vector_name
        }:
            raise ValueError(
                "Collection không khớp phiên bản embedding/index."
            )

        params = vectors[self.vector_name]
        if (
            params.size != self.config.dimension
            or params.distance != models.Distance.COSINE
        ):
            raise ValueError(
                "Collection không khớp dimension hoặc similarity."
            )

    def upsert(self, embedded: Sequence[dict[str, Any]]) -> int:
        """Nhận report.embedded; trả số point được xác nhận ghi xong."""
        points: list[models.PointStruct] = []
        seen: set[str] = set()

        for item in embedded:
            asset_id = item.get("asset_id")
            metadata = item.get("metadata")
            raw_vector = item.get("vector")

            if (
                not isinstance(asset_id, str)
                or not asset_id.strip()
                or asset_id != asset_id.strip()
            ):
                raise ValueError("asset_id không hợp lệ.")

            if asset_id in seen:
                raise ValueError("Trùng asset_id trong cùng lần upsert.")
            seen.add(asset_id)

            if (
                not isinstance(metadata, dict)
                or metadata.get("asset_id") != asset_id
            ):
                raise ValueError("Metadata không khớp asset_id.")

            if (
                not isinstance(raw_vector, list)
                or len(raw_vector) != self.config.dimension
            ):
                raise ValueError("Vector không khớp dimension.")

            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                for value in raw_vector
            ):
                raise ValueError("Vector phải chứa các giá trị số.")

            vector = [float(value) for value in raw_vector]
            if not all(isfinite(value) for value in vector):
                raise ValueError("Vector chứa giá trị không hữu hạn.")

            norm = sqrt(sum(value * value for value in vector))
            if not isclose(norm, 1.0, abs_tol=1e-5):
                raise ValueError("Vector chưa được chuẩn hóa L2.")

            payload = dict(metadata)
            payload.update(
                model_version=(
                    f"{self.config.model_id}@{self.config.model_revision}"
                ),
                index_version=self.config.index_version,
                _index=dict(self._versions),
            )

            points.append(
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, f"ai04/asset/{asset_id}")),
                    vector={self.vector_name: vector},
                    payload=payload,
                )
            )

        if not points:
            return 0

        self.ensure_collection()
        operation = self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

        if operation.status != models.UpdateStatus.COMPLETED:
            raise RuntimeError("Qdrant chưa xác nhận ghi hoàn tất.")

        return len(points)