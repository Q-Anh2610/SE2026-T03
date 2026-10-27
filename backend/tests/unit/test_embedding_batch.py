"""Kiểm thử batch runner bằng ảnh local và encoder giả."""

from math import sqrt
from unittest.mock import Mock

import pytest
from PIL import Image

from app.embedding.batch import (
    MAX_IMAGE_BYTES,
    MAX_IMAGE_SIDE,
    AssetImage,
    embed_assets,
)


@pytest.fixture
def encoder():
    fake = Mock()
    fake.model_id = "fixture-encoder"
    fake.revision = "fixture-revision"
    fake.dimension = 3
    fake.preprocessing_version = "fixture-rgb-l2-v1"

    def encode(images, *, batch_size):
        vectors = []
        for image in images:
            pixel = image.getpixel((0, 0))
            norm = sqrt(sum(value * value for value in pixel))
            vectors.append([value / norm for value in pixel])
        return vectors

    fake.encode_images.side_effect = encode
    return fake


@pytest.fixture
def make_asset(tmp_path):
    def create(asset_id, color=(3, 4, 0)):
        path = tmp_path / f"{asset_id}.png"
        with Image.new("RGB", (4, 4), color) as image:
            image.save(path)

        return AssetImage(
            metadata={
                "asset_id": asset_id,
                "thumbnail_path": f"https://example.org/{asset_id}.png",
                "ingestion_status": "PENDING",
                "model_version": None,
                "index_version": None,
            },
            image_path=path,
        )

    return create


def test_batches_preserve_order_metadata_and_versions(encoder, make_asset):
    colors = [(3, 4, 0), (0, 0, 8), (5, 0, 12), (0, 7, 0), (8, 15, 0)]
    assets = [
        make_asset(f"asset-{index}", color)
        for index, color in enumerate(colors)
    ]

    report = embed_assets(assets, encoder, batch_size=2)

    assert report.summary == {"embedded": 5, "failed": 0, "skipped": 0}
    assert [item["asset_id"] for item in report.embedded] == [
        asset.metadata["asset_id"] for asset in assets
    ]

    for item, asset, color in zip(
        report.embedded, assets, colors, strict=True
    ):
        norm = sqrt(sum(value * value for value in color))
        assert item["vector"] == pytest.approx(
            [value / norm for value in color]
        )
        assert item["metadata"] == asset.metadata
        assert asset.metadata["ingestion_status"] == "PENDING"
        assert asset.metadata["index_version"] is None

    sizes = [
        len(call.args[0])
        for call in encoder.encode_images.call_args_list
    ]
    assert sizes == [2, 2, 1]
    assert report.versions == {
        "model_id": "fixture-encoder",
        "model_revision": "fixture-revision",
        "dimension": 3,
        "preprocessing_version": "fixture-rgb-l2-v1",
    }


def test_corrupt_and_missing_images_do_not_stop_batch(
    encoder, make_asset, tmp_path
):
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"not an image")

    assets = [
        make_asset("good-1"),
        AssetImage({"asset_id": "corrupt"}, corrupt),
        AssetImage({"asset_id": "missing"}, tmp_path / "missing.png"),
        make_asset("good-2"),
    ]

    report = embed_assets(assets, encoder)

    assert report.summary == {"embedded": 2, "failed": 2, "skipped": 0}
    assert [item["asset_id"] for item in report.embedded] == [
        "good-1", "good-2"
    ]
    assert report.failed == [
        {"asset_id": "corrupt", "code": "image_invalid"},
        {"asset_id": "missing", "code": "image_invalid"},
    ]


def test_duplicate_asset_is_embedded_once(encoder, make_asset):
    asset = make_asset("same")
    report = embed_assets([asset, asset], encoder)

    assert report.summary == {"embedded": 1, "failed": 0, "skipped": 1}
    assert report.skipped == ["same"]


def test_invalid_image_does_not_reserve_asset_id(
    encoder, make_asset, tmp_path
):
    bad = AssetImage({"asset_id": "same"}, tmp_path / "missing.png")
    good = make_asset("same")

    report = embed_assets([bad, good], encoder)

    assert report.summary == {"embedded": 1, "failed": 1, "skipped": 0}
    assert report.embedded[0]["asset_id"] == "same"


def test_inference_failure_isolated_to_bad_asset(encoder, make_asset):
    def encode(images, *, batch_size):
        if any(image.getpixel((0, 0))[0] == 255 for image in images):
            raise RuntimeError("Fixture inference failure")
        return [[0.6, 0.8, 0.0] for _ in images]

    encoder.encode_images.side_effect = encode
    assets = [
        make_asset("good-1"),
        make_asset("bad", (255, 0, 0)),
        make_asset("good-2"),
    ]

    report = embed_assets(assets, encoder)

    assert report.summary == {"embedded": 2, "failed": 1, "skipped": 0}
    assert [item["asset_id"] for item in report.embedded] == [
        "good-1", "good-2"
    ]
    assert report.failed == [
        {"asset_id": "bad", "code": "encoding_failed"}
    ]


def test_missing_vectors_are_reported_as_failures(encoder, make_asset):
    encoder.encode_images.side_effect = lambda images, **kwargs: []

    report = embed_assets(
        [make_asset("first"), make_asset("second")],
        encoder,
    )

    assert report.summary == {"embedded": 0, "failed": 2, "skipped": 0}
    assert all(item["code"] == "encoding_failed" for item in report.failed)


@pytest.mark.parametrize("kind", ["bytes", "dimensions"])
def test_rejects_oversized_images(encoder, make_asset, kind):
    asset = make_asset("large")

    if kind == "bytes":
        asset.image_path.write_bytes(b"x" * (MAX_IMAGE_BYTES + 1))
    else:
        with Image.new("RGB", (MAX_IMAGE_SIDE + 1, 1)) as image:
            image.save(asset.image_path)

    report = embed_assets([asset], encoder)

    assert report.failed == [
        {"asset_id": "large", "code": "image_invalid"}
    ]
    encoder.encode_images.assert_not_called()


@pytest.mark.parametrize("batch_size", [0, -1, True, 1.5, "2", None])
def test_rejects_invalid_batch_size(encoder, batch_size):
    with pytest.raises(ValueError):
        embed_assets([], encoder, batch_size=batch_size)


def test_rejects_invalid_ids(encoder, tmp_path):
    assets = [
        AssetImage({"asset_id": value}, tmp_path / "unused.png")
        for value in (None, "", " ", 123)
    ]

    report = embed_assets(assets, encoder)

    assert report.summary == {"embedded": 0, "failed": 4, "skipped": 0}
    assert all(item["code"] == "invalid_asset_id" for item in report.failed)
    encoder.encode_images.assert_not_called()


def test_empty_input_does_not_run_encoder(encoder):
    report = embed_assets([], encoder)

    assert report.summary == {"embedded": 0, "failed": 0, "skipped": 0}
    encoder.encode_images.assert_not_called()