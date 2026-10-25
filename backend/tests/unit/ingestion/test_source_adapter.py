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
    real_manifest_path = Path(__file__).resolve().parents[4] / "data/manifests/objaverse_200.json"
    adapter = SourceAdapter(real_manifest_path)
    data = adapter.load_manifest()
    valid, invalid = adapter.normalize_and_validate(data)
    assert len(data) == 200
    assert len(valid) == 200, invalid
    assert len(invalid) == 0


def asset(**changes):
    return {"asset_id": "a1", "source": "objaverse", "source_id": "uid1",
            "source_url": "https://example.org/model", "name": "Chair",
            "license": "by", **changes}


def test_invalid_record_does_not_reserve_id_or_source():
    valid, invalid = SourceAdapter("").normalize_and_validate([asset(name=None), asset()])
    assert len(valid) == len(invalid) == 1
    assert valid[0]["asset_id"] == "a1"


def test_duplicate_source_with_different_asset_id():
    valid, invalid = SourceAdapter("").normalize_and_validate([asset(), asset(asset_id="a2")])
    assert len(valid) == len(invalid) == 1
    assert "source/source_id" in " ".join(invalid[0]["errors"])


def test_trim_dedup_and_preserve_input():
    original = asset(asset_id=" a1 ", tags=[" chair ", "chair", ""], formats=[" glb "])
    valid, invalid = SourceAdapter("").normalize_and_validate([original, asset()])
    assert len(valid) == len(invalid) == 1
    assert valid[0]["asset_id"] == "a1"
    assert valid[0]["tags"] == ["chair"]
    assert valid[0]["formats"] == ["glb"]
    assert original["asset_id"] == " a1 "
    valid[0]["tags"].append("table")
    assert original["tags"] == [" chair ", "chair", ""]


@pytest.mark.parametrize("url", ["https://", "ftp://example.org/a", "https://exa mple.org/a",
                                     "https://example.org:bad/a", "https://example.org:65536/a",
                                     "https://user:password@example.org/a", "https://example.org/a\nb"])
def test_invalid_urls_are_reported(url):
    valid, invalid = SourceAdapter("").normalize_and_validate([asset(source_url=url), asset(asset_id="a2")])
    assert len(valid) == len(invalid) == 1


@pytest.mark.parametrize("changes", [{"face_count": True}, {"face_count": -1},
                                    {"tags": [1]}, {"formats": "glb"}, {"checksum": "fake"},
                                    {"source_id": []}, {"license": None}, {"ingestion_status": 1}])
def test_invalid_fields_do_not_abort_batch(changes):
    valid, invalid = SourceAdapter("").normalize_and_validate([asset(**changes), asset()])
    assert len(valid) == len(invalid) == 1


@pytest.mark.parametrize("content", ["{", "{}", "null", "123"])
def test_malformed_or_non_array_manifest(tmp_path, content):
    path = tmp_path / "manifest.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        SourceAdapter(path).load_manifest()


def test_non_objects_are_reported_and_raw_preserved():
    original = asset(name=" ")
    valid, invalid = SourceAdapter("").normalize_and_validate([None, [], original, asset()])
    assert len(valid) == 1
    assert len(invalid) == 3
    assert invalid[2]["raw_item"] == original


def test_directory_is_not_manifest(tmp_path):
    with pytest.raises(ValueError):
        SourceAdapter(tmp_path).load_manifest()
