"""Mỗi test có schema PG riêng và migration thật; không đụng DB nhóm."""
import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import Session

from app.models import Asset
from .api import create_export_app


def test_url():
    dedicated = os.environ.get('VT011_DATABASE_URL')
    value = dedicated or os.environ.get('TEST_DATABASE_URL')
    if not value:
        pytest.skip('Set VT011_DATABASE_URL to an isolated PostgreSQL test_vt011_* DB.')
    url = make_url(value)
    required_prefix = 'test_vt011_' if dedicated else 'test_'
    if (url.drivername != 'postgresql+psycopg'
            or not (url.database or '').startswith(required_prefix)):
        pytest.fail('Export tests require PostgreSQL + psycopg and an explicitly isolated test database.')
    return value


@contextmanager
def isolated_database():
    url = test_url()
    schema = 'vt011_' + uuid4().hex
    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, hide_parameters=True,
        connect_args={'options': '-csearch_path=' + schema, 'connect_timeout': 5},
        pool_size=40, max_overflow=0, pool_timeout=10)
    try:
        config = Config(str(Path(__file__).resolve().parents[2] / 'alembic.ini'))
        with engine.begin() as connection:
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
        with Session(engine) as session:
            session.add_all([
                Asset(asset_id='a-2', source='objaverse', source_id='2', name='Ghế gỗ',
                      tags=['gỗ', 'chair'], formats=['glb'], face_count=12, license='CC-BY',
                      model_path='C:/private/model.glb', thumbnail_path='C:/private/preview.png'),
                Asset(asset_id='a-1', source='objaverse', source_id='1', name=None,
                      tags=[], formats=[], face_count=None, license=None,
                      source_url='https://user:password@example.test/private'),
                Asset(asset_id='b-1', source='abo', source_id='3', name='Bàn',
                      tags=['table'], formats=['gltf'], face_count=20, license='CC0'),
            ])
            session.commit()
        yield engine
    finally:
        engine.dispose()
        # Schema ngẫu nhiên được chính fixture tạo trong DB test_vt011_* đã validate.
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def engine():
    with isolated_database() as engine:
        yield engine


@pytest.fixture
def grants():
    # Fixture grants, không phải password/token production.
    return {
        'fixture-a': {'can_export': True, 'sources': frozenset({'objaverse'})},
        'fixture-b': {'can_export': True, 'sources': frozenset({'abo'})},
        'fixture-reader': {'can_export': False, 'sources': frozenset({'objaverse'})},
        'fixture-empty': {'can_export': True, 'sources': frozenset({'empty'})},
    }


@pytest.fixture
def app(engine, grants):
    return create_export_app(engine, grants)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client
