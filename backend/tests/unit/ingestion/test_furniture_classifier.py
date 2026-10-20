
"""
Unit tests cho furniture_classifier.py.

Chạy từ thư mục gốc repository:
    python -m pytest backend/tests/unit/ingestion/test_furniture_classifier.py -v
"""

import pytest

from scripts.generate_objaverse_200 import (
    classify_furniture,
    contains_keyword,
    extract_text_values,
    find_furniture_keywords,
    get_metadata_texts,
    is_furniture,
    normalize_text,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("CHAIR", "chair"),
        ("  Wooden Table  ", "wooden table"),
        ("dining_table", "dining table"),
        ("coffee-table", "coffee table"),
        ("", ""),
        (None, ""),
        (123, ""),
    ],
)
def test_normalize_text(text, expected):
    """Chuẩn hóa chữ hoa, khoảng trắng và dấu phân cách."""
    assert normalize_text(text) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("chair", ["chair"]),
        (["chair", "table"], ["chair", "table"]),
        (("sofa", "lamp"), ["sofa", "lamp"]),
        ({"first": "chair", "second": "desk"}, ["chair", "desk"]),
        (None, []),
        (123, []),
        ("", []),
        (["chair", None, 123, "table"], ["chair", "table"]),
    ],
)
def test_extract_text_values(value, expected):
    """Trích xuất chuỗi từ những kiểu metadata được hỗ trợ."""
    assert extract_text_values(value) == expected


@pytest.mark.parametrize(
    ("text", "keyword", "expected"),
    [
        ("wooden chair", "chair", True),
        ("CHAIR", "chair", True),
        ("a coffee table", "coffee table", True),
        ("dining_table", "dining table", True),
        ("chairman", "chair", False),
        ("tableware", "table", False),
        ("wooden chair", "sofa", False),
        ("chair", "", False),
        (None, "chair", False),
    ],
)
def test_contains_keyword(text, keyword, expected):
    """Kiểm tra so khớp từ khóa theo ranh giới từ."""
    assert contains_keyword(text, keyword) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("chair", ["chair"]),
        ("A wooden chair", ["chair"]),
        ("modern sofa", ["sofa"]),
        ("coffee_table", ["coffee table"]),
        ("a chair and a table", ["chair", "table"]),
        ("chairman", []),
        ("electronic device", []),
        ("", []),
        (None, []),
    ],
)
def test_find_furniture_keywords(text, expected):
    """Tìm từ khóa nội thất trong một chuỗi."""
    assert find_furniture_keywords(text) == expected


def test_get_metadata_texts_extracts_supported_fields():
    """Đọc name, category và tags từ metadata."""
    metadata = {
        "name": "Wooden Chair",
        "category": "Furniture",
        "tags": ["wood", "dining room"],
    }

    result = get_metadata_texts(metadata)

    assert result == {
        "categories": ["Furniture"],
        "tags": ["wood", "dining room"],
        "names": ["Wooden Chair"],
    }


def test_get_metadata_texts_supports_plural_fields():
    """Hỗ trợ categories và names nếu nguồn dữ liệu dùng dạng số nhiều."""
    metadata = {
        "names": ["Office Desk"],
        "categories": ["Home Furniture"],
        "tags": ["modern"],
    }

    result = get_metadata_texts(metadata)

    assert result["names"] == ["Office Desk"]
    assert result["categories"] == ["Home Furniture"]
    assert result["tags"] == ["modern"]


@pytest.mark.parametrize(
    ("metadata", "expected_keyword", "expected_field"),
    [
        (
            {"name": "Wooden Chair"},
            "chair",
            "names",
        ),
        (
            {"category": "Furniture"},
            "furniture",
            "categories",
        ),
        (
            {"tags": ["modern sofa", "living room"]},
            "sofa",
            "tags",
        ),
    ],
)
def test_classify_furniture_matches_metadata_field(
    metadata,
    expected_keyword,
    expected_field,
):
    """Phân loại đúng khi từ khóa xuất hiện ở từng trường metadata."""
    result = classify_furniture(metadata)

    assert result["is_furniture"] is True
    assert expected_keyword in result["matched_keywords"]
    assert expected_field in result["matched_fields"]



