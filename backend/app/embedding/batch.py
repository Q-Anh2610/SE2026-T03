"""Batch embedding cho ảnh local đã được ingestion bàn giao."""

from collections.abc import Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from .clip_encoder import CLIPEncoder


MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_SIDE = 4096


@dataclass(frozen=True)
class AssetImage:
    metadata: dict[str, Any]
    image_path: Path


@dataclass
class BatchReport:
    versions: dict[str, str | int]
    embedded: list[dict[str, Any]] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "embedded": len(self.embedded),
            "failed": len(self.failed),
            "skipped": len(self.skipped),
        }


def _read_image(path: Path) -> Image.Image:
    """Decode ảnh thật, giới hạn kích thước trước khi nạp pixel."""
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError("Ảnh vượt giới hạn dung lượng.")

    with Image.open(path) as image:
        if max(image.size) > MAX_IMAGE_SIDE:
            raise ValueError("Ảnh vượt giới hạn kích thước.")

        image.load()
        return image.convert("RGB")


def embed_assets(
    assets: Sequence[AssetImage],
    encoder: CLIPEncoder,
    *,
    batch_size: int = 8,
) -> BatchReport:
    """Tạo embeddings; chưa ghi Qdrant hoặc đổi trạng thái searchable."""
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or batch_size < 1
    ):
        raise ValueError("batch_size phải là số nguyên dương.")

    report = BatchReport(
        versions={
            "model_id": encoder.model_id,
            "model_revision": encoder.revision,
            "dimension": encoder.dimension,
            "preprocessing_version": encoder.preprocessing_version,
        }
    )
    seen: set[str] = set()

    def encode_group(group: list[tuple[AssetImage, Image.Image]]) -> None:
        try:
            vectors = encoder.encode_images(
                [image for _, image in group],
                batch_size=batch_size,
            )
            if len(vectors) != len(group):
                raise RuntimeError("Số vector không khớp số asset.")
        except (RuntimeError, ValueError, TypeError):
            if len(group) > 1:
                # Tách thành từng ảnh để asset lỗi không làm mất cả batch.
                for item in group:
                    encode_group([item])
            else:
                asset = group[0][0]
                report.failed.append(
                    {
                        "asset_id": asset.metadata["asset_id"],
                        "code": "encoding_failed",
                    }
                )
            return

        for (asset, _), vector in zip(group, vectors, strict=True):
            report.embedded.append(
                {
                    "asset_id": asset.metadata["asset_id"],
                    "metadata": dict(asset.metadata),
                    "vector": vector,
                }
            )

    for start in range(0, len(assets), batch_size):
        with ExitStack() as stack:
            group: list[tuple[AssetImage, Image.Image]] = []

            for asset in assets[start : start + batch_size]:
                asset_id = asset.metadata.get("asset_id")

                if not isinstance(asset_id, str) or not asset_id.strip():
                    report.failed.append(
                        {"asset_id": None, "code": "invalid_asset_id"}
                    )
                    continue

                if asset_id in seen:
                    report.skipped.append(asset_id)
                    continue

                try:
                    image = _read_image(Path(asset.image_path))
                    image = stack.enter_context(image)
                except (
                    OSError,
                    ValueError,
                    TypeError,
                    Image.DecompressionBombError,
                ):
                    report.failed.append(
                        {"asset_id": asset_id, "code": "image_invalid"}
                    )
                    continue

                seen.add(asset_id)
                group.append((asset, image))

            if group:
                encode_group(group)

    return report