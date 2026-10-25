"""Ánh xạ annotation Objaverse 1.0 sang metadata SRS, không suy đoán giá trị."""

import re
from typing import Any

from .source_adapter import SRS_18_FIELDS, SourceAdapter


def annotation_to_asset(annotation: dict[str, Any]) -> dict[str, Any]:
    uid = annotation.get("uid")
    if not isinstance(uid, str) or not re.fullmatch(r"[0-9a-f]{32}", uid):
        raise ValueError("UID Objaverse phải là 32 ký tự hex chữ thường.")
    license_value = annotation.get("license")
    if not isinstance(license_value, str) or license_value not in {"by", "by-sa", "by-nd", "by-nc", "by-nc-sa", "by-nc-nd", "cc0"}:
        raise ValueError("License nguồn thiếu hoặc không thuộc token Creative Commons của Objaverse.")

    def labels(value):
        if not isinstance(value, list):
            return []
        return list(dict.fromkeys(
            item["name"].strip() for item in value
            if isinstance(item, dict) and isinstance(item.get("name"), str)
            and item["name"].strip()
        ))

    thumbnails = annotation.get("thumbnails") or {}
    images = thumbnails.get("images", []) if isinstance(thumbnails, dict) else []
    images = [image for image in images if isinstance(image, dict)
              and SourceAdapter._is_valid_url(image.get("url"))
              and type(image.get("width")) is int and image["width"] >= 256]
    
    # Ưu tiên preview gần 720 px; thumbnail nhiều kích thước không phải multi-view.
    preview = min(images, key=lambda image: (abs(image["width"] - 720), image["url"]), default=None)
    categories = labels(annotation.get("categories"))
    user = annotation.get("user") or {}
    author = (user.get("displayName") or user.get("username")) if isinstance(user, dict) else None
    archives = annotation.get("archives") or {}
    record = dict.fromkeys(SRS_18_FIELDS)
    record.update(
        asset_id=f"objaverse_{uid}", source="objaverse", source_id=uid,
        source_url=annotation.get("viewerUrl"), author=author,

        # Giữ license token gốc, không tự đổi thành một phiên bản CC cụ thể.
        license=annotation.get("license"), name=annotation.get("name"),
        description=annotation.get("description"), tags=labels(annotation.get("tags")),
        category=categories[0] if categories else None,
        thumbnail_path=preview["url"] if preview else None,
        
        # 'source' không phải định dạng; chỉ chấp nhận format được nguồn ghi rõ.
        formats=sorted(key for key, value in archives.items()
                       if key != "source" and isinstance(value, dict) and value.get("type") == key)
                if isinstance(archives, dict) else [],
        face_count=annotation.get("faceCount"), ingestion_status="PENDING",
    )
    valid, invalid = SourceAdapter("").normalize_and_validate([record])
    if invalid:
        raise ValueError("; ".join(invalid[0]["errors"]))
    return valid[0]
