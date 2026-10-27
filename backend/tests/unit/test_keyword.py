"""Tests keyword baseline bằng metadata tự tạo."""

import unicodedata

import pytest

from app.search.keyword import KeywordBaseline


@pytest.fixture
def assets():
    return [
        {
            "asset_id": "asset-b",
            "name": "Wooden chair",
            "description": "Dining furniture",
            "tags": ["oak"],
        },
        {
            "asset_id": "asset-a",
            "name": "Chair",
            "description": "A wooden seat",
            "tags": [],
        },
        {
            "asset_id": "asset-c",
            "name": "Metal stool",
            "description": None,
            "tags": ["chair"],
        },
    ]


def test_ranking_counts_distinct_query_terms(assets):
    baseline = KeywordBaseline(assets)

    results = baseline.search("  WOODEN chair chair  ")

    assert [item["asset"]["asset_id"] for item in results] == [
        "asset-a", "asset-b", "asset-c"
    ]
    assert [item["score"] for item in results] == [2, 2, 1]
    assert [item["rank"] for item in results] == [1, 2, 3]
    assert all(
        item["retrieval_sources"] == ["keyword_metadata"]
        for item in results
    )
    assert "chair" in results[0]["explanation"]
    assert "wooden" in results[0]["explanation"]


def test_ties_are_stable_when_input_order_changes(assets):
    first = KeywordBaseline(assets).search("wooden chair")
    second = KeywordBaseline(list(reversed(assets))).search("wooden chair")

    assert first == second


@pytest.mark.parametrize(
    ("query", "expected_id"),
    [
        ("stool", "asset-c"),   # name
        ("seat", "asset-a"),    # description
        ("oak", "asset-b"),     # tags
    ],
)
def test_searches_name_description_and_tags(assets, query, expected_id):
    results = KeywordBaseline(assets).search(query)

    assert len(results) == 1
    assert results[0]["asset"]["asset_id"] == expected_id
    assert results[0]["score"] == 1


def test_matches_whole_tokens():
    baseline = KeywordBaseline(
        [
            {"asset_id": "armchair", "name": "Armchair"},
            {"asset_id": "chair", "name": "Chair"},
        ]
    )

    results = baseline.search("chair")

    assert [item["asset"]["asset_id"] for item in results] == ["chair"]


def test_unicode_normalization_preserves_vietnamese_accents():
    baseline = KeywordBaseline(
        [
            {
                "asset_id": "vi-chair",
                "name": "Ghế gỗ",
                "description": None,
                "tags": None,
            }
        ]
    )

    queries = ["GHẾ GỖ", unicodedata.normalize("NFD", "ghế gỗ")]
    for query in queries:
        results = baseline.search(query)
        assert results[0]["asset"]["asset_id"] == "vi-chair"
        assert results[0]["score"] == 2

    assert baseline.search("ghe go") == []


@pytest.mark.parametrize("query", ["zebra", "!!!"])
def test_no_matches_returns_empty_list(assets, query):
    assert KeywordBaseline(assets).search(query) == []


def test_limit_is_applied_after_ranking(assets):
    results = KeywordBaseline(assets).search("wooden chair", limit=2)

    assert [item["asset"]["asset_id"] for item in results] == [
        "asset-a", "asset-b"
    ]
    assert [item["rank"] for item in results] == [1, 2]


def test_duplicate_id_keeps_first_record():
    baseline = KeywordBaseline(
        [
            {"asset_id": "same", "name": "First chair"},
            {"asset_id": "same", "name": "Second chair"},
        ]
    )

    results = baseline.search("chair")

    assert len(results) == 1
    assert results[0]["asset"]["name"] == "First chair"


def test_input_and_result_mutations_do_not_change_index(assets):
    baseline = KeywordBaseline(assets)
    assets[0]["name"] = "Changed source"
    assets[0]["tags"].append("zebra")

    results = baseline.search("oak")
    assert results[0]["asset"]["name"] == "Wooden chair"
    assert baseline.search("zebra") == []

    results[0]["asset"]["tags"].append("changed-result")
    again = baseline.search("oak")
    assert again[0]["asset"]["tags"] == ["oak"]


def test_empty_index():
    assert KeywordBaseline([]).search("chair") == []


@pytest.mark.parametrize("query", [None, "", " ", "x" * 501, 123, False])
def test_rejects_invalid_query(assets, query):
    with pytest.raises(ValueError):
        KeywordBaseline(assets).search(query)


@pytest.mark.parametrize("limit", [0, -1, 51, True, 1.5, "2", None])
def test_rejects_invalid_limit(assets, limit):
    with pytest.raises(ValueError):
        KeywordBaseline(assets).search("chair", limit=limit)


@pytest.mark.parametrize("tags", [123, "chair", [1]])
def test_rejects_invalid_tags(tags):
    with pytest.raises(ValueError):
        KeywordBaseline(
            [{"asset_id": "invalid", "name": "Chair", "tags": tags}]
        )