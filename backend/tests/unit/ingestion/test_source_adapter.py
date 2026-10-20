# Kiểm thử các trường hợp dữ liệu

import json
import pytest
from pathlib import Path
from backend.app.ingestion.source_adapter import SourceAdapter, SRS_18_FIELDS


@pytest.fixture
def sample_manifest_file(tmp_path: Path) -> Path:
    """Fixture tạo file JSON manifest giả lập cho test."""
    manifest_data = [
        {
            "asset_id": "objaverse_001",
            "source": "objaverse",
            "source_id": "uid_001",
            "source_url": "https://objaverse.allenai.org/explore?id=uid_001",
            "author": "Creator 1",
            "license": "CC-BY-4.0",
            "name": "Chair Model",
            "description": "A nice chair",
            "tags": ["chair"],
            "category": "furniture",
            "thumbnail_path": "https://images.objaverse.org/thumb1.jpg",
            "formats": ["glb"],
            "face_count": 10000
        },
        {
            # Bản ghi lỗi 1: Thiếu name và source_url
            "asset_id": "objaverse_002",
            "source": "objaverse",
            "source_id": "uid_002",
            "license": "CC-BY-4.0"
        },
        {
            # Bản ghi lỗi 2: Trùng lặp asset_id với bản ghi 1
            "asset_id": "objaverse_001",
            "source": "objaverse",
            "source_id": "uid_003",
            "source_url": "https://objaverse.allenai.org/explore?id=uid_003",
            "name": "Duplicate Chair",
            "license": "CC-BY-4.0"
        },
        {
            # Bản ghi lỗi 3: Sai kiểu dữ liệu face_count
            "asset_id": "objaverse_004",
            "source": "objaverse",
            "source_id": "uid_004",
            "source_url": "https://objaverse.allenai.org/explore?id=uid_004",
            "name": "Bad Face Count",
            "license": "CC-BY-4.0",
            "face_count": "invalid_number_string"
        }
    ]

    file_path = tmp_path / "test_manifest.json"
    file_path.write_text(json.dumps(manifest_data, ensure_ascii=False), encoding="utf-8")
    return file_path


def test_load_manifest_success(sample_manifest_file: Path):
    """Test đọc file manifest thành công."""
    adapter = SourceAdapter(sample_manifest_file)
    data = adapter.load_manifest()
    assert len(data) == 4


def test_load_manifest_file_not_found():
    """Test báo lỗi khi file không tồn tại."""
    adapter = SourceAdapter("non_existent_file.json")
    with pytest.raises(FileNotFoundError):
        adapter.load_manifest()


def test_normalize_and_validate(sample_manifest_file: Path):
    """Test lọc dữ liệu hợp lệ và ghi nhận danh sách bản ghi lỗi."""
    adapter = SourceAdapter(sample_manifest_file)
    raw_data = adapter.load_manifest()
    valid, invalid = adapter.normalize_and_validate(raw_data)

    # 1 bản ghi hợp lệ, 3 bản ghi lỗi
    assert len(valid) == 1
    assert len(invalid) == 3

    # Kiểm tra chuẩn hóa 18 trường của bản ghi hợp lệ
    valid_record = valid[0]
    assert valid_record["asset_id"] == "objaverse_001"
    assert len(valid_record) == len(SRS_18_FIELDS)
    assert valid_record["checksum"] is None
    assert valid_record["ingestion_status"] == "PENDING"
    assert valid_record["model_version"] is None


def test_real_manifest_200_records():
    """Test đọc file manifest 200 records thực tế trong dự án."""
    real_manifest_path = Path("data/manifests/objaverse_200.json")
    if real_manifest_path.exists():
        adapter = SourceAdapter(real_manifest_path)
        data = adapter.load_manifest()
        valid, invalid = adapter.normalize_and_validate(data)

        assert len(data) == 200
        assert len(valid) == 200
        assert len(invalid) == 0