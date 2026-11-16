import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const local = join(repo, 'data/processed/issue105');
const bundle = process.argv[2] ? resolve(process.argv[2]) : join(local, 'raw-review-1');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const requireCheck = (ok, message) => { if (!ok) throw new Error(message); };
const json = async path => JSON.parse(await readFile(path, 'utf8'));
const jsonl = async path => (await readFile(path, 'utf8')).trim().split(/\r?\n/).map(JSON.parse);
const close = (actual, expected, label) => requireCheck(Number.isFinite(actual) && Number.isFinite(expected) && Math.abs(actual - expected) <= 1e-12, label);
const sameSet = (a, b) => a.size === b.size && [...a].every(id => b.has(id));
function csv(text) {
  const rows = []; let row = [], field = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (quoted && text[i + 1] === '"') { field += '"'; i++; }
      else quoted = !quoted;
    } else if (c === ',' && !quoted) { row.push(field); field = ''; }
    else if (c === '\n' && !quoted) {
      row.push(field.replace(/\r$/, '')); field = '';
      if (row.some(value => value.length)) rows.push(row);
      row = [];
    } else field += c;
  }
  requireCheck(!quoted, 'Unclosed CSV quote');
  if (field.length || row.length) { row.push(field.replace(/\r$/, '')); rows.push(row); }
  const header = rows.shift(); header[0] = header[0].replace(/^\uFEFF/, '');
  return rows.map(values => { requireCheck(values.length === header.length, 'CSV column count'); return Object.fromEntries(header.map((key, i) => [key, values[i]])); });
}

