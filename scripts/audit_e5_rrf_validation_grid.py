"""Read-only audit of the three real #91 validation packages; no models."""

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'backend')]
from evaluation import e5_rrf_validation as runner
from app.search.rrf import CLIP_SOURCE, E5_SOURCE, RRFConfig
from scripts.verify_issue91_query_artifact import verify_tree


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def audit_grid(repo):
    inputs = runner.load_inputs(repo / 'evaluation/configs/issue91-e5-rrf-validation.confirmed.json', repo)
    invariant = verify_tree(repo, compare_source_commit=True)
    require(invariant['status'] == 'passed', 'artifact checker')
    evidence = {'schema_version': 'issue91-real-validation-grid-audit-v1',
        'audited_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'passed', 'benchmark_executed_by_auditor': False,
        'auditor_sha256': digest(Path(__file__)), 'input_sha256': inputs.hashes,
        'artifact_provenance': inputs.config['artifact_provenance'],
        'artifact_verification': invariant, 'runs': [],
        'configuration_selection': {'status': 'pending_owner_review', 'selected_k': None,
            'reason': 'No primary selection metric was declared before this grid; report the trade-off for owner review.'},
        'limitations': [
            '28 English validation queries, 200 curated candidates, 7 no-positive queries; no test or Vietnamese quality evaluation.',
            'Sequential CPU runs on one machine; no confidence interval or production/HTTP latency claim.',
            'Every repeat is checked by the runner; auditor binds first-repeat raw hashes and validates all timing samples/diagnostics, not unexported repeat DTOs.',
            'Old f627 baseline provenance remains unresolved; all controls below are fresh CLIP/E5 runs.',
        ]}
    raw_by_k, common = {}, None
    for k in (10, 20, 60):
        root = repo / f'data/processed/issue91/validation-20261114-k{k}-1'
        report = json.loads((root / 'run.json').read_bytes())
        require(report['status'] == 'passed' and report['benchmark'] is True
                and report['execution_kind'] == 'real_model_cache' and report['rank_constant'] == k, f'run status k{k}')
        require(report['protocol'] == runner.PROTOCOL and report['input_sha256'] == inputs.hashes, f'protocol/inputs k{k}')
        require(not report['errors'] and report['skipped_queries'] == {mode: [] for mode in runner.MODES}, f'errors/skips k{k}')
        require(report['artifact_provenance'] == inputs.config['artifact_provenance'], f'artifact provenance k{k}')
        require(report['configuration_selected_by_validation'] is False, f'unexpected selection k{k}')
        files = report['files_sha256']
        require(set(files) == {'clip-index-manifest.json', 'e5-index-manifest.json', 'latency-samples.jsonl',
                'query-artifact-erratum.json', 'raw-rankings.jsonl', 'run-config.json'}, f'package files k{k}')
        for name, expected in files.items():
            require(digest(root / name) == expected, f'file hash k{k}: {name}')
        require((root / 'run-config.json').read_bytes() == inputs.config_bytes, f'config copy k{k}')
        require(files['query-artifact-erratum.json'] == inputs.hashes['artifact_record'], f'erratum copy k{k}')
        context = report['context']
        require(context['persisted_fingerprints_unchanged'] is True
                and context['persisted_before'] == context['persisted_after_reopen'], f'persisted index k{k}')
        for name, expected in context['module_sha256'].items():
            require(digest(repo / name) == expected, f'current module differs from measured code: {name}')
        stable = {name: context[name] for name in ('device', 'machine', 'processor', 'python', 'platform',
            'torch_threads', 'torch_interop_threads', 'package_versions', 'code_commit', 'working_tree_dirty',
            'module_sha256', 'persisted_before')}
        stable['source_provenance'] = report['source_provenance']
        if common is None:
            common = stable
        require(stable == common, f'environment/source/code drift k{k}')
        for source, filename in ((CLIP_SOURCE, 'clip-index-manifest.json'), (E5_SOURCE, 'e5-index-manifest.json')):
            provenance = report['source_provenance'][source]
            require(provenance['index_manifest_sha256'] == files[filename]
                    and provenance['source_manifest_sha256'] == inputs.hashes['candidate_metadata']
                    and provenance['candidate_limit'] == 200, f'source manifest k{k}')
        raw, samples = jsonl(root / 'raw-rankings.jsonl'), jsonl(root / 'latency-samples.jsonl')
        require(len(raw) == 84 and len(samples) == 840, f'raw/timing count k{k}')
        expected_order = [(mode, q.query_id) for mode in runner.MODES for q in inputs.queries]
        require([(r['configuration'], r['query_id']) for r in raw] == expected_order, f'raw order/IDs k{k}')
        require([(r['configuration'], r['query_id'], r['repetition']) for r in samples] ==
                [(mode, q.query_id, repeat) for mode in runner.MODES for q in inputs.queries for repeat in range(1,11)], f'sample order k{k}')
        raw_by_k[k] = by_mode = {mode: {} for mode in runner.MODES}
        configurations = {}
        for mode in runner.MODES:
            metric_records = []
            for q, row in zip(inputs.queries, [r for r in raw if r['configuration'] == mode], strict=True):
                require(row['split'] == 'validation' and row['query_text'] == q.text and row['query_group_id'] == q.group_id
                        and row['relevant_asset_ids'] == list(q.relevant_ids) and row['input_sha256'] == inputs.hashes
                        and row['measured_repetition'] == 1, f'query/qrels/raw provenance k{k}/{mode}/{q.query_id}')
                payload = row['result']
                require(payload['filters'] == {}, f'filters k{k}/{mode}')
                runner._check_hits(payload['hits'], inputs.candidate_ids, cosine=mode != 'clip_e5_rrf')
                if mode == 'clip_e5_rrf':
                    sources = payload['raw_rankings']
                    require([s['source'] for s in sources] == [CLIP_SOURCE, E5_SOURCE], f'RRF sources k{k}')
                    for source in sources:
                        runner._check_hits(source['hits'], inputs.candidate_ids, cosine=True)
                        require(source['filters'] == {} and source['score_type'] == 'cosine'
                                and source['provenance'] == report['source_provenance'][source['source']], f'raw source provenance k{k}')
                    require(payload['score_type'] == 'rrf' and payload['sources'] ==
                            [report['source_provenance'][s] for s in (CLIP_SOURCE, E5_SOURCE)], f'fusion DTO k{k}')
                    parameters = RRFConfig(k, 200, 200, 200)
                    require(all(payload['parameters'][key] == value for key, value in parameters.parameters().items())
                            and payload['parameters']['source_retrieval_window'] == 200
                            and payload['parameters']['rrf_config_version'] == parameters.config_version, f'RRF parameters k{k}')
                    ranks = [{h['asset_id']: h['rank'] for h in source['hits']} for source in sources]
                    exact = {aid: sum((Fraction(1, k + ranks[i][aid]) for i in (0,1)), Fraction()) for aid in inputs.candidate_ids}
                    ordered = sorted(exact, key=lambda aid: (-exact[aid], aid))
                    expected_hits = [{'asset_id': aid, 'rank': rank, 'score': float(exact[aid]),
                        'contributions': [{'source': source, 'rank': ranks[i][aid], 'contribution': float(Fraction(1,k+ranks[i][aid]))}
                                          for i, source in enumerate((CLIP_SOURCE, E5_SOURCE))]}
                                     for rank, aid in enumerate(ordered,1)]
                    require(payload['hits'] == expected_hits, f'independent Fraction RRF k{k}/{q.query_id}')
                else:
                    source = CLIP_SOURCE if mode == 'clip_only' else E5_SOURCE
                    require(payload['source'] == source and payload['score_type'] == 'cosine'
                            and payload['provenance'] == report['source_provenance'][source], f'standalone source k{k}/{mode}')
                by_mode[mode][q.query_id] = payload
                first = next(s for s in samples if s['configuration'] == mode and s['query_id'] == q.query_id and s['repetition'] == 1)
                require(first['raw_result_sha256'] == runner.sha(runner.encoded(payload)), f'first-repeat binding k{k}')
                metric_records.append({'query_id': q.query_id, 'relevant_asset_ids': q.relevant_ids,
                                       'retrieved_asset_ids': [h['asset_id'] for h in payload['hits']]})
            metrics = runner.compute_metrics(metric_records, [5,10])
            entry = report['configurations'][mode]
            require(metrics == entry['metrics'], f'recomputed metrics k{k}/{mode}')
            timings = [s for s in samples if s['configuration'] == mode]
            require(all(s['candidate_count'] == 200 and 0 <= s['max_raw_cosine_delta'] <= 1e-12 for s in timings), f'sample diagnostics k{k}')
            latency = runner.nearest_rank_summary([s['elapsed_ms'] for s in timings])
            require(latency == entry['latency'] and entry['completed_samples'] == 280 and entry['status'] == 'passed', f'latency/count/status k{k}/{mode}')
            require(entry['warmup_query_ids'] == [q.query_id for q in inputs.queries[:5]], f'warmup k{k}/{mode}')
            require(entry['max_raw_cosine_repeat_delta'] == max(s['max_raw_cosine_delta'] for s in timings), f'repeat diagnostic k{k}/{mode}')
            configurations[mode] = {'metrics': {name: value['macro_average'] for name, value in metrics.items()},
                'latency': latency, 'completed_samples': 280, 'max_raw_cosine_repeat_delta': entry['max_raw_cosine_repeat_delta'],
                'no_positive_query_count': 7, 'recall_denominator': 21, 'hit_ndcg_denominator': 28}
        cross = {CLIP_SOURCE: 0.0, E5_SOURCE: 0.0}
        for q in inputs.queries:
            for mode, source in zip(runner.MODES[:2], by_mode['clip_e5_rrf'][q.query_id]['raw_rankings'], strict=True):
                cross[source['source']] = max(cross[source['source']], runner._repeat_check(by_mode[mode][q.query_id], source))
        require(cross == report['standalone_vs_fusion_max_raw_cosine_delta'], f'cross-source diagnostics k{k}')
        evidence['runs'].append({'rank_constant': k, 'output': root.relative_to(repo).as_posix(),
            'run_sha256': digest(root / 'run.json'), 'files_sha256': files,
            'started_at_utc': report['started_at_utc'], 'finished_at_utc': report['finished_at_utc'],
            'command': context['command'], 'model_load_seconds': context['model_load_seconds'],
            'raw_record_count': len(raw), 'measured_sample_count': len(samples),
            'configurations': configurations, 'persisted_after_reopen': context['persisted_after_reopen'],
            'standalone_vs_fusion_max_raw_cosine_delta': cross, 'errors': [], 'skipped_queries': report['skipped_queries']})
    evidence['common_runtime_and_sources'] = common
    evidence['across_grid_source_max_raw_cosine_delta'] = {mode: max(
        runner._repeat_check(raw_by_k[10][mode][q.query_id], raw_by_k[k][mode][q.query_id])
        for k in (20,60) for q in inputs.queries) for mode in runner.MODES[:2]}
    evidence['totals'] = {'raw_records': 252, 'measured_samples': 2520, 'warmup_calls': 45, 'service_calls': 2565}
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence = audit_grid(args.repo.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write((json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))
    print(json.dumps({'status': evidence['status'], 'totals': evidence['totals'],
                      'output': str(args.output), 'across_grid_source_max_raw_cosine_delta': evidence['across_grid_source_max_raw_cosine_delta']}))
