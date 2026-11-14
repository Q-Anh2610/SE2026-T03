from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

URL = '/api/v1/exports/assets'


def download(client, token='fixture-a', source='objaverse', **extras):
    headers = {} if token is None else {'Authorization': 'Bearer ' + token}
    return client.post(URL, headers=headers, json={'source': source, **extras})


def test_t01_download_contract(client):
    response = download(client)
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/json')
    assert response.headers['content-disposition'] == 'attachment; filename="assets.json"'
    assert response.headers['cache-control'] == 'no-store'
    body = response.json()
    assert body['source'] == 'objaverse'
    assert [row['asset_id'] for row in body['items']] == ['a-1', 'a-2']


@pytest.mark.parametrize('token', [None, 'invalid'])
def test_t02_t03_unauthenticated(client, token):
    response = download(client, token)
    assert response.status_code == 401
    assert 'content-disposition' not in response.headers


def test_t04_cannot_export_with_read_permission(client):
    assert download(client, 'fixture-reader').status_code == 403


def test_t05_cannot_export_other_source(client):
    response = download(client, source='abo')
    assert response.status_code == 403
    assert 'b-1' not in response.text


@pytest.mark.parametrize('body', [
    {}, {'source': ''}, {'source': ' '}, {'source': 'x'*65},
    {'source': 'objaverse', 'limit': 0}, {'source': 'objaverse', 'limit': 2001},
    {'source': 'objaverse', 'limit': True}, {'source': 'objaverse', 'limit': '2'},
    {'source': 'objaverse', 'role': 'admin'},
])
def test_t06_invalid_request(client, body):
    response = client.post(URL, headers={'Authorization': 'Bearer fixture-a'}, json=body)
    assert response.status_code == 400
    assert 'content-disposition' not in response.headers


def test_t07_empty_source_is_not_database_failure(client):
    result = download(client, 'fixture-empty', 'empty')
    assert result.status_code == 200
    assert result.json()['items'] == []


def test_t08_real_array_null_and_public_metadata(client):
    rows = download(client).json()['items']
    assert rows[0]['name'] == 'a-1'  # mapping hiện có, không bịa tên trong DB.
    assert rows[0]['face_count'] is None and rows[0]['license'] is None
    assert rows[0]['source_url'] is None
    assert rows[1]['name'] == 'Ghế gỗ'
    assert rows[1]['tags'] == ['gỗ', 'chair'] and rows[1]['formats'] == ['glb']
    assert rows[1]['thumbnail_url'] is None
    assert set(rows[0]) == {'asset_id','name','description','category','tags','formats',
        'face_count','thumbnail_url','source','source_url','author','license'}
    assert 'private' not in str(rows) and 'password' not in str(rows)


def test_t09_limit_boundary_and_overflow(client):
    overflow = download(client, limit=1)
    assert overflow.status_code == 413
    assert 'content-disposition' not in overflow.headers
    assert [r['asset_id'] for r in download(client, limit=2).json()['items']] == ['a-1','a-2']


def test_t10_database_schema_failure_is_visible(client, engine):
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE assets RENAME COLUMN tags TO tags_broken'))
    response = download(client)
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'EXPORT_UNAVAILABLE'
    assert 'tags_broken' not in response.text and 'SELECT' not in response.text
    assert 'content-disposition' not in response.headers


def test_t11_concurrent_scope_and_permission_isolation(app):
    barrier = Barrier(40, timeout=30)
    def worker(i):
        # 10 success A, 10 success B, 10 read-only, 10 forbidden source.
        cases = [('fixture-a','objaverse',200,['a-1','a-2']),
                 ('fixture-b','abo',200,['b-1']),
                 ('fixture-reader','objaverse',403,None),
                 ('fixture-a','abo',403,None)]
        token, source, expected, ids = cases[i % 4]
        with TestClient(app) as client:
            barrier.wait()
            response = download(client, token, source)
            assert response.status_code == expected
            if ids is not None:
                assert [r['asset_id'] for r in response.json()['items']] == ids
            else:
                assert 'content-disposition' not in response.headers
    with ThreadPoolExecutor(max_workers=40) as pool:
        list(pool.map(worker, range(40)))


def test_t12_denial_does_not_query_database(client, engine):
    statements=[]
    def record(*args):
        statements.append(args[2])
    event.listen(engine, 'before_cursor_execute', record)
    try:
        assert download(client, 'fixture-reader').status_code == 403
        assert download(client, source='abo').status_code == 403
        assert download(client, None).status_code == 401
        assert statements == []
    finally:
        event.remove(engine, 'before_cursor_execute', record)


def test_t13_client_headers_cannot_grant_permissions(client):
    response = client.post(URL, headers={
        'Authorization':'Bearer fixture-a','X-Role':'admin','X-Allowed-Sources':'abo'},
        json={'source':'abo'})
    assert response.status_code == 403


def test_t14_sql_injection_is_not_scope(client):
    response = download(client, source="objaverse' OR 1=1 --")
    assert response.status_code == 403
    assert 'b-1' not in response.text


def test_t16_export_has_no_lazy_load_queries(client, engine):
    statements=[]
    def record(*args):
        statements.append(args[2])
    event.listen(engine, 'before_cursor_execute', record)
    try:
        response=download(client)
        assert response.status_code == 200
        assert len(response.json()['items']) == 2
        assert len(statements) == 1  # Không N+1 khi mapping metadata sau projection.
    finally:
        event.remove(engine, 'before_cursor_execute', record)
