"""Encoder CLIP dùng chung cho pipeline batch."""

from collections.abc import Sequence

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor


MODEL_ID = "openai/clip-vit-base-patch32"
MODEL_REVISION = "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"
PREPROCESSING_VERSION = "clip-slow-processor-rgb-l2-v1"


class CLIPEncoder:
    """Tạo một encoder rồi tái sử dụng cho các batch trong tiến trình."""

    def __init__(self, *, device: str = "cpu") -> None:
        self.model_id = MODEL_ID
        self.revision = MODEL_REVISION
        self.preprocessing_version = PREPROCESSING_VERSION
        self.device = torch.device(device)

        self.processor = CLIPProcessor.from_pretrained(
            self.model_id,
            revision=self.revision,
            use_fast=False,
        )
        self.model = CLIPModel.from_pretrained(
            self.model_id,
            revision=self.revision,
        )
        self.model.to(self.device)
        self.model.eval()
        self.dimension = int(self.model.config.projection_dim)

    @torch.inference_mode()
    def encode_images(
        self,
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
                inputs = self.processor(
                    images=batch,
                    return_tensors="pt",
                ).to(self.device)

                features = self.model.get_image_features(**inputs).float()

                if features.shape != (len(batch), self.dimension):
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