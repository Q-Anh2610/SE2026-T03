"""Unit tests offline cho CLIPEncoder."""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import torch
from PIL import Image
from transformers.feature_extraction_utils import BatchFeature

from app.embedding import clip_encoder as module


@pytest.fixture
def setup_encoder(monkeypatch):
    def process(*, images, return_tensors):
        assert return_tensors == "pt"
        assert all(image.mode == "RGB" for image in images)
        pixels = [image.getpixel((0, 0)) for image in images]
        return BatchFeature(
            {"pixel_values": torch.tensor(pixels, dtype=torch.float32)}
        )

    def forward(*, pixel_values):
        assert torch.is_inference_mode_enabled()
        return pixel_values.clone()

    processor = Mock(side_effect=process)
    model = Mock()
    model.config.projection_dim = 3
    model.get_image_features.side_effect = forward

    processor_loader = Mock(return_value=processor)
    model_loader = Mock(return_value=model)

    monkeypatch.setattr(
        module.CLIPProcessor, "from_pretrained", processor_loader
    )
    monkeypatch.setattr(
        module.CLIPModel, "from_pretrained", model_loader
    )

    return SimpleNamespace(
        encoder=module.CLIPEncoder(),
        processor=processor,
        model=model,
        processor_loader=processor_loader,
        model_loader=model_loader,
    )


def test_reuses_model_and_pins_matching_revision(setup_encoder):
    setup = setup_encoder

    with Image.new("RGB", (2, 2), (3, 4, 0)) as image:
        setup.encoder.encode_images([image])
        setup.encoder.encode_images([image])

    setup.model_loader.assert_called_once_with(
        module.MODEL_ID,
        revision=module.MODEL_REVISION,
    )
    setup.processor_loader.assert_called_once_with(
        module.MODEL_ID,
        revision=module.MODEL_REVISION,
        use_fast=False,
    )
    setup.model.eval.assert_called_once()
    assert setup.model.get_image_features.call_count == 2


def test_batches_preserve_order_and_normalize_vectors(setup_encoder):
    setup = setup_encoder
    colors = [(3, 4, 0), (0, 0, 8), (5, 0, 12), (0, 7, 0), (8, 15, 0)]
    expected = [
        [0.6, 0.8, 0.0],
        [0.0, 0.0, 1.0],
        [5 / 13, 0.0, 12 / 13],
        [0.0, 1.0, 0.0],
        [8 / 17, 15 / 17, 0.0],
    ]

    with ExitStack() as stack:
        images = [
            stack.enter_context(Image.new("RGB", (2, 2), color))
            for color in colors
        ]
        vectors = setup.encoder.encode_images(images, batch_size=2)

        # Ảnh gốc vẫn sử dụng được sau khi encode.
        assert [image.getpixel((0, 0)) for image in images] == colors

    assert len(vectors) == len(expected)
    for actual, wanted in zip(vectors, expected, strict=True):
        assert actual == pytest.approx(wanted)
        assert sum(value**2 for value in actual) == pytest.approx(1.0)

    batch_sizes = [
        len(call.kwargs["images"])
        for call in setup.processor.call_args_list
    ]
    assert batch_sizes == [2, 2, 1]


def test_converts_grayscale_to_rgb(setup_encoder):
    with Image.new("L", (2, 2), 10) as image:
        vectors = setup_encoder.encoder.encode_images([image])

    assert vectors[0] == pytest.approx([1 / (3**0.5)] * 3)


def test_empty_input_does_not_run_inference(setup_encoder):
    setup = setup_encoder

    assert setup.encoder.encode_images([]) == []
    setup.processor.assert_not_called()
    setup.model.get_image_features.assert_not_called()


@pytest.mark.parametrize("batch_size", [0, -1, True, 1.5, "2", None])
def test_rejects_invalid_batch_size(setup_encoder, batch_size):
    with pytest.raises(ValueError):
        setup_encoder.encoder.encode_images([], batch_size=batch_size)


def test_rejects_non_image_input(setup_encoder):
    with pytest.raises(TypeError):
        setup_encoder.encoder.encode_images([object()])

    setup_encoder.processor.assert_not_called()


@pytest.mark.parametrize(
    "features",
    [
        torch.zeros((1, 3)),
        torch.tensor([[float("nan"), 1.0, 0.0]]),
        torch.tensor([[float("inf"), 1.0, 0.0]]),
        torch.ones((1, 2)),
    ],
    ids=["zero-vector", "nan", "infinity", "wrong-dimension"],
)
def test_rejects_invalid_model_output(setup_encoder, features):
    setup_encoder.model.get_image_features.side_effect = (
        lambda **kwargs: features
    )

    with Image.new("RGB", (2, 2), (3, 4, 0)) as image:
        with pytest.raises(RuntimeError):
            setup_encoder.encoder.encode_images([image])