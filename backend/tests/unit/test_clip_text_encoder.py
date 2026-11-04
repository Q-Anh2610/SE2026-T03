"""Unit tests encode text bằng model giả lập; không tải weights hoặc gọi Qdrant."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import torch
from transformers.feature_extraction_utils import BatchFeature

from app.embedding import clip_encoder as module


@pytest.fixture
def setup_text_encoder(monkeypatch):
    features = torch.zeros((1, 512), dtype=torch.float64)
    features[0, :2] = torch.tensor([3.0, 4.0])

    def process(**kwargs):
        return BatchFeature(
            {
                "input_ids": torch.tensor([[1, 2, 3]]),
                "attention_mask": torch.tensor([[1, 1, 1]]),
            }
        )

    def forward(*, input_ids, attention_mask):
        assert torch.is_inference_mode_enabled()
        assert input_ids.device.type == "cpu"
        assert attention_mask.tolist() == [[1, 1, 1]]
        return features.clone()

    processor = Mock(side_effect=process)
    model = Mock()
    model.config.projection_dim = 512
    model.config.text_config.max_position_embeddings = 77
    model.get_text_features.side_effect = forward
    processor_loader = Mock(return_value=processor)
    model_loader = Mock(return_value=model)
    monkeypatch.setattr(module.CLIPProcessor, "from_pretrained", processor_loader)
    monkeypatch.setattr(module.CLIPModel, "from_pretrained", model_loader)

    return SimpleNamespace(
        encoder=module.CLIPEncoder(),
        processor=processor,
        model=model,
        processor_loader=processor_loader,
        model_loader=model_loader,
    )


def test_text_vector_has_512_finite_l2_normalized_values(setup_text_encoder):
    vector = setup_text_encoder.encoder.encode_text("wooden chair")

    assert isinstance(vector, list)
    assert len(vector) == 512
    assert all(isinstance(value, float) for value in vector)
    assert torch.isfinite(torch.tensor(vector)).all()
    assert vector == pytest.approx([0.6, 0.8] + [0.0] * 510)
    assert sum(value * value for value in vector) == pytest.approx(1.0)


def test_trims_unicode_query_and_requests_checkpoint_truncation(setup_text_encoder):
    setup = setup_text_encoder
    query = "  ghế gỗ  "

    setup.encoder.encode_text(query)

    setup.processor.assert_called_once_with(
        text=["ghế gỗ"],
        padding=True,
        truncation=True,
        max_length=77,
        return_tensors="pt",
    )
    assert query == "  ghế gỗ  "


def test_token_limit_is_read_from_model_config(setup_text_encoder):
    setup = setup_text_encoder
    setup.model.config.text_config.max_position_embeddings = 19

    setup.encoder.encode_text("wooden chair")

    assert setup.processor.call_args.kwargs["max_length"] == 19


def test_repeated_text_queries_reuse_pinned_model_and_processor(setup_text_encoder):
    setup = setup_text_encoder

    setup.encoder.encode_text("chair")
    setup.encoder.encode_text("table")

    setup.model_loader.assert_called_once_with(
        module.MODEL_ID, revision=module.MODEL_REVISION,
    )
    setup.processor_loader.assert_called_once_with(
        module.MODEL_ID, revision=module.MODEL_REVISION, use_fast=False,
    )
    setup.model.to.assert_called_once_with(torch.device("cpu"))
    setup.model.eval.assert_called_once()
    assert setup.model.get_text_features.call_count == 2
    setup.model.get_image_features.assert_not_called()


def test_offline_encoder_passes_local_only_to_both_loaders(setup_text_encoder):
    setup = setup_text_encoder
    setup.processor_loader.reset_mock()
    setup.model_loader.reset_mock()

    module.CLIPEncoder(local_files_only=True)

    setup.processor_loader.assert_called_once_with(
        module.MODEL_ID, revision=module.MODEL_REVISION,
        use_fast=False, local_files_only=True,
    )
    setup.model_loader.assert_called_once_with(
        module.MODEL_ID, revision=module.MODEL_REVISION, local_files_only=True,
    )


@pytest.mark.parametrize("flag", [None, 1, "true"])
def test_offline_flag_must_be_boolean_before_loading(setup_text_encoder, flag):
    setup = setup_text_encoder
    setup.processor_loader.reset_mock()
    setup.model_loader.reset_mock()

    with pytest.raises(ValueError):
        module.CLIPEncoder(local_files_only=flag)

    setup.processor_loader.assert_not_called()
    setup.model_loader.assert_not_called()


@pytest.mark.parametrize("query", [None, 42, True, ["chair"]])
def test_rejects_non_string_before_inference(setup_text_encoder, query):
    setup = setup_text_encoder

    with pytest.raises(TypeError):
        setup.encoder.encode_text(query)

    setup.processor.assert_not_called()
    setup.model.get_text_features.assert_not_called()


@pytest.mark.parametrize("query", ["", " \t\n ", "x" * 501])
def test_rejects_invalid_length_before_inference(setup_text_encoder, query):
    setup = setup_text_encoder

    with pytest.raises(ValueError):
        setup.encoder.encode_text(query)

    setup.processor.assert_not_called()
    setup.model.get_text_features.assert_not_called()


@pytest.mark.parametrize("query", ["  木  ", "  " + "木" * 500 + "  "])
def test_accepts_inclusive_unicode_length_bounds_after_trim(setup_text_encoder, query):
    setup = setup_text_encoder

    setup.encoder.encode_text(query)

    assert setup.processor.call_args.kwargs["text"] == [query.strip()]


@pytest.mark.parametrize(
    "features",
    [
        torch.zeros((1, 512)),
        torch.full((1, 512), float("nan")),
        torch.full((1, 512), float("inf")),
        torch.full((1, 512), 3e38),
        torch.ones((1, 511)),
        torch.ones((2, 512)),
        torch.ones(512),
    ],
    ids=["zero", "nan", "infinity", "overflow-norm", "dimension", "batch", "shape"],
)
def test_rejects_invalid_text_model_output(setup_text_encoder, features):
    setup = setup_text_encoder
    setup.model.get_text_features.side_effect = lambda **kwargs: features

    with pytest.raises(RuntimeError):
        setup.encoder.encode_text("chair")
