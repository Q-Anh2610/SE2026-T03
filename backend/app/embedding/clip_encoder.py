"""Encoder CLIP dùng chung cho pipeline batch."""

from collections.abc import Sequence

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from app.embedding.image_encoding import encode_image_batches


MODEL_ID = "openai/clip-vit-base-patch32"
MODEL_REVISION = "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"
PREPROCESSING_VERSION = "clip-slow-processor-rgb-l2-v1"


class CLIPEncoder:
    """Tạo một encoder rồi tái sử dụng cho các batch trong tiến trình."""

    def __init__(
        self, *, device: str = "cpu", local_files_only: bool = False,
    ) -> None:
        if not isinstance(local_files_only, bool):
            raise ValueError("local_files_only phải là boolean.")
        self.model_id = MODEL_ID
        self.revision = MODEL_REVISION
        self.preprocessing_version = PREPROCESSING_VERSION
        self.device = torch.device(device)

        loader_options = {"local_files_only": True} if local_files_only else {}
        self.processor = CLIPProcessor.from_pretrained(
            self.model_id,
            revision=self.revision,
            use_fast=False,
            **loader_options,
        )
        self.model = CLIPModel.from_pretrained(
            self.model_id,
            revision=self.revision,
            **loader_options,
        )
        self.model.to(self.device)
        self.model.eval()
        self.dimension = int(self.model.config.projection_dim)

    def encode_images(
        self, images: Sequence[Image.Image], *, batch_size: int = 8,
    ) -> list[list[float]]:
        """Trả vector L2 theo thứ tự ảnh, giữ nguyên preprocessing W3."""
        return encode_image_batches(self, images, batch_size=batch_size)

    @torch.inference_mode()
    def encode_text(self, query: str) -> list[float]:
        """Mã hóa query; truncate theo giới hạn token của checkpoint."""
        if not isinstance(query, str):
            raise TypeError("query phải là chuỗi.")

        query = query.strip()
        if not 1 <= len(query) <= 500:
            raise ValueError("query sau trim phải có từ 1 đến 500 ký tự.")

        inputs = self.processor(
            text=[query],
            padding=True,
            truncation=True,
            max_length=self.model.config.text_config.max_position_embeddings,
            return_tensors="pt",
        ).to(self.device)

        features = self.model.get_text_features(**inputs).float()

        if features.shape != (1, self.dimension):
            raise RuntimeError("Kích thước text embedding không hợp lệ.")

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
            raise RuntimeError("Text embedding chứa vector không hợp lệ.")

        normalized = features / norms
        return normalized[0].cpu().tolist()
