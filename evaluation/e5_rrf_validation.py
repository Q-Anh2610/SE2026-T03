"""Protocol validation #91: gọi service sản phẩm, tái dùng metric W3.

Không chọn k tự động, không chạy split test, không sửa input đã khóa.
"""

from contextlib import ExitStack
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
from math import ceil, isfinite
from pathlib import Path
import re
from time import perf_counter_ns

from evaluation.run_keyword_baseline import compute_metrics, validate_locked_inputs


PROTOCOL = {
    "version": "issue91-validation-28-all200-v1",
    "benchmark_version": "home-interior-text-v2",
    "snapshot": "home-interior-clear-200-v3",
    "query_count": 70, "validation_count": 28, "test_count": 42,
    "candidate_count": 200, "positive_threshold": 1,
    "recall_defined_count": 21, "no_positive_count": 7,
    "source_window": 200, "cutoff": 200, "filters": {},
    "metric_cutoffs": [5, 10], "allowed_rrf_constants": [10, 20, 60],
    "warmup_per_configuration": 5, "repetitions_per_query": 10,
    "ordering": "configuration_then_csv_query_order_then_repetition",
    "raw_ranking_sample": "first_measured_repetition",
    "latency_scope": "service call including encode/retrieval/audits/fusion; excluding load/export/metrics",
    "percentile_method": "nearest-rank",
}
MODES = ("clip_only", "e5_only", "clip_e5_rrf")
COSINE_REPEAT_TOLERANCE = 1e-12


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class InputsNotConfirmed(ValueError):
    pass


class ValidationRunFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class ValidationQuery:
    query_id: str
    text: str
    group_id: str
    relevant_ids: tuple[str, ...]


@dataclass(frozen=True)
class ValidationInputs:
    queries: tuple[ValidationQuery, ...]
    candidate_ids: tuple[str, ...]
    metadata: dict
    hashes: dict
    config: dict
    files: dict[str, Path]
    config_bytes: bytes


def _csv(raw, required):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    fields = reader.fieldnames or []
    if len(set(fields)) != len(fields) or not required.issubset(fields):
        raise ValueError("CSV thiếu cột hoặc có cột trùng.")
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("CSV có dòng không đủ/thừa cột.")
        yield row


def _byte_policy(raw, policy):
    if (not isinstance(policy, dict) or set(policy) != {"bom", "newline", "final_newline"}
            or type(policy["bom"]) is not bool or type(policy["final_newline"]) is not bool
            or policy["newline"] not in ("LF", "CRLF")):
        raise ValueError("Cần xác nhận BOM/newline/final newline cụ thể.")
    bom = raw.startswith(b"\xef\xbb\xbf")
    body = raw[3:] if bom else raw
    newline = b"\n" if policy["newline"] == "LF" else b"\r\n"
    remaining = body.replace(newline, b"")
    if bom != policy["bom"] or b"\r" in remaining or b"\n" in remaining:
        raise ValueError("Query bytes không đúng BOM/newline đã xác nhận.")
    if body.endswith(newline) != policy["final_newline"]:
        raise ValueError("Query final newline không đúng xác nhận.")


