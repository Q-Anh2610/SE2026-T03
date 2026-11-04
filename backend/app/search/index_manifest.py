"""Index manifest tái lập; chỉ ghi số liệu do caller thực sự quan sát."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from typing import Literal, Self

from pydantic import (
    BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr,
    field_validator, model_validator,
)
from qdrant_client import QdrantClient

from app.schemas.text_search import SearchExecutionVersions
from app.search.qdrant_store import IndexConfig, QdrantStore, index_vector_name
from app.search.retrieval_config import RetrievalConfig


def _portable_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value or value != value.strip() or "\\" in value or ":" in value
        or path.is_absolute() or any(part in {".", ".."} for part in value.split("/"))
        or "" in value.split("/")
    ):
        raise ValueError("Cần đường dẫn tương đối portable, không đi ra ngoài gói/repo.")
    return value


class IndexManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["clip-text-index-manifest-v1"] = "clip-text-index-manifest-v1"
    created_at_utc: datetime
    observed_at_utc: datetime
    index_config: dict[str, StrictStr | StrictInt]
    collection: str = Field(min_length=1)
    vector_name: str = Field(min_length=1)
    processor_revision: str = Field(min_length=1)
    tokenizer_revision: str = Field(min_length=1)
    max_text_tokens: int = Field(ge=1, strict=True)
    processor_use_fast: Literal[False] = False
    image_color_mode: Literal["RGB"] = "RGB"
    normalization: Literal["L2"] = "L2"
    similarity: Literal["Cosine"] = "Cosine"
    source_manifest: str
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ready_manifest: str
    ready_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    asset_count: int = Field(ge=1, strict=True)
    point_count: int = Field(ge=1, strict=True)
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    working_tree_dirty: StrictBool
    module_sha256: dict[str, str] = Field(min_length=1)
    retrieval_config: RetrievalConfig

    @field_validator("index_config", mode="before")
    @classmethod
    def canonical_index_config(cls, value):
        if not isinstance(value, dict):
            raise ValueError("index_config phải là object.")
        try:
            return asdict(IndexConfig(**value))
        except (TypeError, ValueError):
            raise ValueError("index_config thiếu trường, sai kiểu hoặc chứa trường lạ.") from None

    @field_validator("source_manifest", "ready_manifest")
    @classmethod
    def portable_input_path(cls, value: str) -> str:
        return _portable_path(value)

    @field_validator("collection", "vector_name", "processor_revision", "tokenizer_revision")
    @classmethod
    def no_surrounding_whitespace(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("Giá trị không được có khoảng trắng đầu/cuối.")
        return value

    @field_validator("created_at_utc", "observed_at_utc")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("Thời điểm phải có timezone UTC.")
        return value

    @field_validator("module_sha256")
    @classmethod
    def portable_module_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        for path, digest in value.items():
            _portable_path(path)
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Module hash phải là SHA-256 lowercase.")
        return value

    @model_validator(mode="after")
    def compatible_fields(self) -> Self:
        config = self.as_index_config()
        if self.vector_name != index_vector_name(config):
            raise ValueError("Named vector không khớp index_config.")
        if self.processor_revision != config.model_revision or self.tokenizer_revision != config.model_revision:
            raise ValueError("Model, processor và tokenizer phải cùng pinned revision.")
        if not config.dataset_snapshot.endswith("sha256:" + self.source_manifest_sha256):
            raise ValueError("Dataset snapshot không khớp SHA-256 manifest nguồn.")
        if self.point_count != self.asset_count:
            raise ValueError("Baseline single-preview yêu cầu một point cho mỗi asset.")
        if self.observed_at_utc > self.created_at_utc:
            raise ValueError("Thời điểm quan sát không được sau lúc tạo manifest.")
        self.execution_versions()
        return self

    def as_index_config(self) -> IndexConfig:
        return IndexConfig(**self.index_config)

    def execution_versions(self) -> SearchExecutionVersions:
        config = self.as_index_config()
        return SearchExecutionVersions(
            model_version=f"{config.model_id}@{config.model_revision}",
            index_version=config.index_version,
            dataset_snapshot=config.dataset_snapshot,
            config_version=self.retrieval_config.config_version,
        )

    def make_store(self, client: QdrantClient) -> QdrantStore:
        """Dựng adapter, không gọi server hoặc tạo collection."""
        return QdrantStore(client, collection_name=self.collection, config=self.as_index_config())

    def check_encoder(self, encoder) -> None:
        config = self.as_index_config()
        actual = (encoder.model_id, encoder.revision, encoder.dimension, encoder.preprocessing_version)
        expected = (config.model_id, config.model_revision, config.dimension, config.preprocessing_version)
        if actual != expected or encoder.model.config.text_config.max_position_embeddings != self.max_text_tokens:
            raise ValueError("Encoder/token limit không khớp index manifest.")

    def verify_input_hashes(self, handoff_root: Path) -> None:
        """Đường dẫn input tính từ gói bàn giao, không phải gốc repository."""
        root = Path(handoff_root).resolve()
        for relative, expected in (
            (self.source_manifest, self.source_manifest_sha256),
            (self.ready_manifest, self.ready_manifest_sha256),
        ):
            path = (root / relative).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError("Input không tồn tại hoặc nằm ngoài thư mục gói.")
            if sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("SHA-256 input không khớp index manifest.")


def load_index_manifest(path: Path) -> IndexManifest:
    return IndexManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def save_index_manifest(manifest: IndexManifest, path: Path) -> None:
    """Ghi file mới, không ghi đè báo cáo/manifest đã có."""
    checked = IndexManifest.model_validate(manifest.model_dump())
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(checked.model_dump(mode="json"), stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
