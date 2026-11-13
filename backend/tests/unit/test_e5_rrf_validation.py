"""Runner #91: dữ liệu/encoder fixture; không mở queries/qrels benchmark thật."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
import csv
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.search.experimental_text_search import (
    ExperimentalFusionService, RankedCandidate, SourceProvenance, SourceRanking,
)
from app.search.rrf import CLIP_SOURCE, E5_SOURCE, RRFConfig
from app.search.vector_search import SearchUnavailableError
from evaluation import e5_rrf_validation as runner
from scripts import run_e5_rrf_validation as cli
from test_experimental_text_search import pair  # Existing real-Qdrant fixture, not model weights.


def csv_bytes(rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


class Dataset:
    def __init__(self, root, assets=None):
        self.root = root
        self.paths = {"manifest": root / "data/benchmark/manifest.yaml",
            "queries": root / "data/benchmark/queries.csv", "qrels": root / "data/benchmark/qrels.csv",
            "candidates": root / "data/manifests/objaverse_200.json"}
        for path in self.paths.values(): path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path = root / "config.json"
        self.assets = assets if assets is not None else [{"asset_id": f"asset_{i:03d}", "name": f"fixture {i}"} for i in range(200)]
        self.queries = [{"query_id": f"q{i:03d}", "query_type": "text", "language": "en",
            "query_group_id": f"{'validation' if i < 28 else 'test'}-{i // 7}",
            "split": "validation" if i < 28 else "test",
            "query_text": f"fixture query {i}" if i < 28 else f"TEST_TEXT_MUST_NEVER_RUN_{i}"} for i in range(70)]
        self.qrels = [{"query_id": q["query_id"], "asset_id": f"asset_{a:03d}",
            "relevance": str(2 if i == 0 and a == 0 else int((i < 21 and a == 0) or (i == 0 and a == 1)))
                if i < 28 else "TEST_LABEL_MUST_NOT_INFLUENCE_VALIDATION"}
            for i, q in enumerate(self.queries) for a in range(200)]
        self.config = {"schema_version": "issue91-validation-config-v1", "protocol": deepcopy(runner.PROTOCOL),
            # Deliberately fictional URL inside a clearly labelled fixture run.
            "input_confirmation": {"status": "confirmed", "evidence_url": "https://github.com/Q-Anh2610/SE2026-T03/issues/91#issuecomment-0",
                                   "queries_byte_policy": {"bom": False, "newline": "LF", "final_newline": True}},
            "paths": {k: v.relative_to(root).as_posix() for k, v in self.paths.items()}, "expected_sha256": {}}
        self.save()

    def save(self):
        self.paths["queries"].write_bytes(csv_bytes(self.queries, list(self.queries[0])))
        self.paths["qrels"].write_bytes(csv_bytes(self.qrels, ["query_id", "asset_id", "relevance"]))
        self.paths["candidates"].write_bytes(runner.encoded(self.assets))
        self.refresh_fixture_pins()

    def refresh_fixture_pins(self):
        pins = {name: runner.sha(self.paths[key].read_bytes()) for key, name in
                (("queries", "queries.csv"), ("qrels", "qrels.csv"), ("candidates", "candidate_metadata"))}
        self.config["expected_sha256"] = pins
        self.paths["manifest"].write_text(
            "benchmark_version: home-interior-text-v2\n"
            f"snapshot_manifest_sha256: {pins['candidate_metadata']}\n"
            f"locked_files_sha256:\n  queries.csv: {pins['queries.csv']}\n  qrels.csv: {pins['qrels.csv']}\n", encoding="utf-8")
        self.save_config()

    def save_config(self):
        self.config_path.write_bytes(runner.encoded(self.config))

    def load(self):
        return runner.load_inputs(self.config_path, self.root)


@pytest.fixture
def dataset(tmp_path):
    return Dataset(tmp_path / "fixture-inputs")


class FixtureSource:
    def __init__(self, inputs, source):
        self.source, self.inputs = source, inputs
        self.asset_ids, self.metadata = inputs.candidate_ids, inputs.metadata
        self.source_hash = inputs.hashes["candidate_metadata"]
        self.snapshot = f"{runner.PROTOCOL['snapshot']}-sha256:{self.source_hash}"
        self.manifest = SimpleNamespace(corpus_sha256="a" * 64, recipe_version="fixture-only")
        ids = self.asset_ids if source == CLIP_SOURCE else tuple(reversed(self.asset_ids))
        self.hits = tuple(RankedCandidate(aid, i, (201-i)/200) for i, aid in enumerate(ids, 1))
        self.calls = []

    def provenance(self, limit):
        return SourceProvenance(self.source, "fixture-encoder", "f" * 40, "fixture-index",
            f"fixture-{self.source}-k{limit}", self.snapshot, self.source_hash,
            "fixture-index-manifest.json", "b" * 64, "fixture-collection", "fixture-vector", limit,
            "a" * 64 if self.source == E5_SOURCE else None,
            "fixture-only" if self.source == E5_SOURCE else None,
            "c" * 64 if self.source == E5_SOURCE else None)

    def search_text(self, query, filters, *, candidate_limit):
        assert query in {q.text for q in self.inputs.queries}
        actual_filters = filters.model_dump(exclude_none=True) if hasattr(filters, "model_dump") else filters
        assert actual_filters == {} and candidate_limit == 200
        self.calls.append(query)
        return SourceRanking(self.source, self.hits, {}, self.provenance(200))


def services(inputs):
    return ExperimentalFusionService(FixtureSource(inputs, CLIP_SOURCE), FixtureSource(inputs, E5_SOURCE))


def factory_for(fusion, state=None, after=None):
    state = state if state is not None else {}
    @contextmanager
    def factory(output):
        state["opened"] = state.get("opened", 0) + 1
        try:
            yield fusion
            if after is not None: after()
        finally:
            state["closed"] = state.get("closed", 0) + 1
    return factory


def test_loads_only_28_validation_queries_and_never_uses_test_text_or_labels(dataset):
    data = dataset.load()
    assert len(data.queries) == 28 and len(data.candidate_ids) == 200
    assert sum(bool(q.relevant_ids) for q in data.queries) == 21
    assert data.queries[0].relevant_ids == ("asset_000", "asset_001")
    assert all("TEST_TEXT" not in q.text for q in data.queries)
    assert data.hashes["queries.csv"] == runner.sha(dataset.paths["queries"].read_bytes())


@pytest.mark.parametrize("status", ["pending", "draft", None])
def test_unconfirmed_gate_precedes_csv_reads_and_factory(dataset, monkeypatch, capsys, status):
    dataset.config["input_confirmation"]["status"] = status
    dataset.save_config()
    dataset.paths["queries"].unlink(); dataset.paths["qrels"].unlink()
    factory = Mock(side_effect=AssertionError("must not load models"))
    monkeypatch.setattr(cli, "real_service_factory", factory)
    assert cli.main(["--config", str(dataset.config_path), "--preflight-only"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "canonical_query_artifact_not_confirmed"
    factory.assert_not_called()


def test_locked_hash_mismatch_precedes_csv_parse(dataset, monkeypatch):
    dataset.paths["queries"].write_bytes(dataset.paths["queries"].read_bytes() + b"\n")
    monkeypatch.setattr(runner, "_csv", Mock(side_effect=AssertionError("must not parse")))
    with pytest.raises(ValueError, match="hash mismatch"):
        dataset.load()


@pytest.mark.parametrize("change", ["bom", "newline", "final_newline", "mixed_newlines"])
def test_byte_policy_is_exact_without_normalizing_hash(dataset, change):
    raw = dataset.paths["queries"].read_bytes()
    if change == "bom": raw = b"\xef\xbb\xbf" + raw
    elif change == "newline": raw = raw.replace(b"\n", b"\r\n")
    elif change == "final_newline": raw = raw.rstrip(b"\n")
    else: raw = raw.replace(b"\n", b"\r\n", 1)
    dataset.paths["queries"].write_bytes(raw)
    dataset.refresh_fixture_pins()
    with pytest.raises(ValueError, match="newline"):
        dataset.load()


def test_confirmed_bom_crlf_is_recorded_not_silently_converted(dataset):
    raw = b"\xef\xbb\xbf" + dataset.paths["queries"].read_bytes().replace(b"\n", b"\r\n")
    dataset.paths["queries"].write_bytes(raw)
    dataset.config["input_confirmation"]["queries_byte_policy"].update(bom=True, newline="CRLF")
    dataset.refresh_fixture_pins()
    assert dataset.load().hashes["queries.csv"] == runner.sha(raw)


@pytest.mark.parametrize("change", ["split_count", "duplicate_id", "group_overlap", "language", "empty_query"])
def test_query_protocol_corruption_is_rejected(dataset, change):
    if change == "split_count": dataset.queries[0]["split"] = "test"
    elif change == "duplicate_id": dataset.queries[0]["query_id"] = dataset.queries[1]["query_id"]
    elif change == "group_overlap": dataset.queries[-1]["query_group_id"] = dataset.queries[0]["query_group_id"]
    elif change == "language": dataset.queries[0]["language"] = "vi"
    else: dataset.queries[0]["query_text"] = " "
    dataset.save()
    with pytest.raises(ValueError): dataset.load()


@pytest.mark.parametrize("change", ["duplicate", "unknown_query", "unknown_asset", "missing", "invalid_label", "no_positive_count"])
def test_qrels_completeness_and_validation_labels_are_checked(dataset, change):
    if change == "duplicate": dataset.qrels.append(dataset.qrels[0].copy())
    elif change == "unknown_query": dataset.qrels[0]["query_id"] = "unknown"
    elif change == "unknown_asset": dataset.qrels[0]["asset_id"] = "unknown"
    elif change == "missing": dataset.qrels.pop(0)
    elif change == "invalid_label": dataset.qrels[0]["relevance"] = "3"
    else: dataset.qrels[200]["relevance"] = "0"  # q001 loses its only positive.
    dataset.save()
    with pytest.raises(ValueError): dataset.load()


@pytest.mark.parametrize("change", ["candidate_count", "duplicate_candidate", "protocol", "approval", "escape_path", "hash_pin"])
def test_input_config_and_candidate_mismatches_are_rejected(dataset, change):
    if change == "candidate_count": dataset.assets.pop()
    elif change == "duplicate_candidate": dataset.assets[-1] = dataset.assets[0].copy()
    elif change == "protocol": dataset.config["protocol"]["warmup_per_configuration"] = 5.0
    elif change == "approval": dataset.config["input_confirmation"]["evidence_url"] = "https://example.com/approval"
    elif change == "escape_path": dataset.config["paths"]["queries"] = "../queries.csv"
    else: dataset.config["expected_sha256"]["queries.csv"] = "0" * 64
    if change in ("candidate_count", "duplicate_candidate"): dataset.save()
    else: dataset.save_config()
    with pytest.raises(ValueError): dataset.load()


def test_nearest_rank_known_answers_and_280_denominator():
    summary = runner.nearest_rank_summary(list(range(1, 281)))
    assert summary == {"method": "nearest-rank", "sample_count": 280, "p50_ms": 140, "p95_ms": 266}


@pytest.mark.parametrize("values", [[], [-1], [float("nan")], [True], ["1"]])
def test_invalid_latency_samples_are_rejected(values):
    with pytest.raises(ValueError): runner.nearest_rank_summary(values)


def test_complete_fixture_run_exports_raw_metrics_and_exact_protocol(dataset, tmp_path):
    inputs = dataset.load(); fusion = services(inputs); state = {}
    ticks = iter(range(0, 2 * 840 * 1000, 1000)); clock = lambda: next(ticks)
    output = tmp_path / "fixture-output"
    report = runner.run_validation(inputs, factory_for(fusion, state), output, rank_constant=60,
        context={"label": "fixture providers; actual product RRF orchestration; synthetic clock"}, clock_ns=clock)
    assert report["status"] == "passed" and report["execution_kind"] == "fixture" and report["benchmark"] is False
    assert report["configuration_selected_by_validation"] is False
    assert report["errors"] == [] and all(not qids for qids in report["skipped_queries"].values())
    assert state == {"opened": 1, "closed": 1}
    assert len(fusion.clip.calls) == len(fusion.e5.calls) == 570  # own 285 + orchestration 285
    raw = [json.loads(line) for line in (output / "raw-rankings.jsonl").read_text(encoding="utf-8").splitlines()]
    samples = [json.loads(line) for line in (output / "latency-samples.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(raw) == 84 and len(samples) == 840
    assert all(len(row["result"]["hits"]) == 200 and row["split"] == "validation" for row in raw)
    for name in ("run.json", "raw-rankings.jsonl", "latency-samples.jsonl"):
        assert "TEST_TEXT" not in (output / name).read_text(encoding="utf-8")
    for mode, entry in report["configurations"].items():
        assert entry["status"] == "passed" and entry["completed_samples"] == 280
        assert entry["warmup_query_ids"] == [q.query_id for q in inputs.queries[:5]]
        assert entry["latency"]["p50_ms"] == entry["latency"]["p95_ms"] == .001
        assert entry["metrics"]["recall@5"]["defined_query_count"] == 21
        assert len(entry["metrics"]["hit@5"]["per_query"]) == len(entry["metrics"]["ndcg@10"]["per_query"]) == 28
    assert report["configurations"]["clip_only"]["metrics"]["recall@5"]["macro_average"] == 1
    assert report["configurations"]["clip_only"]["metrics"]["hit@5"]["macro_average"] == 21/28
    for name, digest in report["files_sha256"].items(): assert runner.sha((output / name).read_bytes()) == digest
    assert json.loads((output / "run.json").read_text(encoding="utf-8")) == report


@pytest.mark.parametrize("value", [True, 0, 9, 61, "60", 60.0])
def test_rank_constant_must_be_an_explicit_allowed_integer(dataset, tmp_path, value):
    factory = Mock(side_effect=AssertionError("no load")); output = tmp_path / "invalid-k"
    with pytest.raises(ValueError): runner.run_validation(dataset.load(), factory, output, rank_constant=value)
    factory.assert_not_called(); assert not output.exists()


def test_existing_output_is_not_overwritten(dataset, tmp_path):
    output = tmp_path / "existing"; output.mkdir(); (output / "sentinel").write_text("keep")
    with pytest.raises(FileExistsError): runner.run_validation(dataset.load(), Mock(), output, rank_constant=10)
    assert (output / "sentinel").read_text() == "keep"


def test_source_failure_retains_partial_run_and_names_the_query(dataset, tmp_path, monkeypatch):
    inputs = dataset.load(); fusion = services(inputs); original = fusion.clip.search_text; calls = 0
    def failed(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 8: raise SearchUnavailableError("fixture_dependency_unavailable")
        return original(*args, **kwargs)
    monkeypatch.setattr(fusion.clip, "search_text", failed)
    output = tmp_path / "failed"; state = {}
    with pytest.raises(runner.ValidationRunFailed):
        runner.run_validation(inputs, factory_for(fusion, state), output, rank_constant=20)
    report = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed" and state["closed"] == 1
    assert report["errors"][0] == {"phase": "measurement", "configuration": "clip_only",
        "query_id": "q000", "repetition": 3, "error_type": "SearchUnavailableError", "reason": "fixture_dependency_unavailable"}
    assert report["configurations"]["clip_only"]["completed_samples"] == 2
    assert len(report["skipped_queries"]["clip_only"]) == 28
    assert len((output / "latency-samples.jsonl").read_text().splitlines()) == 2


def test_input_drift_after_search_invalidates_the_whole_run(dataset, tmp_path):
    inputs = dataset.load(); fusion = services(inputs); output = tmp_path / "input-drift"
    def mutate(): dataset.paths["qrels"].write_bytes(dataset.paths["qrels"].read_bytes() + b"\n")
    with pytest.raises(runner.ValidationRunFailed):
        runner.run_validation(inputs, factory_for(fusion, after=mutate), output, rank_constant=10)
    report = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed" and report["errors"][0]["phase"] == "input_integrity_after_run"


@pytest.mark.parametrize("change", ["duplicate", "short", "nan", "rank", "filters", "provenance", "ordering"])
def test_malformed_source_results_cannot_be_exported(dataset, change):
    inputs = dataset.load(); fusion = services(inputs)
    source = fusion.clip.search_text(inputs.queries[0].text, {}, candidate_limit=200)
    if change == "duplicate": source = replace(source, hits=(source.hits[0], replace(source.hits[0], rank=2), *source.hits[2:]))
    elif change == "short": source = replace(source, hits=source.hits[:-1])
    elif change == "nan": source = replace(source, hits=(replace(source.hits[0], score=float("nan")), *source.hits[1:]))
    elif change == "rank": source = replace(source, hits=(replace(source.hits[0], rank=2), *source.hits[1:]))
    elif change == "filters": source = replace(source, filters={"category": "wrong"})
    elif change == "provenance": source = replace(source, provenance=replace(source.provenance, index_version="wrong"))
    else: source = replace(source, hits=tuple(reversed(source.hits)))
    provenances = {s.source: json.loads(runner.encoded(asdict(s.provenance(200)))) for s in (fusion.clip, fusion.e5)}
    with pytest.raises(ValueError): runner._payload(source, "clip_only", inputs, provenances, RRFConfig(60, 200, 200, 200))


def test_runner_calls_current_service_dtos_with_real_qdrant_fixture(pair, tmp_path):
    inputs = Dataset(tmp_path / "actual-service-inputs", assets=pair.records).load()
    provenances = {s.source: json.loads(runner.encoded(asdict(s.provenance(200)))) for s in (pair.clip, pair.e5)}
    config = RRFConfig(60, 200, 200, 200)
    results = {mode: runner._payload(runner.invoke(pair.service, mode, "fixture query 0", config),
        mode, inputs, provenances, config) for mode in runner.MODES}
    for mode, raw_source in zip(runner.MODES[:2], results["clip_e5_rrf"]["raw_rankings"], strict=True):
        assert runner._repeat_check(results[mode], raw_source) == 0.0


def test_confirmed_preflight_only_never_constructs_service(dataset, monkeypatch, capsys):
    monkeypatch.setattr(cli, "ROOT", dataset.root)
    factory = Mock(side_effect=AssertionError("must not load"))
    monkeypatch.setattr(cli, "real_service_factory", factory)
    assert cli.main(["--config", str(dataset.config_path), "--preflight-only"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "inputs_verified" and result["models_loaded"] is False
    assert result["validation_queries"] == 28
    factory.assert_not_called()


def test_source_comparison_tolerates_only_documented_raw_cosine_roundoff(dataset):
    inputs = dataset.load(); fusion = services(inputs)
    original = json.loads(runner.encoded(asdict(fusion.e5.search_text(inputs.queries[0].text, {}, candidate_limit=200))))
    tiny = deepcopy(original); tiny["hits"][10]["score"] += 1e-14
    assert 0 < runner._repeat_check(original, tiny) < runner.COSINE_REPEAT_TOLERANCE
    large = deepcopy(original); large["hits"][10]["score"] += 1e-6
    with pytest.raises(ValueError, match="cosine"): runner._repeat_check(original, large)
    changed = deepcopy(original); changed["provenance"]["index_version"] = "changed"
    with pytest.raises(ValueError, match="provenance"): runner._repeat_check(original, changed)


def test_factory_setup_failure_is_saved_as_failed_not_empty_results(dataset, tmp_path):
    @contextmanager
    def unavailable(output):
        raise SearchUnavailableError("fixture_index_missing")
        yield
    output = tmp_path / "setup-failed"
    with pytest.raises(runner.ValidationRunFailed):
        runner.run_validation(dataset.load(), unavailable, output, rank_constant=60)
    report = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed" and report["errors"][0]["phase"] == "setup"
    assert all(entry["status"] == "not_started" for entry in report["configurations"].values())
    assert all(len(qids) == 28 for qids in report["skipped_queries"].values())
    assert (output / "raw-rankings.jsonl").read_bytes() == b""


def test_cli_hash_failure_reports_reason_without_loading_models(dataset, monkeypatch, capsys):
    monkeypatch.setattr(cli, "ROOT", dataset.root)
    dataset.paths["queries"].write_bytes(dataset.paths["queries"].read_bytes() + b"\n")
    factory = Mock(side_effect=AssertionError("must not load"))
    monkeypatch.setattr(cli, "real_service_factory", factory)
    assert cli.main(["--config", str(dataset.config_path), "--preflight-only"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["reason"] == "input_preflight_failed" and "hash mismatch" in result["detail"]
    assert result["models_loaded"] is False
    factory.assert_not_called()


def test_cli_factory_reuses_fixture_encoders_and_verifies_both_persisted_indexes(pair, tmp_path, monkeypatch):
    from qdrant_client import QdrantClient
    from app.search.qdrant_store import QdrantStore
    import app.embedding.clip_encoder as clip_module
    import app.embedding.e5_encoder as e5_module
    # Construct a second CLIP fixture storage; existing pair's CLIP is in memory.
    points, cursor = pair.clip_client.scroll(pair.clip.store.collection_name, limit=256, with_vectors=True)
    assert cursor is None
    client = QdrantClient(path=str(pair.clip_root / "qdrant"))
    try:
        store = QdrantStore(client, collection_name=pair.clip.store.collection_name, config=pair.clip.store.config)
        store.upsert([{"asset_id": p.payload["asset_id"], "metadata": pair.clip.metadata[p.payload["asset_id"]],
                       "vector": p.vector[pair.clip.store.vector_name]} for p in points])
    finally: client.close()
    pair.e5_client.close()  # Release fixture lock before the CLI factory owns it.
    clip_load, e5_load = Mock(return_value=pair.clip_encoder), Mock(return_value=pair.e5_encoder)
    monkeypatch.setattr(clip_module, "CLIPEncoder", clip_load)
    monkeypatch.setattr(e5_module, "E5Encoder", e5_load)
    args = SimpleNamespace(device="cpu", clip_index_root=pair.clip_root,
        clip_input_root=pair.clip_root, e5_index_root=pair.e5_root)
    output = tmp_path / "factory-output"; output.mkdir(); context = {"label": "fixture encoder lifecycle only"}
    with cli.real_service_factory(args, context)(output) as fusion:
        result = fusion.search_text("fixture query", {}, config=RRFConfig(60, 200, 200, 200))
        assert len(result.hits) == 200
    clip_load.assert_called_once_with(device="cpu", local_files_only=True)
    e5_load.assert_called_once_with(device="cpu", local_files_only=True)
    assert context["persisted_fingerprints_unchanged"] is True
    assert context["persisted_before"] == context["persisted_after_reopen"]
    assert (output / "clip-index-manifest.json").read_bytes() == (pair.clip_root / "index-manifest.json").read_bytes()
    assert (output / "e5-index-manifest.json").read_bytes() == (pair.e5_root / "index-manifest.json").read_bytes()