def load_inputs(config_path: Path, repo: Path) -> ValidationInputs:
    """Chặn pending trước đọc CSV/nạp model; giữ nguyên bytes dùng để hash."""
    config_path, repo = Path(config_path).resolve(), Path(repo).resolve()
    raw_config = config_path.read_bytes()
    config = json.loads(raw_config.decode("utf-8-sig"))
    if (not isinstance(config, dict) or set(config) != {
            "schema_version", "protocol", "input_confirmation", "paths", "expected_sha256"}
            or config["schema_version"] != "issue91-validation-config-v1"):
        raise ValueError("Config validation không hợp lệ.")
    confirmation = config["input_confirmation"]
    if not isinstance(confirmation, dict) or set(confirmation) != {"status", "evidence_url", "queries_byte_policy"}:
        raise ValueError("Input confirmation không hợp lệ.")
    if confirmation["status"] != "confirmed":
        raise InputsNotConfirmed("canonical_query_artifact_not_confirmed")
    evidence = confirmation["evidence_url"]
    if not isinstance(evidence, str) or not re.fullmatch(
            r"https://github\.com/Q-Anh2610/SE2026-T03/(?:issues/91#issuecomment-[0-9]+|pull/[0-9]+(?:#[-a-z0-9]+)?)", evidence):
        raise ValueError("Cần liên kết xác nhận/review input thật trong repository.")
    if encoded(config["protocol"]) != encoded(PROTOCOL):
        raise ValueError("Protocol khác bản đã thống nhất; cần review trước chạy.")
    expected = config["expected_sha256"]
    if (not isinstance(expected, dict) or set(expected) != {"queries.csv", "qrels.csv", "candidate_metadata"}
            or any(not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for v in expected.values())):
        raise ValueError("Cần pins SHA-256 đầy đủ.")
    if not isinstance(config["paths"], dict) or set(config["paths"]) != {"manifest", "queries", "qrels", "candidates"}:
        raise ValueError("Config paths không hợp lệ.")
    files = {}
    for key, relative in config["paths"].items():
        if not isinstance(relative, str) or "\\" in relative:
            raise ValueError("Dùng đường dẫn tương đối portable.")
        path = (repo / relative).resolve()
        if Path(relative).is_absolute() or ".." in Path(relative).parts or not path.is_relative_to(repo):
            raise ValueError("Input phải nằm trong repository.")
        files[key] = path
    # Dùng nguyên validator lock hiện có; không tự chuẩn hóa để hash khớp.
    locked = validate_locked_inputs(PROTOCOL, files)
    if locked != expected:
        raise ValueError("Config pins không khớp input/manifest đã khóa.")
    contents = {key: path.read_bytes() for key, path in files.items()}
    for key, name in (("queries", "queries.csv"), ("qrels", "qrels.csv"), ("candidates", "candidate_metadata")):
        if sha(contents[key]) != expected[name]:
            raise ValueError("Input thay đổi trong preflight.")
    _byte_policy(contents["queries"], confirmation["queries_byte_policy"])
    assets = json.loads(contents["candidates"].decode("utf-8-sig"))
    if not isinstance(assets, list) or len(assets) != 200 or any(not isinstance(a, dict) for a in assets):
        raise ValueError("Candidate metadata cần đúng 200 records.")
    ids = [a.get("asset_id") for a in assets]
    if any(not isinstance(a, str) or not a or a != a.strip() for a in ids) or len(set(ids)) != 200:
        raise ValueError("Candidate IDs thiếu/trùng.")
    from app.schemas.text_search import TextSearchHit
    for aid in ids:
        TextSearchHit(asset_id=aid, score=0)
    metadata = dict(zip(ids, assets, strict=True))
    splits, groups, validation = {}, {"validation": set(), "test": set()}, []
    required = {"query_id", "query_type", "language", "split", "query_group_id", "query_text"}
    for row in _csv(contents["queries"], required):
        qid, split, group = row["query_id"], row["split"], row["query_group_id"]
        if (not qid or qid != qid.strip() or qid in splits or split not in groups
                or not group or row["query_type"] != "text" or row["language"] != "en"):
            raise ValueError("Query IDs/splits/groups/type/language không hợp lệ.")
        splits[qid] = split
        groups[split].add(group)
        if split == "validation":
            from app.schemas.text_search import LiveTextSearchRequest
            LiveTextSearchRequest(query=row["query_text"], filters={})
            validation.append((qid, row["query_text"], group))
        # Test text không đưa vào service, raw output, metrics hoặc selection.
    if (len(splits) != 70 or len(validation) != 28 or len(splits) - len(validation) != 42
            or groups["validation"] & groups["test"]):
        raise ValueError("Cần split 28/42 không giao query group.")
    pairs, judgments = set(), {qid: set() for qid in splits}
    relevant = {qid: [] for qid, _, _ in validation}
    for row in _csv(contents["qrels"], {"query_id", "asset_id", "relevance"}):
        qid, aid = row["query_id"], row["asset_id"]
        if qid not in splits or aid not in metadata or (qid, aid) in pairs:
            raise ValueError("Qrels chứa cặp ID trùng/không xác định.")
        pairs.add((qid, aid)); judgments[qid].add(aid)
        if qid in relevant:
            if row["relevance"] not in ("0", "1", "2"):
                raise ValueError("Validation relevance cần 0/1/2.")
            if int(row["relevance"]) >= 1:
                relevant[qid].append(aid)
    if any(len(rows) != 200 for rows in judgments.values()):
        raise ValueError("Qrels cần đủ 200 judgments/query.")
    if sum(not values for values in relevant.values()) != 7:
        raise ValueError("Protocol cần 7 validation query không positive, Recall denominator 21.")
    queries = tuple(ValidationQuery(qid, text, group, tuple(sorted(relevant[qid]))) for qid, text, group in validation)
    hashes = {**expected, "manifest": sha(contents["manifest"]), "config": sha(raw_config)}
    return ValidationInputs(queries, tuple(sorted(ids)), metadata, hashes, config,
                            {**files, "config": config_path}, raw_config)


