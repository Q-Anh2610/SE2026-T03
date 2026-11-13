"""Fixture E5 có attention mask thật; không nạp weights hoặc gọi mạng."""

from math import sqrt
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import torch
from transformers.tokenization_utils_base import BatchEncoding

from app.embedding import e5_encoder as module


@pytest.fixture
def setup(monkeypatch):
    def tokenize(texts, **kwargs):
        ids = [int(text[-1]) if text[-1].isdigit() else 4 for text in texts]
        return BatchEncoding({
            "input_ids": torch.tensor([[value, 2, 0] for value in ids]),
            "attention_mask": torch.tensor([[1, 1, 0] for _ in ids]),
        })

    def forward(input_ids, attention_mask):
        assert torch.is_inference_mode_enabled()
        assert input_ids.device.type == "cpu"
        hidden = torch.zeros((len(input_ids), 3, 384), dtype=torch.float64)
        hidden[:, 0, 0] = 3.0
        hidden[:, 1, 1] = input_ids[:, 0]
        hidden[:, 2, :] = float("nan")  # Padding không được lọt vào pooled vector.
        return SimpleNamespace(last_hidden_state=hidden)

    tokenizer = Mock(side_effect=tokenize)
    tokenizer.is_fast = True
    model = Mock(side_effect=forward)
    model.config.hidden_size = 384
    model.config.max_position_embeddings = 512
    tokenizer_loader, model_loader = Mock(return_value=tokenizer), Mock(return_value=model)
    monkeypatch.setattr(module.AutoTokenizer, "from_pretrained", tokenizer_loader)
    monkeypatch.setattr(module.AutoModel, "from_pretrained", model_loader)
    return SimpleNamespace(
        encoder=module.E5Encoder(), tokenizer=tokenizer, model=model,
        tokenizer_loader=tokenizer_loader, model_loader=model_loader,
    )


def test_masked_mean_l2_ignores_nan_padding_and_returns_finite_384_vector(setup):
    vector = setup.encoder.encode_text("chair")
    assert vector == pytest.approx([0.6, 0.8] + [0.0] * 382)
    assert all(isinstance(value, float) for value in vector)
    assert sum(value * value for value in vector) == pytest.approx(1.0)


def test_query_and_passage_use_distinct_prefixes_and_checkpoint_truncation(setup):
    setup.encoder.encode_text("  ghế gỗ  ")
    setup.encoder.encode_passages(["  original metadata  "])
    assert [call.args[0] for call in setup.tokenizer.call_args_list] == [
        ["query: ghế gỗ"], ["passage: original metadata"]]
    for call in setup.tokenizer.call_args_list:
        assert call.kwargs == {
            "max_length": 512, "padding": True,
            "truncation": True, "return_tensors": "pt"}


def test_pins_model_tokenizer_and_loads_once_offline_by_default(setup):
    setup.encoder.encode_text("chair")
    setup.encoder.encode_text("table")
    setup.encoder.encode_passages(["original metadata"])
    setup.tokenizer_loader.assert_called_once_with(
        module.MODEL_ID, revision=module.MODEL_REVISION, use_fast=True,
        padding_side="right", truncation_side="right", local_files_only=True)
    setup.model_loader.assert_called_once_with(
        module.MODEL_ID, revision=module.MODEL_REVISION,
        use_safetensors=True, local_files_only=True)
    setup.model.to.assert_called_once_with(torch.device("cpu"))
    setup.model.eval.assert_called_once()
    assert setup.model.call_count == 3
    assert setup.encoder.tokenizer_revision == setup.encoder.revision


def test_explicit_online_opt_in_is_forwarded_to_both_loaders(setup):
    module.E5Encoder(local_files_only=False)
    assert setup.model_loader.call_args.kwargs["local_files_only"] is False
    assert setup.tokenizer_loader.call_args.kwargs["local_files_only"] is False


def test_batching_keeps_order_and_matches_single_passages_without_mutation(setup):
    passages = [" item1 ", "item2", "item3"]
    vectors = setup.encoder.encode_passages(passages, batch_size=2)
    assert [len(call.args[0]) for call in setup.tokenizer.call_args_list] == [2, 1]
    for value, vector in enumerate(vectors, start=1):
        norm = sqrt(9 + value * value)
        assert vector == pytest.approx([3 / norm, value / norm] + [0.0] * 382)
        assert vector == setup.encoder.encode_passages([passages[value - 1]])[0]
    assert passages == [" item1 ", "item2", "item3"]


