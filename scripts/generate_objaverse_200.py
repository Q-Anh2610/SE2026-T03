
"""
Phân loại asset nội thất/đồ gia dụng dựa trên metadata.

Mục đích:
- Chuẩn hóa metadata dạng chuỗi hoặc danh sách.
- Tìm từ khóa nội thất trong name, category và tags.
- Trả về kết quả phân loại cùng các từ khóa/trường khớp.
- Không tự suy đoán hoặc bổ sung metadata còn thiếu.

File này chỉ phân loại metadata, không tải model và không tạo manifest.
"""

import re
import unicodedata
from collections.abc import Mapping
from typing import Any


# Các từ khóa tiếng Anh thường gặp trong nhóm nội thất và đồ gia dụng.
# Có thể bổ sung từ khóa khi kiểm tra dữ liệu Objaverse thực tế.
FURNITURE_KEYWORDS = {
    "armchair",
    "bed",
    "bench",
    "bookcase",
    "bookshelf",
    "cabinet",
    "chair",
    "chest of drawers",
    "coffee table",
    "couch",
    "cupboard",
    "desk",
    "dining table",
    "dresser",
    "drawer",
    "furniture",
    "kitchen cabinet",
    "lamp",
    "mattress",
    "nightstand",
    "ottoman",
    "pillow",
    "shelf",
    "sofa",
    "stool",
    "table",
    "wardrobe",
}

# Các trường metadata được sử dụng để phân loại.
# Tên khóa được giữ ở dạng số nhiều để nhất quán trong kết quả.
METADATA_FIELDS = ("categories", "tags", "names")


def normalize_text(value: Any) -> str:
    """
    Chuẩn hóa một giá trị thành chuỗi chữ thường.

    Ví dụ:
        "Dining_Table" -> "dining table"
        "  SOFA  "     -> "sofa"

    Giá trị None hoặc không phải chuỗi sẽ trả về chuỗi rỗng.
    """
    if not isinstance(value, str):
        return ""

    # Chuẩn hóa Unicode và chuyển về chữ thường.
    text = unicodedata.normalize("NFKC", value).lower().strip()

    # Xem dấu gạch dưới/gạch nối là dấu phân cách giữa các từ.
    text = re.sub(r"[_\-]+", " ", text)

    # Chuẩn hóa các dấu câu và khoảng trắng thành dấu cách.
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def extract_text_values(value: Any) -> list[str]:
    """
    Lấy các giá trị dạng chuỗi từ metadata.

    Hỗ trợ:
    - Chuỗi: "chair"
    - Danh sách/tuple/set: ["chair", "wooden table"]
    - Dictionary: lấy các giá trị bên trong
    - None hoặc kiểu dữ liệu không hỗ trợ: trả về []

    Không chuyển số hoặc boolean thành chuỗi để tránh tạo ra
    nội dung metadata không có ý nghĩa.
    """
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []

    if isinstance(value, Mapping):
        results: list[str] = []
        for nested_value in value.values():
            results.extend(extract_text_values(nested_value))
        return results

    if isinstance(value, (list, tuple, set)):
        results: list[str] = []
        for item in value:
            results.extend(extract_text_values(item))
        return results

    return []


def contains_keyword(text: Any, keyword: Any) -> bool:
    """
    Kiểm tra text có chứa keyword sau khi chuẩn hóa hay không.

    So khớp theo ranh giới từ để hạn chế trường hợp khớp nhầm:
        "chair" khớp "wooden chair"
        "chair" không khớp "chairman"
    """
    normalized_text = normalize_text(text)
    normalized_keyword = normalize_text(keyword)

    if not normalized_text or not normalized_keyword:
        return False

    # Escape từ khóa để các ký tự đặc biệt không bị hiểu là regex.
    pattern = rf"(?<!\w){re.escape(normalized_keyword)}(?!\w)"

    return re.search(pattern, normalized_text) is not None



def find_furniture_keywords(text: Any) -> list[str]:
    """Tìm từ khóa nội thất, ưu tiên cụm từ dài hơn."""

    normalized_text = normalize_text(text)

    if not normalized_text:
        return []

    # Lấy tất cả từ khóa khớp, sắp xếp cụm dài trước.
    candidates = [
        keyword
        for keyword in FURNITURE_KEYWORDS
        if contains_keyword(normalized_text, keyword)
    ]
    candidates.sort(key=lambda keyword: (-len(keyword), keyword))

    selected = []

    for keyword in candidates:
        # Không thêm từ khóa ngắn nếu nó đã nằm trong cụm dài được chọn.
        is_inside_longer_phrase = any(
            contains_keyword(selected_keyword, keyword)
            for selected_keyword in selected
        )

        if not is_inside_longer_phrase:
            selected.append(keyword)

    return sorted(selected)



def get_metadata_texts(metadata: Any) -> dict[str, list[str]]:
    """
    Trích xuất nội dung từ các trường metadata cần dùng.

    Các khóa đầu ra luôn có mặt:
        categories, tags, names

    Metadata thiếu trường, None hoặc không phải dictionary
    sẽ được xử lý như dữ liệu rỗng.
    """
    result = {
        "categories": [],
        "tags": [],
        "names": [],
    }

    if not isinstance(metadata, Mapping):
        return result

    # Category có thể là chuỗi, danh sách hoặc cấu trúc lồng nhau.
    result["categories"] = extract_text_values(metadata.get("category"))
    result["categories"].extend(
        extract_text_values(metadata.get("categories"))
    )

    # Tags có thể là một chuỗi hoặc danh sách tag.
    result["tags"] = extract_text_values(metadata.get("tags"))

    # Name có thể là chuỗi hoặc danh sách tên.
    result["names"] = extract_text_values(metadata.get("name"))
    result["names"].extend(extract_text_values(metadata.get("names")))

    return result


def classify_furniture(metadata: Any) -> dict[str, Any]:
    """
    Phân loại metadata có thuộc nhóm nội thất/đồ gia dụng hay không.

    Returns:
        {
            "is_furniture": bool,
            "matched_keywords": list[str],
            "matched_fields": list[str],
        }

    Quy tắc:
    - Chỉ xét category/categories, tags, name/names.
    - Một từ khóa khớp ở ít nhất một trường thì is_furniture=True.
    - matched_fields dùng các tên khóa số nhiều:
      "categories", "tags", "names".
    - Metadata không hợp lệ hoặc không khớp từ khóa sẽ trả về
      is_furniture=False với hai danh sách rỗng.
    """
    metadata_texts = get_metadata_texts(metadata)

    matched_keywords: set[str] = set()
    matched_fields: list[str] = []

    for field_name in METADATA_FIELDS:
        field_values = metadata_texts[field_name]
        field_keywords: set[str] = set()

        for value in field_values:
            field_keywords.update(find_furniture_keywords(value))

        if field_keywords:
            matched_fields.append(field_name)
            matched_keywords.update(field_keywords)

    return {
        "is_furniture": bool(matched_keywords),
        "matched_keywords": sorted(matched_keywords),
        "matched_fields": matched_fields,
    }


def is_furniture(metadata: Any) -> bool:
    """
    Hàm tiện ích nếu chỉ cần kết quả True/False.
    """
    return classify_furniture(metadata)["is_furniture"]
