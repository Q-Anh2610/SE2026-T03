"""Fault injection runner; không nạp weights, ghi DB hay dựng index thật."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.jobs import JobResult
from app.services import job_runner, reindex
from app.services.job_runner import Outcome
from sqlalchemy.exc import SQLAlchemyError


@pytest.mark.parametrize('outcome', [None, Outcome(JobResult(exit_code=3)),
    Outcome(JobResult(failed=1)), Outcome(JobResult(search_verified=False)),
    Outcome(JobResult(), processed=2, total=1)])
def test_invalid_outcome_becomes_failed_instead_of_succeeded_or_stuck(monkeypatch, outcome):
    stored = []
    monkeypatch.setattr(reindex, 'start_job', lambda *_: None)
    monkeypatch.setattr(reindex, 'finish_job', lambda *_, **values: stored.append(values))
    manager = reindex.ReindexManager(None, None, operation=lambda *_: outcome)
    try:
        manager.work(uuid4())
    finally:
        manager.close()
    assert len(stored) == 1
    assert stored[0]['error']['code'] == 'RUNNER_OUTPUT_INVALID'
    assert stored[0].get('result') is None


def test_unknown_failure_code_cannot_leak_to_database_or_log(monkeypatch, caplog):
    stored = []
    monkeypatch.setattr(reindex, 'start_job', lambda *_: None)
    monkeypatch.setattr(reindex, 'finish_job', lambda *_, **values: stored.append(values))
    def fail(*_):
        raise reindex.ReindexFailure('private-password-or-path')
    manager = reindex.ReindexManager(None, None, operation=fail)
    try:
        manager.work(uuid4())
    finally:
        manager.close()
    assert stored[0]['error']['code'] == 'RUNNER_FAILED'
    assert 'private-password-or-path' not in caplog.text + str(stored)


def test_cli_invalid_outcome_is_durable_failure(monkeypatch):
    stored = []
    monkeypatch.setattr(job_runner, 'create_job', lambda *_, **__: uuid4())
    monkeypatch.setattr(job_runner, 'start_job', lambda *_: None)
    monkeypatch.setattr(job_runner, 'finish_job', lambda *_, **values: stored.append(values))
    _, succeeded = job_runner.execute_job(None, kind='indexing', runner='fixture',
        operation=lambda: Outcome(JobResult(exit_code=1)))
    assert succeeded is False
    assert stored[0]['error']['code'] == 'RUNNER_OUTPUT_INVALID'


@pytest.mark.parametrize('failure,expected_stage,code', [
    (RuntimeError('private-fixture'), 'operation', 'RUNNER_FAILED'),
    (reindex.ReindexFailure('REINDEX_TIMEOUT'), 'runner_timeout', 'REINDEX_TIMEOUT'),
    (reindex.ReindexFailure('INDEXING_FAILED'), 'runner_exit', 'INDEXING_FAILED'),
    (reindex.ReindexFailure('REINDEX_OUTPUT_INVALID'), 'artifact', 'REINDEX_OUTPUT_INVALID'),
    (reindex.ReindexFailure('REINDEX_INPUT_INVALID'), 'input', 'REINDEX_INPUT_INVALID'),
])
@pytest.mark.parametrize('commit_fails', [False, True])
def test_operation_and_failure_state_are_diagnosed_separately(monkeypatch, caplog, failure, expected_stage, code, commit_fails):
    identifier = uuid4()
    monkeypatch.setattr(reindex, 'start_job', lambda *_: None)
    def finish(*_, **__):
        if commit_fails:
            raise SQLAlchemyError('private-fixture')
    monkeypatch.setattr(reindex, 'finish_job', finish)
    def fail(*_):
        raise failure
    manager = reindex.ReindexManager(None, None, operation=fail)
    try:
        manager.work(identifier)
    finally:
        manager.close()
    records = [json.loads(r.message) for r in caplog.records if r.name == reindex.logger.name]
    assert records[0]['job_id'] == str(identifier)
    assert records[0]['stage'] == expected_stage and records[0]['error_code'] == code
    assert records[0]['request_id'] is None
    assert len(records) == (2 if commit_fails else 1)
    if commit_fails:
        assert records[1]['stage'] == 'failure_state'
        assert records[1]['error_code'] == 'JOB_STATE_UNAVAILABLE'
        assert records[1]['operation_error_code'] == code
        assert records[1]['intended_status'] == 'failed'
    assert 'private-fixture' not in caplog.text


@pytest.mark.parametrize('phase', ['create', 'start', 'failure', 'final'])
def test_cli_state_errors_propagate_without_false_success(monkeypatch, caplog, phase):
    identifier = uuid4()
    calls = []
    def fail(*_, **__):
        raise SQLAlchemyError('private-cli-fixture')
    monkeypatch.setattr(job_runner, 'create_job', fail if phase == 'create' else lambda *_, **__: identifier)
    monkeypatch.setattr(job_runner, 'start_job', fail if phase == 'start' else lambda *_: None)
    monkeypatch.setattr(job_runner, 'finish_job', fail)
    def operation():
        calls.append(True)
        if phase == 'failure':
            raise RuntimeError('private-cli-fixture')
        return Outcome(JobResult(exit_code=0))
    with pytest.raises(SQLAlchemyError):
        job_runner.execute_job(None, kind='indexing', runner='fixture', operation=operation)
    assert len(calls) == (0 if phase in ('create', 'start') else 1)
    records = [json.loads(r.message) for r in caplog.records if r.name == job_runner.logger.name]
    assert records[-1]['stage'] == {'create': 'create_state', 'start': 'start_state',
                                  'failure': 'failure_state', 'final': 'final_state'}[phase]
    assert records[-1]['job_id'] == (None if phase == 'create' else str(identifier))
    assert 'private-cli-fixture' not in caplog.text


@pytest.mark.parametrize('bad', ['source', 'model', 'snapshot', 'count', 'dimension',
    'hashes', 'check_failed', 'check_versions', 'collection', 'missing_check', 'valid'])
def test_artifact_checks_gate_success_after_child_exit_zero(monkeypatch, tmp_path, bad):
    """Child/store là fixture; kiểm các guard thực tế của run_index."""
    from app.schemas.text_search import SearchExecutionVersions
    from app.core.config import Settings
    from app.search import index_manifest
    import qdrant_client
    ready = tmp_path / 'ready.json'
    ready.write_text('[]', encoding='utf-8')
    identifier = uuid4()
    version = 'reindex-clip-' + identifier.hex
    output = tmp_path / str(identifier)
    output.mkdir()
    (output / 'index-manifest.json').write_text('{}', encoding='utf-8')
    versions = SearchExecutionVersions(model_version=reindex.MODEL,
        index_version=version, config_version='clip-text-exact-all-filtered-v1-k200',
        dataset_snapshot=reindex.SNAPSHOT + '-sha256:' + reindex.SOURCE_HASH)
    if bad == 'model':
        versions = versions.model_copy(update={'model_version': 'fixture-wrong-model'})
    if bad == 'snapshot':
        versions = versions.model_copy(update={'dataset_snapshot': 'fixture-wrong-snapshot'})
    check = {'passed': bad != 'check_failed', 'hit_count': 200,
             'versions': {} if bad == 'check_versions' else versions.model_dump()}
    if bad != 'missing_check':
        (output / 'search-check.json').write_text(json.dumps(check), encoding='utf-8')
    def fail_hashes(*_):
        if bad == 'hashes':
            raise ValueError('private-artifact-fixture')
    def validate_collection():
        if bad == 'collection':
            raise ValueError('private-artifact-fixture')
    manifest = SimpleNamespace(source_manifest_sha256='wrong' if bad == 'source' else reindex.SOURCE_HASH,
        asset_count=199 if bad == 'count' else 200, point_count=200, collection='fixture',
        verify_input_hashes=fail_hashes, execution_versions=lambda: versions,
        as_index_config=lambda: SimpleNamespace(dimension=1 if bad == 'dimension' else 512,
            preprocessing_version='clip-slow-processor-rgb-l2-v1'),
        make_store=lambda _: SimpleNamespace(validate_collection=validate_collection))
    monkeypatch.setattr(index_manifest, 'load_index_manifest', lambda _: manifest)
    monkeypatch.setattr(reindex.subprocess, 'run', lambda *_, **__: SimpleNamespace(returncode=0))
    monkeypatch.setattr(qdrant_client, 'QdrantClient', lambda **_: SimpleNamespace(
        close=lambda: None, count=lambda *_, **__: SimpleNamespace(count=200)))
    settings = Settings(_env_file=None, reindex_enabled=True, reindex_cache_ready=ready, reindex_output_root=tmp_path)
    if bad == 'valid':
        assert reindex.run_index(settings, identifier).result.search_verified is True
    else:
        with pytest.raises(reindex.ReindexFailure) as raised:
            reindex.run_index(settings, identifier)
        assert raised.value.code == 'REINDEX_OUTPUT_INVALID'
