"""Kiểm contract các profile tài liệu; không nạp model hoặc truy cập DB."""

import json
from pathlib import Path

from fastapi.routing import APIRoute
from pydantic import TypeAdapter
import pytest

from app.core.config import Settings
from app.export_openapi import contract_app
from app.main import create_app
from app.schemas.api import ErrorResponse

ROOT = Path(__file__).resolve().parents[3]
PROFILES = [
    ('openapi.json', 'mock', 'mock', 'mock'),
    ('openapi-text-search.json', 'service', 'mock', 'mock'),
    ('openapi-image-search.json', 'service', 'service', 'mock'),
    ('openapi-feedback.json', 'service', 'service', 'database'),
]


@pytest.mark.parametrize('filename,text,image,feedback', PROFILES)
def test_documented_profiles_match_exports_examples_and_frontend_feedback_discovery(filename, text, image, feedback):
    app = contract_app(text_search_source=text, image_search_source=image, feedback_source=feedback)
    schema = app.openapi()
    assert json.loads((ROOT / 'docs' / filename).read_text(encoding='utf-8')) == schema
    expected = {
        '/healthz', '/api/v1/assets', '/api/v1/assets/{asset_id}',
        '/api/v1/search/text', '/api/v1/search/image', '/api/v1/feedback',
        '/api/v1/admin/jobs', '/api/v1/admin/jobs/{job_id}', '/api/v1/admin/reindex',
    }
    assert set(schema['paths']) == expected
    feedback_schema = schema['paths']['/api/v1/feedback']['post']['responses']['201']['content']['application/json']['schema']
    assert feedback_schema['$ref'] == '#/components/schemas/' + ('LiveFeedbackResponse' if feedback == 'database' else 'FeedbackResponse')

    def refs(node):
        if isinstance(node, dict):
            if '$ref' in node:
                assert node['$ref'].startswith('#/')
                target = schema
                for part in node['$ref'][2:].split('/'):
                    target = target[part.replace('~1', '/').replace('~0', '~')]
            for value in node.values():
                refs(value)
        elif isinstance(node, list):
            for value in node:
                refs(value)
    refs(schema)
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            operation = schema['paths'][route.path][method.lower()]
            assert '422' not in operation['responses']
            for status, response in operation['responses'].items():
                content = response.get('content', {}).get('application/json', {})
                if 'example' not in content:
                    continue
                model = ErrorResponse if int(status) >= 400 else route.response_model
                TypeAdapter(model).validate_python(content['example'])
    # Constructor/OpenAPI không chạy lifespan hay dựng adapter/DB.
    assert app.state.db_engine is None and app.state.text_search_service is None
    assert app.state.image_search_service is None


@pytest.mark.parametrize('production,enabled', [(True, True), (True, False), (False, False)])
def test_disabled_mock_does_not_advertise_search_or_feedback_routes(production, enabled):
    app = create_app(Settings(_env_file=None, env='production' if production else 'test',
        mock_api_enabled=enabled, text_search_source='mock', image_search_source='mock', feedback_source='mock'))
    paths = app.openapi()['paths']
    assert '/api/v1/assets' in paths
    assert not {'/api/v1/search/text', '/api/v1/search/image', '/api/v1/feedback'} & paths.keys()


def test_service_profile_survives_production_without_enabling_mock():
    app = create_app(Settings(_env_file=None, env='production', mock_api_enabled=False,
        asset_list_source='fixture', text_search_source='service', image_search_source='service', feedback_source='database'))
    schema = app.openapi()
    assert {'/api/v1/search/text', '/api/v1/search/image', '/api/v1/feedback'} <= schema['paths'].keys()
    assert schema['paths']['/api/v1/assets']['get']['responses']['200']['content']['application/json']['example']['mock'] is False
    assert app.state.db_engine is None
