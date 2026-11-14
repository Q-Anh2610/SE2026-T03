import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.ingestion.export_metadata import ExportPrincipal, ExportRequest, authorize


def test_u01_authorize_granted_source():
    assert authorize(ExportPrincipal(True, frozenset({'objaverse'})), 'objaverse') is None


@pytest.mark.parametrize('principal,source,expected', [
    (None, 'objaverse', 401),
    (ExportPrincipal(False, frozenset({'objaverse'})), 'objaverse', 403),
    (ExportPrincipal(True, frozenset({'objaverse'})), 'abo', 403),
    (ExportPrincipal(True, frozenset()), 'objaverse', 403),
])
def test_u02_authorization_rejects_each_invalid_partition(principal, source, expected):
    with pytest.raises(HTTPException) as error:
        authorize(principal, source)
    assert error.value.status_code == expected


def test_u03_request_boundaries_and_normalization():
    assert ExportRequest(source=' objaverse ', limit=1).source == 'objaverse'
    assert ExportRequest(source='x'*64, limit=2000).limit == 2000
    with pytest.raises(ValidationError):
        ExportRequest(source='objaverse', limit=2001)


def test_u04_existing_ci_test_database_is_supported(monkeypatch):
    from .conftest import test_url
    monkeypatch.delenv('VT011_DATABASE_URL', raising=False)
    value='postgresql+psycopg://ci_user@127.0.0.1/test_backend'
    monkeypatch.setenv('TEST_DATABASE_URL', value)
    assert test_url() == value


def test_u05_non_test_database_is_rejected(monkeypatch):
    from .conftest import test_url
    monkeypatch.delenv('VT011_DATABASE_URL', raising=False)
    monkeypatch.setenv('TEST_DATABASE_URL','postgresql+psycopg://ci_user@127.0.0.1/production')
    with pytest.raises(pytest.fail.Exception):
        test_url()
