"""Kiểm tra filters với Qdrant trong bộ nhớ; không chạm collection thật."""

import pytest
from pydantic import ValidationError
from qdrant_client import QdrantClient, models

from app.schemas.text_search import TextSearchFilters
from app.search.filters import build_qdrant_filter


@pytest.fixture
def filter_index():
    # Metadata và vectors tự tạo cho test, không phải kết quả CLIP thật.
    base = dict(category="chair", license="cc-by", formats=["glb"], face_count=100)
    records = [
        ("chair-low", {**base, "formats": ["obj", "glb"]}),
        ("chair-high", {**base, "formats": ["obj"], "face_count": 200}),
        ("table", {**base, "category": "table", "license": "cc0", "face_count": 300}),
        ("case-chair", {**base, "category": "Chair"}),
        ("different-license", {**base, "license": "cc-by-sa", "face_count": 0}),
        ("nulls", dict.fromkeys(base)),
        ("missing", {}),
        ("no-formats", {**base, "formats": [], "face_count": 150}),
        ("no-count", {**base, "face_count": None}),
    ]
    client = QdrantClient(location=":memory:")
    try:
        client.create_collection(
            collection_name="filter_fixtures",
            vectors_config={
                "preview": models.VectorParams(size=3, distance=models.Distance.COSINE)
            },
        )
        client.upsert(
            collection_name="filter_fixtures",
            points=[
                models.PointStruct(
                    id=index,
                    vector={
                        "preview": (
                            [0.6, 0.8, 0.0]
                            if asset_id == "chair-low" else [1.0, 0.0, 0.0]
                        )
                    },
                    payload={"asset_id": asset_id, **metadata},
                )
                for index, (asset_id, metadata) in enumerate(records)
            ],
            wait=True,
        )
        yield client
    finally:
        client.close()


def query(client, filters, *, limit=20):
    return client.query_points(
        collection_name="filter_fixtures",
        query=[1.0, 0.0, 0.0],
        using="preview",
        query_filter=build_qdrant_filter(filters),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    ).points


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        (
            {"category": "chair"},
            {"chair-low", "chair-high", "different-license", "no-formats", "no-count"},
        ),
        (
            {"license": "cc-by"},
            {"chair-low", "chair-high", "case-chair", "no-formats", "no-count"},
        ),
        (
            {"format": "glb"},
            {"chair-low", "table", "case-chair", "different-license", "no-count"},
        ),
        (
            {"face_count_min": 100},
            {"chair-low", "chair-high", "table", "case-chair", "no-formats"},
        ),
        (
            {"face_count_max": 100},
            {"chair-low", "case-chair", "different-license"},
        ),
        (
            {"face_count_min": 100, "face_count_max": 200},
            {"chair-low", "chair-high", "case-chair", "no-formats"},
        ),
        ({"face_count_min": 200, "face_count_max": 200}, {"chair-high"}),
        ({"face_count_min": 0, "face_count_max": 0}, {"different-license"}),
        ({"category": "Chair"}, {"case-chair"}),
        ({"category": "CHAIR"}, set()),
        ({"license": "cc"}, set()),
        ({"format": "GLB"}, set()),
        ({"category": "table", "license": "cc-by"}, set()),
        ({"category": "absent"}, set()),
    ],
)
def test_individual_and_combined_filters_match_expected_assets(
    filter_index, filters, expected,
):
    hits = query(filter_index, filters)

    assert {hit.payload["asset_id"] for hit in hits} == expected


@pytest.mark.parametrize(
    "filters",
    [{}, {
        "category": None,
        "license": None,
        "format": None,
        "face_count_min": None,
        "face_count_max": None,
    }],
)
def test_absent_filters_keep_null_and_missing_metadata(filter_index, filters):
    assert build_qdrant_filter(filters) is None
    hits = query(filter_index, filters)

    assert len(hits) == 9
    assert {"nulls", "missing", "no-count"}.issubset(
        {hit.payload["asset_id"] for hit in hits}
    )


def test_all_filters_apply_before_top_one_without_changing_index(filter_index):
    filters = TextSearchFilters(
        category="  chair  ",
        license=" cc-by ",
        format=" glb ",
        face_count_min=100,
        face_count_max=100,
    )
    before = filter_index.count("filter_fixtures", exact=True).count
    hits = query(filter_index, filters, limit=1)

    # chair-low có score thấp hơn các asset không khớp; vẫn phải xuất hiện.
    assert [hit.payload["asset_id"] for hit in hits] == ["chair-low"]
    assert hits[0].score == pytest.approx(0.6)
    assert filter_index.count("filter_fixtures", exact=True).count == before
    assert filters.category == "chair"


@pytest.mark.parametrize(
    "filters",
    [
        {"category": " "},
        {"license": ""},
        {"format": ""},
        {"face_count_min": True},
        {"face_count_max": "100"},
        {"face_count_min": 1.5},
        {"face_count_max": -1},
        {"face_count_min": 200, "face_count_max": 100},
        {"formats": ["glb"]},
        {"unknown": "value"},
    ],
)
def test_invalid_filter_is_rejected_instead_of_silently_ignored(filters):
    with pytest.raises(ValidationError):
        build_qdrant_filter(filters)


def test_modified_schema_instance_is_revalidated():
    filters = TextSearchFilters()
    filters.face_count_min = True

    with pytest.raises(ValidationError):
        build_qdrant_filter(filters)