def nearest_rank_summary(samples):
    if not samples or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) or v < 0 for v in samples):
        raise ValueError("Latency samples không hợp lệ.")
    ordered = sorted(samples)
    return {"method": "nearest-rank", "sample_count": len(ordered),
            "p50_ms": ordered[ceil(.50 * len(ordered)) - 1],
            "p95_ms": ordered[ceil(.95 * len(ordered)) - 1]}


def invoke(fusion, mode, query, rrf_config):
    if mode == "clip_only":
        return fusion.clip.search_text(query, {}, candidate_limit=200)
    if mode == "e5_only":
        return fusion.e5.search_text(query, {}, candidate_limit=200)
    if mode == "clip_e5_rrf":
        return fusion.search_text(query, {}, config=rrf_config)
    raise ValueError("Unknown validation mode.")


def _payload(result, mode, inputs, provenances, config):
    from app.search.experimental_text_search import SourceRanking, FusionSearchResult
    from app.search.rrf import CLIP_SOURCE, E5_SOURCE
    expected_type = FusionSearchResult if mode == "clip_e5_rrf" else SourceRanking
    if not isinstance(result, expected_type):
        raise ValueError("Service DTO không đúng contract.")
    payload = json.loads(encoded(asdict(result)))
    sources = [payload] if mode != "clip_e5_rrf" else payload["raw_rankings"]
    expected_sources = [CLIP_SOURCE if mode == "clip_only" else E5_SOURCE] if mode != "clip_e5_rrf" else [CLIP_SOURCE, E5_SOURCE]
    if len(sources) != len(expected_sources):
        raise ValueError("Source count không hợp lệ.")
    for source, expected_source in zip(sources, expected_sources, strict=True):
        if (source["source"] != expected_source or source["score_type"] != "cosine"
                or source["filters"] != {} or source["provenance"] != provenances[expected_source]):
            raise ValueError("Source filters/provenance thay đổi.")
        _check_hits(source["hits"], inputs.candidate_ids, cosine=True)
    if mode == "clip_e5_rrf":
        if (payload["score_type"] != "rrf" or payload["filters"] != {}
                or payload["sources"] != [provenances[s] for s in expected_sources]
                or payload["candidate_snapshot"] != provenances[E5_SOURCE]["dataset_snapshot"]
                or payload["source_manifest_sha256"] != inputs.hashes["candidate_metadata"]
                or payload["candidate_ids_sha256"] != sha(encoded(list(inputs.candidate_ids)))
                or payload["corpus_sha256"] != provenances[E5_SOURCE]["corpus_sha256"]
                or payload["recipe_version"] != provenances[E5_SOURCE]["recipe_version"]
                or payload["parameters"].get("rrf_config_version") != config.config_version
                or payload["parameters"].get("source_retrieval_window") != 200
                or any(payload["parameters"].get(k) != v for k, v in config.parameters().items())):
            raise ValueError("Fusion filters/provenance/parameters không hợp lệ.")
        for rank, hit in enumerate(payload["hits"], 1):
            hit["rank"] = rank
        _check_hits(payload["hits"], inputs.candidate_ids, cosine=False)
    return payload


def _check_hits(hits, candidate_ids, *, cosine):
    if (len(hits) != 200 or {h["asset_id"] for h in hits} != set(candidate_ids)
            or any(type(h["rank"]) is not int or h["rank"] != i for i, h in enumerate(hits, 1))
            or any(isinstance(h["score"], bool) or not isinstance(h["score"], (int, float))
                   or not isfinite(h["score"]) or (cosine and not -1 <= h["score"] <= 1) for h in hits)
            or hits != sorted(hits, key=lambda h: (-h["score"], h["asset_id"]))):
        raise ValueError("Cần đúng 200 IDs duy nhất/rank liên tục/score hữu hạn/thứ tự xác định.")


