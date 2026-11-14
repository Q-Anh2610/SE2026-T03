"""Backend E2E: TCP HTTP -> router -> service -> migrated PG -> download file."""
import json
import httpx2

from .server import live_server


def test_t15_tcp_download_journey(app, tmp_path):
    with live_server(app) as base_url, httpx2.Client(base_url=base_url, trust_env=False) as client:
        assert client.get('/healthz').status_code == 200
        denied = client.post('/api/v1/exports/assets', json={'source': 'objaverse'})
        assert denied.status_code == 401
        response = client.post('/api/v1/exports/assets',
            headers={'Authorization': 'Bearer fixture-a'}, json={'source': 'objaverse'})
        assert response.status_code == 200
        assert response.headers['content-disposition'] == 'attachment; filename="assets.json"'
        target = tmp_path / 'assets.json'
        target.write_bytes(response.content)
        document = json.loads(target.read_text(encoding='utf-8'))
        assert [row['asset_id'] for row in document['items']] == ['a-1', 'a-2']
        assert document['items'][1]['tags'] == ['gỗ', 'chair']
        forbidden = client.post('/api/v1/exports/assets',
            headers={'Authorization': 'Bearer fixture-a'}, json={'source':'abo'})
        assert forbidden.status_code == 403
        assert 'content-disposition' not in forbidden.headers
