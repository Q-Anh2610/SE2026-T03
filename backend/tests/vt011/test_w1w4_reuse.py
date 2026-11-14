"""T17: reuse Huyền's W1 reader, W2 writer, W3/W4 committed snapshots.

No downloads: preview evidence is metadata already audited in W4, not a new
image verification. Source-level scope is deliberately distinct from snapshot
membership: a source grant permits all rows of that source in the test DB.
"""
import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ingestion.repository import upsert_downloaded_asset
from app.ingestion.source_adapter import SourceAdapter
from app.models import Asset
from .test_api import download

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = ROOT / 'data/manifests/home-interior-354-v1'


@pytest.mark.parametrize('relative,count', [
    ('data/manifests/objaverse_200.json', 200),
    ('data/manifests/home-interior-354-v1/assets_354.json', 354),
])
def test_t17_w1_reader_w2_idempotent_db_w3_snapshot_w4_evidence(
        engine, client, relative, count):
    path = ROOT / relative
    raw = json.loads(path.read_text(encoding='utf-8-sig'))
    valid, invalid = SourceAdapter(path).normalize_and_validate(raw)
    assert not invalid and len(valid) == count
    expected = {r['asset_id']: r for r in raw}  # oracle from committed data
    assert len(expected) == count
    if count == 354:
        provenance = json.loads((SNAPSHOT/'assets_354.provenance.json').read_text(encoding='utf-8-sig'))
        assert hashlib.sha256(path.read_bytes()).hexdigest() == provenance['manifest_sha256']
    # Replace only objaverse fixtures; keep b-1 (abo) to expose source leaks.
    with Session(engine) as session:
        session.execute(delete(Asset).where(Asset.source == 'objaverse'))
        for _ in range(2):
            for asset in valid:
                upsert_downloaded_asset(session, asset, {
                    'preview_source_url': asset['thumbnail_path'],
                    'preview_local_path': 'fixture/preview.png',
                    'checksum': 'a'*64, 'checksum_resource': 'preview',
                })
            session.commit()
        assert session.scalar(select(func.count()).select_from(Asset)) == count + 1
    response = download(client, limit=count)
    assert response.status_code == 200
    rows = response.json()['items']
    assert [r['asset_id'] for r in rows] == sorted(expected)
    assert len(rows) == count and 'b-1' not in {r['asset_id'] for r in rows}
    for row in rows:
        original = expected[row['asset_id']]
        assert row['source'] == 'objaverse'
        for key in ('name', 'tags', 'formats', 'license', 'author', 'source_url'):
            assert row[key] == original[key]
    # Boundary on real data, not a two-row-only characterization.
    assert download(client, limit=count-1).status_code == 413
    assert download(client, 'fixture-reader', limit=count).status_code == 403
