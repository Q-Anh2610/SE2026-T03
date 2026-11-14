"""Reproducible 40 concurrent HTTP/TCP export requests, not a mock benchmark."""
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from threading import Barrier
from time import perf_counter
import math
import platform

import httpx2
from sqlalchemy import delete, insert, text

from app.models import Asset
from .api import create_export_app
from .conftest import isolated_database
from .server import live_server


def run_load(rounds=5, rows_per_source=1000):
    samples=[]
    with isolated_database() as engine:
        with engine.begin() as connection:
            connection.execute(delete(Asset))
            connection.execute(insert(Asset), [
                {'asset_id': f'{source}-{i:04d}', 'source': source, 'source_id': str(i),
                 'name':'Ghế gỗ', 'tags':['chair','gỗ'], 'formats':['glb'],
                 'license':'CC-BY', 'face_count':None}
                for source in ('objaverse','abo') for i in range(rows_per_source)])
            pg_version = connection.scalar(text('SHOW server_version'))
        app = create_export_app(engine, {
            'fixture-a': {'can_export':True, 'sources':{'objaverse'}},
            'fixture-b': {'can_export':True, 'sources':{'abo'}},
        })
        with live_server(app) as url:
            for round_id in range(rounds):
                barrier = Barrier(40, timeout=30)
                def worker(i):
                    source = 'objaverse' if i % 2 == 0 else 'abo'
                    token = 'fixture-a' if i % 2 == 0 else 'fixture-b'
                    with httpx2.Client(base_url=url, trust_env=False, timeout=30) as client:
                        barrier.wait()
                        start=perf_counter()
                        response=client.post('/api/v1/exports/assets',
                            headers={'Authorization':'Bearer '+token},
                            json={'source':source,'limit':rows_per_source})
                        elapsed=perf_counter()-start  # includes complete response body over TCP.
                        body=response.json()
                        correct=(response.status_code == 200 and
                            [r['asset_id'] for r in body.get('items',[])] ==
                            [f'{source}-{j:04d}' for j in range(rows_per_source)] and
                            all(r['source']==source for r in body.get('items',[])))
                        return {'round':round_id+1,'worker':i,'source':source,
                                'seconds':elapsed,'status':response.status_code,
                                'bytes':len(response.content),'correct':correct}
                with ThreadPoolExecutor(max_workers=40) as pool:
                    samples.extend(pool.map(worker,range(40)))
    values=sorted(sample['seconds'] for sample in samples)
    p95=lambda a: sorted(a)[math.ceil(.95*len(a))-1]
    return {'mode':'HTTP/TCP loopback -> Uvicorn -> service -> migrated PostgreSQL; fixture auth',
        'python':platform.python_version(),'platform':platform.platform(),
        'postgresql':pg_version,'packages':{n:version(n) for n in
            ('fastapi','SQLAlchemy','psycopg','alembic','uvicorn','httpx2','pytest')},
        'concurrency':40,'rounds':rounds,'samples':len(samples),
        'dataset_rows':rows_per_source*2,'export_rows_per_request':rows_per_source,
        'p95_method':'nearest rank: sorted[ceil(.95*n)-1]',
        'p95_seconds':p95(values),'max_seconds':values[-1],
        'round_p95_seconds':[p95([s['seconds'] for s in samples if s['round']==r+1]) for r in range(rounds)],
        'errors':sum(not s['correct'] for s in samples),'target_seconds':1.5,
        'raw':samples}
