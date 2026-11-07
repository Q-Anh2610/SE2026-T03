"""Batch RGB/L2 dùng chung cho CLIP và SigLIP 2; không nạp model."""

from collections.abc import Sequence
import torch
from PIL import Image


@torch.inference_mode()
def encode_image_batches(
    encoder,
    images: Sequence[Image.Image],
    *,
    batch_size: int = 8,
) -> list[list[float]]:
    """Trả vector L2 chuẩn hóa, giữ nguyên thứ tự ảnh đầu vào."""
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or batch_size < 1
    ):
        raise ValueError("batch_size phải là số nguyên dương.")

    if any(not isinstance(image, Image.Image) for image in images):
        raise TypeError("Mỗi phần tử đầu vào phải là ảnh PIL.")

    vectors: list[list[float]] = []

    for start in range(0, len(images), batch_size):
        batch = [
            image.convert("RGB")
            for image in images[start : start + batch_size]
        ]

        try:
            inputs = encoder.processor(
                images=batch,
                return_tensors="pt",
            ).to(encoder.device)

            features = encoder.model.get_image_features(**inputs).float()

            if features.shape != (len(batch), encoder.dimension):
                raise RuntimeError("Kích thước embedding không hợp lệ.")

            norms = torch.linalg.vector_norm(
                features,
                dim=-1,
                keepdim=True,
            )

            if (
                not torch.isfinite(features).all()
                or not torch.isfinite(norms).all()
                or torch.any(norms <= 0)
            ):
                raise RuntimeError("Embedding chứa vector không hợp lệ.")

            normalized = features / norms
            vectors.extend(normalized.cpu().tolist())
        finally:
            for image in batch:
                image.close()

    return vectors