def _repeat_check(reference, actual):
    """Exact ranks/RRF/provenance; chỉ raw cosine được có roundoff đã công bố."""
    def without_cosines(payload):
        copy = json.loads(encoded(payload))
        sources = copy["raw_rankings"] if copy["score_type"] == "rrf" else [copy]
        scores = []
        for source in sources:
            for hit in source["hits"]:
                scores.append(hit.pop("score"))
        return copy, scores
    left, a = without_cosines(reference); right, b = without_cosines(actual)
    if left != right:
        raise ValueError("Repeat/source comparison thay đổi ranks/RRF/provenance.")
    delta = max((abs(x-y) for x, y in zip(a, b, strict=True)), default=0.0)
    if delta > COSINE_REPEAT_TOLERANCE:
        raise ValueError("Raw cosine repeat vượt tolerance diagnostic 1e-12.")
    return delta


def run_validation(inputs, factory, output: Path, *, rank_constant: int,
                   execution_kind="fixture", context=None, clock_ns=perf_counter_ns):
    """Factory quản lý load/audit/reopen ngoài timing; lỗi giữ partial outputs."""
    from app.search.rrf import CLIP_SOURCE, E5_SOURCE, RRFConfig
    if type(rank_constant) is not int or rank_constant not in PROTOCOL["allowed_rrf_constants"]:
        raise ValueError("Chọn k tường minh trong 10/20/60; không tự chọn best k.")
    if execution_kind not in ("fixture", "real_model_cache"):
        raise ValueError("execution_kind không hợp lệ.")
    config = RRFConfig(rank_constant, 200, 200, 200)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    context = context if context is not None else {}
    report = {"schema_version": "issue91-validation-run-v1", "status": "running",
        "execution_kind": execution_kind, "benchmark": execution_kind == "real_model_cache",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "protocol": PROTOCOL,
        "input_sha256": inputs.hashes, "input_confirmation": inputs.config["input_confirmation"],
        "rank_constant": rank_constant, "configuration_selected_by_validation": False,
        "search_implementation": "app.search.experimental_text_search",
        "metric_implementation": "evaluation.run_keyword_baseline.compute_metrics",
        "context": context, "configurations": {mode: {"status": "not_started", "completed_samples": 0} for mode in MODES},
        "errors": [], "skipped_queries": {},
        "raw_cosine_repeat_tolerance": COSINE_REPEAT_TOLERANCE}
    position = {"phase": "setup", "configuration": None, "query_id": None, "repetition": None}
    references, completed = {}, {mode: set() for mode in MODES}
    failure = None
    try:
        (output / "run-config.json").write_bytes(inputs.config_bytes)
        with ExitStack() as streams:
            raw = streams.enter_context((output / "raw-rankings.jsonl").open("xb"))
            latency = streams.enter_context((output / "latency-samples.jsonl").open("xb"))
            with factory(output) as fusion:
                snapshot = f"{PROTOCOL['snapshot']}-sha256:{inputs.hashes['candidate_metadata']}"
                provenances = {}
                for source in (fusion.clip, fusion.e5):
                    if (tuple(source.asset_ids) != inputs.candidate_ids or source.metadata != inputs.metadata
                            or source.snapshot != snapshot or source.source_hash != inputs.hashes["candidate_metadata"]):
                        raise ValueError("Service và benchmark khác candidate inputs.")
                    provenances[source.source] = json.loads(encoded(asdict(source.provenance(200))))
                if set(provenances) != {CLIP_SOURCE, E5_SOURCE}:
                    raise ValueError("Hai nguồn không đúng nhãn CLIP/E5.")
                report["source_provenance"] = provenances
                for mode in MODES:
                    references[mode] = {}
                    entry = report["configurations"][mode] = {
                        "status": "running", "completed_samples": 0, "warmup_query_ids": [],
                        "max_raw_cosine_repeat_delta": 0.0}
                    for i in range(5):
                        query = inputs.queries[i]
                        position = dict(phase="warmup", configuration=mode, query_id=query.query_id, repetition=i+1)
                        _payload(invoke(fusion, mode, query.text, config), mode, inputs, provenances, config)
                        entry["warmup_query_ids"].append(query.query_id)
                    metrics, timings = [], []
                    for query in inputs.queries:
                        for repeat in range(1, 11):
                            position = dict(phase="measurement", configuration=mode, query_id=query.query_id, repetition=repeat)
                            started = clock_ns()
                            result = invoke(fusion, mode, query.text, config)
                            elapsed = clock_ns() - started
                            if type(elapsed) is not int or elapsed < 0:
                                raise ValueError("Clock không monotonic hoặc không trả nanoseconds integer.")
                            position["phase"] = "validate_and_export"
                            payload = _payload(result, mode, inputs, provenances, config)
                            if repeat == 1:
                                references[mode][query.query_id] = payload
                                raw.write(encoded({"query_id": query.query_id, "query_text": query.text,
                                    "query_group_id": query.group_id, "split": "validation", "configuration": mode,
                                    "measured_repetition": 1, "input_sha256": inputs.hashes,
                                    "relevant_asset_ids": query.relevant_ids, "result": payload}))
                                metrics.append({"query_id": query.query_id, "relevant_asset_ids": query.relevant_ids,
                                    "retrieved_asset_ids": [h["asset_id"] for h in payload["hits"]]})
                            delta = _repeat_check(references[mode][query.query_id], payload)
                            entry["max_raw_cosine_repeat_delta"] = max(entry["max_raw_cosine_repeat_delta"], delta)
                            ms = elapsed / 1_000_000
                            latency.write(encoded({"configuration": mode, "query_id": query.query_id,
                                "repetition": repeat, "elapsed_ms": ms, "candidate_count": len(payload["hits"]),
                                "config_version": payload.get("config_version", payload.get("provenance", {}).get("config_version")),
                                "raw_result_sha256": sha(encoded(payload)), "max_raw_cosine_delta": delta}))
                            timings.append(ms); entry["completed_samples"] += 1
                        completed[mode].add(query.query_id)
                    position = dict(phase="metrics", configuration=mode, query_id=None, repetition=None)
                    entry.update(status="passed", metrics=compute_metrics(metrics, [5, 10]),
                                 latency=nearest_rank_summary(timings))
                position = dict(phase="cross_source_comparison", configuration=None, query_id=None, repetition=None)
                report["standalone_vs_fusion_max_raw_cosine_delta"] = {CLIP_SOURCE: 0.0, E5_SOURCE: 0.0}
                for query in inputs.queries:
                    position["query_id"] = query.query_id
                    fused = references["clip_e5_rrf"][query.query_id]
                    for mode, source in zip(MODES[:2], fused["raw_rankings"], strict=True):
                        delta = _repeat_check(references[mode][query.query_id], source)
                        report["standalone_vs_fusion_max_raw_cosine_delta"][source["source"]] = max(
                            report["standalone_vs_fusion_max_raw_cosine_delta"][source["source"]], delta)
                position = dict(phase="final_index_audit_and_reopen", configuration=None, query_id=None, repetition=None)
            position["phase"] = "input_integrity_after_run"
            after = {"queries.csv": sha(inputs.files["queries"].read_bytes()),
                "qrels.csv": sha(inputs.files["qrels"].read_bytes()),
                "candidate_metadata": sha(inputs.files["candidates"].read_bytes()),
                "manifest": sha(inputs.files["manifest"].read_bytes()), "config": sha(inputs.files["config"].read_bytes())}
            if after != inputs.hashes:
                raise ValueError("Input/config thay đổi trong lúc chạy.")
        report["status"] = "passed"
    except (Exception, KeyboardInterrupt) as error:
        failure = error
        report["status"] = "failed"
        report["errors"].append({**position, "error_type": type(error).__name__,
                                 "reason": getattr(error, "reason", "validation_run_failed")})
    finally:
        for entry in report["configurations"].values():
            if entry["status"] == "running":
                entry["status"] = "failed"
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["skipped_queries"] = {mode: [q.query_id for q in inputs.queries if q.query_id not in completed[mode]] for mode in MODES}
        report["files_sha256"] = {p.name: sha(p.read_bytes()) for p in output.iterdir() if p.is_file()}
        with (output / "run.json").open("xb") as stream:
            stream.write(encoded(report))
    if failure is not None:
        raise ValidationRunFailed("Validation failed; giữ partial outputs và xem run.json.") from failure
    return report