try {
  const manifestBytes = await readFile(join(bundle, 'bundle-files-sha256.json'));
  const manifest = JSON.parse(manifestBytes);
  requireCheck(Object.keys(manifest).length === 46, 'Expected 46 hashed files');
  for (const [name, expected] of Object.entries(manifest)) {
    requireCheck(!/(^\/|^[A-Za-z]:|\\|(^|\/)\.\.(\/|$))/.test(name), 'Unsafe archive path');
    requireCheck(hash(await readFile(join(bundle, name))) === expected, 'File hash mismatch: ' + name);
  }
  const queries = csv(await readFile(join(bundle, 'inputs/data/benchmark/queries.csv'), 'utf8'));
  const validation = queries.filter(q => q.split === 'validation');
  requireCheck(queries.length === 70 && validation.length === 28 && queries.filter(q => q.split === 'test').length === 42, 'Query split');
  const queryMap = new Map(validation.map(q => [q.query_id, q]));
  requireCheck(queryMap.size === 28, 'Duplicate validation query');
  const candidates = new Set((await json(join(bundle, 'inputs/data/manifests/objaverse_200.json'))).map(a => a.asset_id));
  requireCheck(candidates.size === 200, 'Candidate count');
  const qrels = new Map(validation.map(q => [q.query_id, new Map()]));
  for (const row of csv(await readFile(join(bundle, 'inputs/data/benchmark/qrels.csv'), 'utf8'))) {
    if (!qrels.has(row.query_id)) continue;
    const labels = qrels.get(row.query_id);
    requireCheck(candidates.has(row.asset_id) && !labels.has(row.asset_id), 'Unknown/duplicate qrel');
    requireCheck(['0', '1', '2'].includes(row.relevance), 'Invalid relevance');
    labels.set(row.asset_id, Number(row.relevance));
  }
  const positives = new Map();
  for (const [id, labels] of qrels) {
    requireCheck(labels.size === 200, 'Qrel coverage: ' + id);
    positives.set(id, new Set([...labels].filter(([, score]) => score >= 1).map(([asset]) => asset)));
  }
  requireCheck([...positives.values()].filter(ids => ids.size).length === 21, 'Recall denominator');
  const evidence = await json(join(bundle, 'docs/evidence/issue91-e5-rrf-validation-20261114.json'));
  const modes = ['clip_only', 'e5_only', 'clip_e5_rrf'];
  const results = []; let totalRaw = 0, totalSamples = 0;
  for (const k of [10, 20, 60]) {
    const runRoot = join(bundle, 'runs', 'validation-20261114-k' + k + '-1');
    const run = await json(join(runRoot, 'run.json'));
    requireCheck(run.status === 'passed' && run.rank_constant === k && run.errors.length === 0, 'Run status');
    requireCheck(run.benchmark === true && run.execution_kind === 'real_model_cache' && run.configuration_selected_by_validation === false, 'Run kind/selection');
    const raw = await jsonl(join(runRoot, 'raw-rankings.jsonl'));
    const samples = await jsonl(join(runRoot, 'latency-samples.jsonl'));
    requireCheck(raw.length === 84 && samples.length === 840, 'Run record/sample counts');
    requireCheck(raw.every(r => modes.includes(r.configuration)) && samples.every(s => modes.includes(s.configuration)), 'Unknown configuration');
    const original = evidence.runs.find(r => r.rank_constant === k);
    requireCheck(hash(await readFile(join(runRoot, 'run.json'))) === original.run_sha256, 'Original run hash');
    totalRaw += raw.length; totalSamples += samples.length;
    for (const mode of modes) {
      requireCheck(run.skipped_queries[mode].length === 0, 'Skipped queries');
      const records = raw.filter(r => r.configuration === mode);
      const timings = samples.filter(s => s.configuration === mode);
      requireCheck(records.length === 28 && new Set(records.map(r => r.query_id)).size === 28 && timings.length === 280, 'Mode coverage');
      const sums = { 'recall@5': 0, 'recall@10': 0, 'hit@5': 0, 'hit@10': 0, 'ndcg@10': 0 };
      for (const record of records) {
        const query = queryMap.get(record.query_id);
        requireCheck(query && record.split === 'validation' && query.query_text === record.query_text && query.query_group_id === record.query_group_id && record.measured_repetition === 1, 'Query identity/split');
        const relevant = positives.get(record.query_id);
        requireCheck(record.relevant_asset_ids.length === relevant.size && sameSet(new Set(record.relevant_asset_ids), relevant), 'Raw qrels differ');
        const hits = record.result.hits;
        requireCheck(Object.keys(record.result.filters).length === 0 && hits.length === 200 && sameSet(new Set(hits.map(h => h.asset_id)), candidates), 'Candidate/filter coverage');
        requireCheck(hits.every((h, i) => h.rank === i + 1), 'Noncontinuous ranks');
        for (const cutoff of [5, 10]) {
          const top = hits.slice(0, cutoff);
          const found = top.filter(h => relevant.has(h.asset_id)).length;
          if (relevant.size) sums['recall@' + cutoff] += found / relevant.size;
          sums['hit@' + cutoff] += Number(found > 0);
          if (cutoff === 10) {
            const dcg = top.reduce((sum, h, i) => sum + (relevant.has(h.asset_id) ? 1 / Math.log2(i + 2) : 0), 0);
            const ideal = Array.from({ length: Math.min(10, relevant.size) }, (_, i) => 1 / Math.log2(i + 2)).reduce((a, b) => a + b, 0);
            sums['ndcg@10'] += ideal ? dcg / ideal : 0;
          }
        }
        const measured = timings.filter(s => s.query_id === record.query_id);
        requireCheck(measured.length === 10 && new Set(measured.map(s => s.repetition)).size === 10 && measured.every(s => Number.isInteger(s.repetition) && s.repetition >= 1 && s.repetition <= 10 && s.candidate_count === 200 && Number.isFinite(s.elapsed_ms) && s.elapsed_ms >= 0), 'Latency coverage');
      }
      const metrics = Object.fromEntries(Object.entries(sums).map(([name, sum]) => [name, sum / (name.startsWith('recall') ? 21 : 28)]));
      for (const [name, actual] of Object.entries(metrics)) {
        close(actual, run.configurations[mode].metrics[name].macro_average, 'Run metric ' + k + '/' + mode + '/' + name);
        close(actual, original.configurations[mode].metrics[name], 'Evidence metric ' + k + '/' + mode + '/' + name);
      }
      const elapsed = timings.map(s => s.elapsed_ms).sort((a, b) => a - b);
      const latency = { sample_count: 280, method: 'nearest-rank', p50_ms: elapsed[139], p95_ms: elapsed[265] };
      for (const name of ['p50_ms', 'p95_ms']) {
        close(latency[name], run.configurations[mode].latency[name], 'Run latency ' + name);
        close(latency[name], original.configurations[mode].latency[name], 'Evidence latency ' + name);
      }
      results.push({ k, configuration: mode, query_count: 28, recall_denominator: 21, metrics, latency });
    }
  }
  requireCheck(totalRaw === 252 && totalSamples === 2520 && results.length === 9, 'Totals');
  const output = {
    schema_version: 'issue105-archive-metrics-review-v1', status: 'passed', audited_at_utc: new Date().toISOString(),
    auditor_sha256: hash(await readFile(fileURLToPath(import.meta.url))), node_version: process.version,
    bundle_hash_table_sha256: hash(manifestBytes), hashed_files: 46, raw_records: totalRaw, measured_samples: totalSamples,
    metrics_source: 'archived validation qrels and raw rankings', benchmark_executed: false, results,
    limitations: ['No weights/retrieval, full Fraction RRF, unexported repeat DTO or live persisted-index audit.', 'Numeric metric comparisons use absolute tolerance 1e-12; raw file hashes remain exact.', 'Reading split metadata is structural verification; no test rankings or test quality metric was computed.']
  };
  const outputPath = process.argv[3] ? resolve(process.argv[3]) : join(local, 'metrics-review-2.json');
  await writeFile(outputPath, JSON.stringify(output, null, 2) + '\n', { encoding: 'utf8', flag: 'wx' });
  console.table(results.map(r => ({ k: r.k, mode: r.configuration, recall10: r.metrics['recall@10'].toFixed(5), ndcg10: r.metrics['ndcg@10'].toFixed(5), p50_ms: r.latency.p50_ms, p95_ms: r.latency.p95_ms })));
  console.log('PASSED: 9/9 combinations; 252 raw records; 2520 samples; metrics and latency match');
  console.log('Evidence: ' + outputPath);
} catch (error) { console.error('FAILED: ' + error.message); process.exitCode = 1; }
