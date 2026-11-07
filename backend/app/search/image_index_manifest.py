"""Manifest ảnh riêng theo model; không thay schema/index manifest W3."""

from dataclasses import asdict
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator
from app.schemas.text_search import SearchExecutionVersions
from app.search.image_search import ImageRetrievalConfig
from app.search.index_manifest import _portable_path
from app.search.qdrant_store import IndexConfig, QdrantStore, index_vector_name


class ImageIndexManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["image-index-manifest-v1"] = "image-index-manifest-v1"
    created_at_utc: datetime
    observed_at_utc: datetime
    index_config: dict[str, StrictStr | StrictInt]
    collection: str = Field(min_length=1)
    vector_name: str = Field(min_length=1)
    processor_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    processor_class: str = Field(min_length=1)
    processor_config: dict = Field(min_length=1)
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
    snapshot_confirmation: str = Field(min_length=1)
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    working_tree_dirty: StrictBool
    module_sha256: dict[str, str] = Field(min_length=1)
    package_versions: dict[str, str] = Field(min_length=1)
    retrieval_config: ImageRetrievalConfig

    @field_validator("index_config", mode="before")
    @classmethod
    def canonical_config(cls, value):
        if not isinstance(value, dict):
            raise ValueError("index_config phải là object.")
        try:
            return asdict(IndexConfig(**value))
        except (TypeError, ValueError):
            raise ValueError("index_config không hợp lệ.") from None

    @field_validator("source_manifest", "ready_manifest")
    @classmethod
    def portable_path(cls, value):
        return _portable_path(value)

    @field_validator("created_at_utc", "observed_at_utc")
    @classmethod
    def utc(cls, value):
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("Thời điểm cần timezone UTC.")
        return value

    @field_validator("module_sha256")
    @classmethod
    def portable_hashes(cls, value):
        import re
        for path, digest in value.items():
            _portable_path(path)
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Module hash phải là SHA-256.")
        return value

    @model_validator(mode="after")
    def compatible_fields(self) -> Self:
        config = self.as_index_config()
        if self.vector_name != index_vector_name(config):
            raise ValueError("Named vector không khớp index.")
        if self.processor_revision != config.model_revision:
            raise ValueError("Model và processor cần cùng pinned revision.")
        if not config.dataset_snapshot.endswith("sha256:" + self.source_manifest_sha256):
            raise ValueError("Snapshot không khớp manifest nguồn.")
        if self.point_count != self.asset_count:
            raise ValueError("Single-preview cần một point cho mỗi asset.")
        if self.observed_at_utc > self.created_at_utc:
            raise ValueError("Thời điểm quan sát không hợp lệ.")
        self.execution_versions()
        return self

    def as_index_config(self) -> IndexConfig:
        return IndexConfig(**self.index_config)

    def execution_versions(self) -> SearchExecutionVersions:
        config = self.as_index_config()
        return SearchExecutionVersions(
            model_version=f"{config.model_id}@{config.model_revision}",
            index_version=config.index_version, dataset_snapshot=config.dataset_snapshot,
            config_version=self.retrieval_config.config_version)

    def make_store(self, client) -> QdrantStore:
        return QdrantStore(client, collection_name=self.collection, config=self.as_index_config())

    def check_encoder(self, encoder):
        config = self.as_index_config()
        actual = (encoder.model_id, encoder.revision, encoder.dimension, encoder.preprocessing_version)
        expected = (config.model_id, config.model_revision, config.dimension, config.preprocessing_version)
        processor = getattr(encoder.processor, "image_processor", encoder.processor)
        if (actual != expected or type(processor).__name__ != self.processor_class
                or processor.to_dict() != self.processor_config):
            raise ValueError("Encoder/processor không khớp manifest.")

    def verify_input_hashes(self, root: Path):
        root = Path(root).resolve()
        for relative, digest in ((self.source_manifest, self.source_manifest_sha256),
                                 (self.ready_manifest, self.ready_manifest_sha256)):
            path = (root / relative).resolve()
            if (not path.is_relative_to(root) or not path.is_file()
                    or sha256(path.read_bytes()).hexdigest() != digest):
                raise ValueError("Input nằm ngoài gói hoặc checksum không khớp.")


def save_image_index_manifest(manifest: ImageIndexManifest, path: Path):
    checked = ImageIndexManifest.model_validate(manifest.model_dump())
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(checked.model_dump(mode="json"), stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def load_image_index_manifest(path: Path) -> ImageIndexManifest:
    return ImageIndexManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def require_same_image_inputs(first: ImageIndexManifest, second: ImageIndexManifest) -> None:
    """So sánh provenance/cutoff trước khi so CLIP với SigLIP 2; không so scores."""
    a = (first.as_index_config().dataset_snapshot, first.source_manifest_sha256,
         first.ready_manifest_sha256, first.asset_count, first.retrieval_config)
    b = (second.as_index_config().dataset_snapshot, second.source_manifest_sha256,
         second.ready_manifest_sha256, second.asset_count, second.retrieval_config)
    if a != b:
        raise ValueError("Hai index không cùng snapshot/preview/retrieval policy.")
