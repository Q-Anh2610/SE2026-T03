"""Adapter ảnh SigLIP 2 FixRes; pin checkpoint và official image processor."""

from collections.abc import Sequence
from PIL import Image
import torch
from transformers import AutoImageProcessor, AutoModel

from app.embedding.image_encoding import encode_image_batches

MODEL_ID = "google/siglip2-base-patch16-224"
MODEL_REVISION = "75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2"
PREPROCESSING_VERSION = "siglip2-fixres-slow-processor-rgb-l2-v1"


class SigLIP2Encoder:
    def __init__(self, *, device: str = "cpu", local_files_only: bool = False):
        if not isinstance(local_files_only, bool):
            raise ValueError("local_files_only phải là boolean.")
        self.model_id = MODEL_ID
        self.revision = MODEL_REVISION
        self.preprocessing_version = PREPROCESSING_VERSION
        self.device = torch.device(device)
        options = {"local_files_only": True} if local_files_only else {}
        self.processor = AutoImageProcessor.from_pretrained(
            MODEL_ID, revision=MODEL_REVISION, use_fast=False, **options)
        self.model = AutoModel.from_pretrained(MODEL_ID, revision=MODEL_REVISION, **options)
        self.model.to(self.device)
        self.model.eval()
        self.dimension = int(self.model.config.vision_config.hidden_size)

    def encode_images(self, images: Sequence[Image.Image], *, batch_size: int = 8) -> list[list[float]]:
        return encode_image_batches(self, images, batch_size=batch_size)
