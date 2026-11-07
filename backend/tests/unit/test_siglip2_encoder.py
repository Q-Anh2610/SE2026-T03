"""Adapter SigLIP 2 với loader/model giả lập; không tải weights."""

from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import torch
from PIL import Image
from transformers.feature_extraction_utils import BatchFeature
from app.embedding import siglip2_encoder as module


@pytest.fixture
def setup(monkeypatch):
    processor = Mock(side_effect=lambda **kw: BatchFeature({"pixel_values": torch.tensor(
        [image.getpixel((0, 0)) for image in kw["images"]], dtype=torch.float32)}))
    def forward(**kw):
        assert torch.is_inference_mode_enabled()
        return kw["pixel_values"]
    model = Mock()
    model.config.vision_config.hidden_size = 3
    model.get_image_features.side_effect = forward
    pl, ml = Mock(return_value=processor), Mock(return_value=model)
    monkeypatch.setattr(module.AutoImageProcessor, "from_pretrained", pl)
    monkeypatch.setattr(module.AutoModel, "from_pretrained", ml)
    return SimpleNamespace(processor=processor, model=model, pl=pl, ml=ml)


def test_pins_fixres_model_processor_and_reuses_once(setup):
    encoder = module.SigLIP2Encoder(local_files_only=True)
    with Image.new("RGB", (2, 2), (3, 4, 0)) as image:
        a = encoder.encode_images([image, image, image], batch_size=2)
        b = encoder.encode_images([image])
        assert image.getpixel((0, 0)) == (3, 4, 0)
    assert a == [b[0]] * 3
    assert b[0] == pytest.approx([0.6, 0.8, 0])
    setup.pl.assert_called_once_with(module.MODEL_ID, revision=module.MODEL_REVISION,
                                    use_fast=False, local_files_only=True)
    setup.ml.assert_called_once_with(module.MODEL_ID, revision=module.MODEL_REVISION, local_files_only=True)
    setup.model.eval.assert_called_once()
    assert [len(c.kwargs["images"]) for c in setup.processor.call_args_list] == [2, 1, 1]


@pytest.mark.parametrize("value", [None, 1, "true"])
def test_offline_flag_rejected_before_loading(setup, value):
    with pytest.raises(ValueError):
        module.SigLIP2Encoder(local_files_only=value)
    setup.pl.assert_not_called()
    setup.ml.assert_not_called()


@pytest.mark.parametrize("features", [torch.zeros((1, 3)), torch.ones((1, 2)),
    torch.full((1, 3), float("nan")), torch.full((1, 3), float("inf"))])
def test_invalid_features(setup, features):
    encoder = module.SigLIP2Encoder()
    setup.model.get_image_features.side_effect = lambda **kw: features
    with Image.new("RGB", (2, 2)) as image:
        with pytest.raises(RuntimeError):
            encoder.encode_images([image])
