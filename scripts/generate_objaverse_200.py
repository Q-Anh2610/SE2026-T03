
"""
Phân loại asset nội thất/đồ gia dụng dựa trên metadata.

Mục đích:
- Chuẩn hóa metadata dạng chuỗi hoặc danh sách.
- Tìm từ khóa nội thất trong name, category và tags.
- Trả về kết quả phân loại cùng các từ khóa/trường khớp.
- Không tự suy đoán hoặc bổ sung metadata còn thiếu.

Chạy bằng python -m scripts.generate_objaverse_200 để tạo manifest có provenance.
Chỉ đọc metadata và kiểm tra preview; không tải model 3D.
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
    result["categories"] = extract_metadata_labels(metadata.get("category"))
    result["categories"].extend(
        extract_metadata_labels(metadata.get("categories"))
    )

    # Tags có thể là một chuỗi hoặc danh sách tag.
    result["tags"] = extract_metadata_labels(metadata.get("tags"))

    # Name có thể là chuỗi hoặc danh sách tên.
    result["names"] = extract_metadata_labels(metadata.get("name"))
    result["names"].extend(extract_metadata_labels(metadata.get("names")))

    return result


def extract_metadata_labels(value: Any) -> list[str]:
    """Objaverse tag/category: chỉ dùng nhãn, không phân loại theo URI/ID."""
    if isinstance(value, Mapping):
        return extract_text_values(value.get("name") or value.get("slug"))
    if isinstance(value, (list, tuple)):
        return [text for item in value for text in extract_metadata_labels(item)]
    return extract_text_values(value)


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


def main(argv=None) -> int:
    """Tạo đúng subset yêu cầu; thất bại không ghi đè manifest đang dùng."""
    import argparse
    import gzip
    import hashlib
    import json
    import sys
    import warnings
    from collections import Counter
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timezone
    from io import BytesIO
    from pathlib import Path
    from urllib.parse import urlparse
    from urllib.request import urlopen

    from PIL import Image
    from backend.app.ingestion.objaverse import annotation_to_asset

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--revision", default="556637099bf4fa79ea7b239d0d9c328b8a2e9ac8")
    parser.add_argument("--shards", nargs="+", default=["000-000"])
    parser.add_argument("--output", type=Path, default=Path("data/manifests/objaverse_200.json"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/objaverse"))
    args = parser.parse_args(argv)
    if not 1 <= args.count <= 1000:
        parser.error("count phải nằm trong 1..1000.")
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        parser.error("revision phải là commit SHA Hugging Face 40 ký tự.")
    if any(not re.fullmatch(r"\d{3}-\d{3}", shard) for shard in args.shards):
        parser.error("Tên shard phải có dạng 000-000.")

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    rejected = Counter()
    sources, annotations = [], {}
    try:
        for shard in dict.fromkeys(args.shards):
            url = f"https://huggingface.co/datasets/allenai/objaverse/resolve/{args.revision}/metadata/{shard}.json.gz"
            cache = args.cache_dir / f"{args.revision}-{shard}.json.gz"
            if not cache.is_file():
                with urlopen(url, timeout=30) as response:
                    content = response.read(16 * 1024 * 1024 + 1)
                if len(content) > 16 * 1024 * 1024:
                    raise ValueError("Metadata shard vượt giới hạn 16 MiB.")
                cache.write_bytes(content)
            content = cache.read_bytes()
            source = json.loads(gzip.decompress(content))
            if not isinstance(source, dict):
                raise ValueError("Metadata shard phải là object JSON.")
            sources.append({"url": url, "sha256": hashlib.sha256(content).hexdigest(), "records": len(source)})
            for uid, annotation in source.items():
                if not isinstance(annotation, dict) or annotation.get("uid") != uid:
                    rejected["invalid_annotation"] += 1
                    continue
                annotations.setdefault(uid, annotation)

        candidates = []
        for uid, annotation in sorted(annotations.items()):
            if annotation.get("isAgeRestricted"):
                rejected["age_restricted"] += 1
                continue
            if not is_furniture(annotation):
                rejected["outside_domain"] += 1
                continue
            try:
                asset = annotation_to_asset(annotation)
            except ValueError:
                rejected["invalid_metadata_or_license"] += 1
                continue
            url = urlparse(asset["thumbnail_path"] or "")
            if url.scheme != "https" or url.hostname != "media.sketchfab.com" or url.username or url.password:
                rejected["missing_or_untrusted_preview"] += 1
                continue
            candidates.append((asset, annotation))

        def check_preview(candidate):
            asset, annotation = candidate
            try:
                with urlopen(asset["thumbnail_path"], timeout=15) as response:
                    if urlparse(response.url).hostname != "media.sketchfab.com":
                        raise ValueError("Preview chuyển hướng ra ngoài nguồn cho phép.")
                    content = response.read(2 * 1024 * 1024 + 1)
                if len(content) > 2 * 1024 * 1024:
                    raise ValueError("Preview vượt giới hạn 2 MiB.")
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(BytesIO(content)) as image:
                        if max(image.size) > 4096 or image.format not in {"JPEG", "PNG", "WEBP"}:
                            raise ValueError("Preview không đáp ứng kích thước/định dạng.")
                        image.verify()
                    with Image.open(BytesIO(content)) as image:
                        image.load()
                        size = list(image.size)
                return asset, annotation, {
                    "asset_id": asset["asset_id"], "url": asset["thumbnail_path"],
                    "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
                    "dimensions": size, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            except Exception as exc:
                return {"asset_id": asset["asset_id"], "error_type": type(exc).__name__}

        selected, evidence, raw, failures = [], [], {}, []
        # Batches nhỏ, kiểm tra song song sáu preview; dừng khi đủ subset.
        with ThreadPoolExecutor(max_workers=6) as executor:
            for offset in range(0, len(candidates), 6):
                for result in executor.map(check_preview, candidates[offset:offset + 6]):
                    if isinstance(result, dict):
                        failures.append(result)
                    elif len(selected) < args.count:
                        asset, annotation, preview = result
                        selected.append(asset)
                        raw[asset["source_id"]] = annotation
                        evidence.append(preview)
                print(f"Preview hợp lệ: {len(selected)}/{args.count}", flush=True)
                if len(selected) == args.count:
                    break
        if len(selected) != args.count:
            raise ValueError(f"Chỉ có {len(selected)}/{args.count} asset đạt kiểm tra; chưa ghi manifest. Thêm --shards để mở rộng metadata.")

        def encoded(value):
            return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

        manifest = encoded(selected)
        originals = encoded(raw)
        report = {
            "dataset": "Objaverse 1.0", "revision": args.revision,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "count": len(selected), "sources": sources,
            "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
            "annotations_sha256": hashlib.sha256(originals).hexdigest(),
            "selection": "UID tăng dần; keyword trong name/categories/tags; không age-restricted; license có sẵn; preview decode được. Chưa review ngữ nghĩa thủ công.",
            "rejected_metadata": dict(rejected), "preview_failures": failures,
            "license_counts": dict(Counter(asset["license"] for asset in selected)),
            "face_count_semantics": "Giữ nguyên faceCount nguồn Sketchfab; chưa xác nhận tương đương triangle count của file GLB.",
            "previews": evidence,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(manifest)
        args.output.with_suffix(".annotations.json").write_bytes(originals)
        args.output.with_suffix(".provenance.json").write_bytes(encoded(report))
        print(f"Đã ghi {len(selected)} asset và provenance tại {args.output}")
        return 0
    except (OSError, ValueError, EOFError) as exc:
        print(f"Không tạo được manifest: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())