def test_classify_furniture_matches_multiple_fields():
    """Ghi nhận tất cả trường và từ khóa khớp."""
    metadata = {
        "name": "Wooden Dining Chair",
        "category": "Furniture",
        "tags": ["dining table", "wood"],
    }

    result = classify_furniture(metadata)

    assert result["is_furniture"] is True

    assert set(result["matched_fields"]) == {
        "names",
        "categories",
        "tags",
    }

    # Cụm từ khóa dài được ưu tiên hơn từ khóa nằm bên trong.
    assert {
        "chair",
        "dining table",
        "furniture",
    }.issubset(set(result["matched_keywords"]))

    # "table" không xuất hiện riêng vì đã nằm trong "dining table".
    assert "table" not in result["matched_keywords"]



def test_classify_furniture_returns_expected_structure():
    """Kết quả luôn có đủ ba khóa đầu ra."""
    result = classify_furniture({"name": "Office Chair"})

    assert set(result.keys()) == {
        "is_furniture",
        "matched_keywords",
        "matched_fields",
    }
    assert isinstance(result["is_furniture"], bool)
    assert isinstance(result["matched_keywords"], list)
    assert isinstance(result["matched_fields"], list)


@pytest.mark.parametrize(
    "metadata",
    [
        {"name": "Electronic Device"},
        {"name": "A person standing"},
        {"category": "Vehicle", "tags": ["road", "engine"]},
        {},
        {"name": ""},
        {"name": None, "tags": []},
    ],
)
def test_classify_furniture_rejects_unmatched_metadata(metadata):
    """Không phân loại thành nội thất nếu không có từ khóa phù hợp."""
    result = classify_furniture(metadata)

    assert result["is_furniture"] is False
    assert result["matched_keywords"] == []
    assert result["matched_fields"] == []


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        "",
        "wooden chair",
        123,
        [],
        ["chair"],
    ],
)
def test_classify_furniture_handles_invalid_metadata(metadata):
    """Không phát sinh lỗi với metadata không phải dictionary."""
    result = classify_furniture(metadata)

    assert result == {
        "is_furniture": False,
        "matched_keywords": [],
        "matched_fields": [],
    }


def test_is_furniture_returns_boolean():
    """Hàm tiện ích chỉ trả về True hoặc False."""
    assert is_furniture({"name": "Office Chair"}) is True
    assert is_furniture({"name": "Mountain Landscape"}) is False


def test_classifier_is_case_insensitive():
    """Không phân biệt chữ hoa và chữ thường."""
    assert is_furniture({"name": "WOODEN CHAIR"}) is True
    assert is_furniture({"tags": ["MODERN SOFA"]}) is True


@pytest.mark.parametrize(
    "name",
    [
        "dining_table",
        "dining-table",
        "dining table",
        "coffee_table",
        "coffee-table",
    ],
)
def test_classifier_handles_common_delimiters(name):
    """Nhận diện từ khóa có dấu gạch dưới, gạch nối hoặc dấu cách."""
    assert is_furniture({"name": name}) is True


def test_classifier_does_not_match_keyword_inside_another_word():
    """Tránh khớp nhầm từ khóa nằm bên trong từ dài hơn."""
    assert is_furniture({"name": "chairman"}) is False
    assert is_furniture({"name": "tableware"}) is False


def test_classifier_does_not_use_unconfigured_description_field():
    """Description không được dùng khi chưa đưa vào quy tắc phân loại."""
    metadata = {
        "name": "Unknown Object",
        "description": "A wooden chair for a dining room",
    }

    assert is_furniture(metadata) is False