def test_empty_passage_sequence_does_not_run_inference(setup):
    assert setup.encoder.encode_passages([]) == []
    setup.tokenizer.assert_not_called()
    setup.model.assert_not_called()


@pytest.mark.parametrize("passages", ["text", b"text", None, [None], ["ok", 1]])
def test_invalid_passage_types_rejected_before_inference(setup, passages):
    with pytest.raises(TypeError):
        setup.encoder.encode_passages(passages)
    setup.tokenizer.assert_not_called()


@pytest.mark.parametrize("passages", [[""], ["ok", " \t\n"]])
def test_missing_metadata_is_not_silently_encoded_or_skipped(setup, passages):
    with pytest.raises(ValueError):
        setup.encoder.encode_passages(passages, batch_size=1)
    setup.tokenizer.assert_not_called()


@pytest.mark.parametrize("size", [True, False, 0, -1, 1.5, "2", None])
def test_invalid_batch_size_rejected_even_for_empty_input(setup, size):
    with pytest.raises(ValueError):
        setup.encoder.encode_passages([], batch_size=size)
    setup.tokenizer.assert_not_called()


@pytest.mark.parametrize("query", [None, 1, True, ["chair"]])
def test_invalid_query_type_rejected_before_inference(setup, query):
    with pytest.raises(TypeError):
        setup.encoder.encode_text(query)
    setup.tokenizer.assert_not_called()


@pytest.mark.parametrize("query", ["", " \t\n", "x" * 501])
def test_invalid_query_length_rejected_before_inference(setup, query):
    with pytest.raises(ValueError):
        setup.encoder.encode_text(query)
    setup.tokenizer.assert_not_called()


@pytest.mark.parametrize("query", [" 木 ", " " + "木" * 500 + " "])
def test_inclusive_query_length_bounds_and_unicode(setup, query):
    setup.encoder.encode_text(query)
    assert setup.tokenizer.call_args.args[0] == ["query: " + query.strip()]


@pytest.mark.parametrize("flag", [None, 0, 1, "true"])
def test_invalid_offline_option_rejected_before_loading(setup, flag):
    setup.tokenizer_loader.reset_mock()
    setup.model_loader.reset_mock()
    with pytest.raises(ValueError):
        module.E5Encoder(local_files_only=flag)
    setup.tokenizer_loader.assert_not_called()
    setup.model_loader.assert_not_called()


@pytest.mark.parametrize("shape", [(1, 3, 383), (2, 3, 384), (1, 2, 384), (384,)])
def test_incompatible_hidden_shape_rejected(setup, shape):
    setup.model.side_effect = lambda **kwargs: SimpleNamespace(last_hidden_state=torch.ones(shape))
    with pytest.raises(RuntimeError):
        setup.encoder.encode_text("chair")


@pytest.mark.parametrize("value", [0.0, float("nan"), float("inf"), 3e38])
def test_invalid_pooled_vectors_rejected(setup, value):
    setup.model.side_effect = lambda **kwargs: SimpleNamespace(
        last_hidden_state=torch.full((1, 3, 384), value))
    with pytest.raises(RuntimeError):
        setup.encoder.encode_text("chair")


@pytest.mark.parametrize("mask", [[[0, 0, 0]], [[1, -1, 0]], [[1, 2, 0]], [[1, 1]]])
def test_invalid_attention_mask_rejected_without_dividing_by_zero(setup, mask):
    setup.tokenizer.side_effect = lambda *args, **kwargs: BatchEncoding({
        "input_ids": torch.tensor([[1, 2, 0]]), "attention_mask": torch.tensor(mask)})
    with pytest.raises(RuntimeError):
        setup.encoder.encode_text("chair")


@pytest.mark.parametrize("field,value", [("hidden_size", 383), ("max_position_embeddings", 511)])
def test_incompatible_checkpoint_config_rejected(setup, field, value):
    setattr(setup.model.config, field, value)
    with pytest.raises(ValueError):
        module.E5Encoder()


def test_slow_tokenizer_is_not_silently_substituted(setup):
    setup.tokenizer.is_fast = False
    setup.model_loader.reset_mock()
    with pytest.raises(ValueError):
        module.E5Encoder()
    setup.model_loader.assert_not_called()


def test_dependency_failure_propagates_instead_of_fake_embedding(setup):
    setup.model.side_effect = OSError("fixture dependency unavailable")
    with pytest.raises(OSError):
        setup.encoder.encode_text("chair")
