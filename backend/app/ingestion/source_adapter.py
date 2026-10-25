import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


# 18 trường metadata theo SRS
SRS_18_FIELDS = [
    "asset_id",
    "source",
    "source_id",
    "source_url",
    "author",
    "license",
    "name",
    "description",
    "tags",
    "category",
    "thumbnail_path",
    "model_path",
    "formats",
    "face_count",
    "checksum",
    "ingestion_status",
    "model_version",
    "index_version",
]

# Các trường bắt buộc phải có giá trị là chuỗi không rỗng.
REQUIRED_FIELDS = {
    "asset_id",
    "source",
    "source_id",
    "source_url",
    "name",
    "license",
}

# Các trường phải là chuỗi hoặc None.
OPTIONAL_STRING_FIELDS = {
    "author",
    "description",
    "category",
    "thumbnail_path",
    "model_path",
    "checksum",
    "model_version",
    "index_version",
}


class SourceAdapter:
    """
    Đọc manifest JSON, chuẩn hóa metadata theo 18 trường SRS
    và tách bản ghi hợp lệ khỏi bản ghi không hợp lệ.

    Quy ước:
    - Bản ghi hợp lệ được chuẩn hóa về đúng 18 trường.
    - Trường tùy chọn bị thiếu được gán None, trừ các trường
      có giá trị mặc định được quy định bên dưới.
    - tags và formats được chuẩn hóa thành [] nếu thiếu hoặc None.
    - ingestion_status được chuẩn hóa thành "PENDING" nếu thiếu,
      None hoặc chuỗi rỗng.
    - License không được tự suy đoán hoặc tự gán mặc định.
    - Các trường không thuộc SRS được bỏ qua trong đầu ra.
    """

    def __init__(self, manifest_path: str | Path):
        self.manifest_path = Path(manifest_path)

    def load_manifest(self) -> list[Any]:
        """
        Đọc file JSON manifest.

        Raises:
            FileNotFoundError: Nếu file không tồn tại.
            ValueError: Nếu JSON sai định dạng hoặc không phải JSON array.
        """
        if not self.manifest_path.is_file():
            if not self.manifest_path.exists():
                raise FileNotFoundError(
                    f"File manifest không tồn tại: {self.manifest_path}"
                )

            raise ValueError(
                f"Đường dẫn manifest không phải file: {self.manifest_path}"
            )

        try:
            with self.manifest_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(
                f"File manifest không đúng định dạng JSON: {exc}"
            ) from exc

        if not isinstance(data, list):
            raise ValueError(
                "Dữ liệu manifest phải là một danh sách (JSON array)."
            )

        return data

    def normalize_and_validate(
        self,
        raw_data: list[Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Kiểm tra và chuẩn hóa danh sách bản ghi.

        Args:
            raw_data: Danh sách bản ghi đọc từ manifest.

        Returns:
            Tuple gồm:
            - valid_assets: Các bản ghi hợp lệ, mỗi bản ghi có đúng 18 trường.
            - invalid_assets: Thông tin các bản ghi không hợp lệ và lý do lỗi.
        """
        valid_assets: list[dict[str, Any]] = []
        invalid_assets: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        seen_sources: set[tuple[str, str]] = set()

        if not isinstance(raw_data, list):
            raise ValueError("raw_data phải là một danh sách.")

        for index, item in enumerate(raw_data):
            if not isinstance(item, dict):
                invalid_assets.append(
                    {
                        "index": index,
                        "asset_id": f"unknown_{index}",
                        "errors": [
                            "Bản ghi phải là JSON object/dictionary."
                        ],
                        "raw_item": item,
                    }
                )
                continue

            raw_item = item
            # So sánh định danh sau trim, không sửa dictionary của caller.
            item = {
                key: value.strip() if isinstance(value, str) else value
                for key, value in item.items()
            }
            errors: list[str] = []
            asset_id = item.get("asset_id")

            # 1. Kiểm tra trường bắt buộc và kiểu chuỗi.
            for field in sorted(REQUIRED_FIELDS):
                value = item.get(field)

                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"Trường '{field}' phải là chuỗi không rỗng."
                    )

            # 2. Kiểm tra asset_id trùng lặp.
            # Chỉ xử lý trùng lặp sau khi xác nhận asset_id là chuỗi hợp lệ.
            if isinstance(asset_id, str) and asset_id.strip():
                if asset_id in seen_ids:
                    errors.append(f"Trùng lặp asset_id: '{asset_id}'")

            source_key = (item.get("source"), item.get("source_id"))
            if all(isinstance(value, str) and value for value in source_key):
                if source_key in seen_sources:
                    errors.append("Trùng lặp source/source_id.")

            # 3. Kiểm tra source_url.
            source_url = item.get("source_url")

            if isinstance(source_url, str) and source_url.strip():
                if not self._is_valid_url(source_url):
                    errors.append(
                        f"Định dạng source_url không hợp lệ: '{source_url}'"
                    )

            # 4. Kiểm tra các trường chuỗi tùy chọn.
            for field in sorted(OPTIONAL_STRING_FIELDS):
                value = item.get(field)

                if value is not None and not isinstance(value, str):
                    errors.append(
                        f"Trường '{field}' phải là chuỗi hoặc null."
                    )

            # thumbnail_path có thể là URL hoặc đường dẫn local.
            # Nếu là URL HTTP(S), cần kiểm tra cú pháp.
            thumbnail_path = item.get("thumbnail_path")

            if isinstance(thumbnail_path, str):
                if thumbnail_path.strip().lower().startswith(
                    ("http://", "https://")
                ):
                    if not self._is_valid_url(thumbnail_path):
                        errors.append(
                            "Định dạng URL trong 'thumbnail_path' "
                            f"không hợp lệ: '{thumbnail_path}'"
                        )

            # 5. tags phải là list[str] hoặc None.
            tags = item.get("tags")

            if tags is not None:
                if not isinstance(tags, list):
                    errors.append("Trường 'tags' phải là danh sách hoặc null.")
                elif any(not isinstance(tag, str) for tag in tags):
                    errors.append(
                        "Các phần tử trong 'tags' phải là chuỗi."
                    )

            # 6. formats phải là list[str] hoặc None.
            formats = item.get("formats")

            if formats is not None:
                if not isinstance(formats, list):
                    errors.append(
                        "Trường 'formats' phải là danh sách hoặc null."
                    )
                elif any(not isinstance(fmt, str) for fmt in formats):
                    errors.append(
                        "Các phần tử trong 'formats' phải là chuỗi."
                    )

            # 7. face_count phải là số nguyên không âm hoặc None.
            face_count = item.get("face_count")

            if face_count is not None:
                if (
                    not isinstance(face_count, int)
                    or isinstance(face_count, bool)
                    or face_count < 0
                ):
                    errors.append(
                        "Trường 'face_count' phải là số nguyên "
                        "không âm hoặc null."
                    )

            # 8. ingestion_status phải là chuỗi hoặc None.
            # Danh sách giá trị trạng thái cụ thể cần thống nhất theo SRS.
            ingestion_status = item.get("ingestion_status")

            if (
                ingestion_status is not None
                and not isinstance(ingestion_status, str)
            ):
                errors.append(
                    "Trường 'ingestion_status' phải là chuỗi hoặc null."
                )

            checksum = item.get("checksum")
            if isinstance(checksum, str) and not re.fullmatch(r"[0-9a-fA-F]{64}", checksum):
                errors.append("Trường 'checksum' phải là SHA-256 hex 64 ký tự hoặc null.")

            # Có lỗi thì không đưa bản ghi vào danh sách hợp lệ.
            if errors:
                invalid_assets.append(
                    {
                        "index": index,
                        "asset_id": (
                            asset_id
                            if isinstance(asset_id, str) and asset_id.strip()
                            else f"unknown_{index}"
                        ),
                        "errors": errors,
                        "raw_item": raw_item,
                    }
                )
                continue

            # 9. Chuẩn hóa đúng 18 trường SRS.
            normalized_record: dict[str, Any] = {
                field: item.get(field)
                for field in SRS_18_FIELDS
            }

            # Giá trị mặc định được quy định rõ.
            normalized_record["tags"] = list(dict.fromkeys(
                value.strip() for value in (item.get("tags") or []) if value.strip()
            ))
            normalized_record["formats"] = list(dict.fromkeys(
                value.strip() for value in (item.get("formats") or []) if value.strip()
            ))

            status = item.get("ingestion_status")
            normalized_record["ingestion_status"] = (
                status.strip() if isinstance(status, str) and status.strip()
                else "PENDING"
            )

            valid_assets.append(normalized_record)
            # Bản ghi lỗi không được chiếm ID của bản ghi hợp lệ phía sau.
            seen_ids.add(asset_id)
            seen_sources.add(source_key)

        return valid_assets, invalid_assets

    @staticmethod
    def _is_valid_url(url_string: str) -> bool:
        """
        Kiểm tra cú pháp URL HTTP(S).

        Lưu ý: Hàm này không gửi request và không xác nhận URL
        hoặc tài nguyên thực sự tồn tại.
        """
        if not isinstance(url_string, str) or not url_string.strip():
            return False

        try:
            if any(char.isspace() or ord(char) < 32 for char in url_string):
                return False
            parsed = urlparse(url_string)
            # Truy cập port để bắt cả URL có port sai định dạng/ngoài khoảng.
            port = parsed.port

            return (
                parsed.scheme.lower() in {"http", "https"}
                and bool(parsed.netloc)
                and parsed.hostname is not None
                and parsed.username is None
                and parsed.password is None
                and port != 0
            )
        except (ValueError, TypeError):
            return False
