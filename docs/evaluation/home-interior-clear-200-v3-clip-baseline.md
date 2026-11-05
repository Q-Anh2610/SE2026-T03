# CLIP text retrieval baseline: home-interior-clear-200-v3

Issue #71 evaluation of Chi's ranked CLIP results against the locked 70-query
benchmark and its adjudicated qrels. This report compares CLIP with the existing
keyword diagnostic; it does not select or tune a retrieval configuration.

## Validation

- Confirmed all 70 locked query IDs occur exactly once in the benchmark and each
  has exactly 10 ranked results (700 rows total).
- Confirmed ranks are 1–10 for every query, with no repeated asset in a query's
  top 10. Scores are descending; score ties follow asset ID ascending.
- Confirmed all returned asset IDs belong to the 200-asset candidate snapshot.
- Confirmed query split and result provenance agree: 28 validation and 42 test
  queries. Chi reported no incomplete queries, failed embeddings, or skipped
  assets; the bundle records 200 indexed assets.
- Confirmed the query, qrels, source manifest, candidate asset CSV, preview
  provenance, ranked-results CSV and index-manifest checksums against the local
  locked inputs and handoff.
- Resolved the two checksum differences with Chi's Issue #71 comment. The
  benchmark manifest checksum in the handoff is over CRLF bytes; normalizing the
  local Git-blob LF file to CRLF reproduces `2c2dcf…`. The `7d0a3e…` ready
  checksum identifies the source `home-interior-354-v1` handoff; `85aefb…`
  identifies the selected 200-asset `objaverse_200.ready.json` used by the index.
  They refer to different stages of the same data path.

No query, qrel, split, filter, or retrieval configuration was changed for this
evaluation.

## Metrics

Relevance is binary: qrels with relevance ≥ 1 count as relevant. Recall is the
macro average over queries with at least one positive qrel; 7 validation and 4
test queries have no positive qrels and are excluded from Recall's denominator.
Hit@K and binary nDCG@10 include every query, assigning zero to queries with no
positive qrels. nDCG uses the original ranking order and a binary gain.

| Split | Queries | Metric | CLIP | Keyword | Difference |
|---|---:|---|---:|---:|---:|
| Validation | 28 | Recall@5 | 0.329473 | 0.124704 | +20.48 pp |
| Validation | 28 | Hit@5 | 0.678571 | 0.535714 | +14.29 pp |
| Validation | 28 | Recall@10 | 0.492996 | 0.172658 | +32.03 pp |
| Validation | 28 | Hit@10 | 0.750000 | 0.642857 | +10.71 pp |
| Validation | 28 | nDCG@10 | 0.469824 | 0.188325 | +28.15 pp |
| Test | 42 | Recall@5 | 0.394618 | 0.138764 | +25.59 pp |
| Test | 42 | Hit@5 | 0.857143 | 0.642857 | +21.43 pp |
| Test | 42 | Recall@10 | 0.581198 | 0.231332 | +34.99 pp |
| Test | 42 | Hit@10 | 0.857143 | 0.738095 | +11.90 pp |
| Test | 42 | nDCG@10 | 0.672967 | 0.276618 | +39.63 pp |

The deltas are CLIP minus keyword in percentage points. On these locked splits,
CLIP is higher than the keyword diagnostic on every reported metric. The test
numbers are descriptive results for this benchmark; no acceptance threshold was
specified, and they were not used to change retrieval settings.

## Run provenance

- Snapshot: `home-interior-clear-200-v3`
- Snapshot source manifest SHA-256: `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`
- Locked `queries.csv` SHA-256: `f62762c4a0b392ddc310d1d64e0bdb685b2010347e3790395bbb523428c38788`
- Locked `qrels.csv` SHA-256: `cc1d42f6e3f41f92fab1b842c7a70ca68be4341cdd30e4262e13989f99019df5`
- Model: `openai/clip-vit-base-patch32`, revision `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`
- Index: `issue71-home-interior-clear-200-v3-clip-v1`; 200 points
- Retrieval config: `clip-text-exact-all-filtered-v1-k10`; exact search, top 10,
  no metadata filters, score descending then asset ID ascending
- Run time in Chi's provenance: `2026-11-04T09:00:05Z`–`2026-11-04T09:00:31Z`
- Chi's run environment: Windows 11, Python 3.13.7, CPU, PyTorch 2.8.0+cpu,
  Transformers 4.57.1, Qdrant client 1.15.1
- Metric calculation environment: Windows 11, Python 3.13.15

## Metric tests

Ran the evaluation test suite after adding a known-answer test for the
`compute_metrics` function used by this run. The added case checks Recall's
denominator and the zero score behavior for Hit/nDCG when a query has no
positive qrels.

```powershell
backend\.venv\Scripts\python.exe -m pytest -c evaluation/pytest.ini evaluation/tests
```

Result: **15 passed** with Python 3.13.15 and pytest 9.1.1 (0.45 s). This
validates metric implementation behavior on deterministic fixtures; it does not
assert a quality threshold for the CLIP baseline.

The result file [home-interior-clear-200-v3-clip-baseline.json](../../evaluation/results/home-interior-clear-200-v3-clip-baseline.json)
contains the 700 ranked rows, per-query metrics, input checksums, provenance,
and the keyword comparison. Reproduce the validation and metric calculation
after extracting Chi's ZIP into the repository root as `issue71/`:

```powershell
backend\.venv\Scripts\python.exe evaluation/run_issue71_clip.py
```
