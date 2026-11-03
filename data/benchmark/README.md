# Benchmark labeling work files

`queries.csv` contains 70 English text queries for Issue #46. Khuê and Huyền independently labeled all 200 candidates for all 70 queries (14,000 pairs per annotator). `labels_khue.csv` and `labels_huyen.csv` preserve their separate judgments. Their scores agree on 13,402 pairs; all 598 disagreements were adjudicated in `qrels.csv`. The benchmark is locked as `home-interior-text-v2`; see `manifest.yaml` for split details and SHA-256 hashes. Retrieval results for the locked snapshot are still pending from Chi.

The candidate set is `candidate_assets.csv`, derived from the 200 asset IDs in `data/manifests/objaverse_200.json`. Its `preview_sha256` column identifies each verified source preview (`<sha256>.jpg`) under `objaverse/previews/`. The local `home-interior-clear-200-v3` images are not included in Git. The ordered copies are under `objaverse/previews_by_candidate_order/` and use `0001_<asset_id>.jpg` through `0200_<asset_id>.jpg`, following CSV row order. Both labeler pages accept these names as well as the hash filenames. Do not substitute mutable source URLs for the verified images.

## Local labeler

Open `annotator.html` in a browser and load:

1. `queries.csv`;
2. `candidate_assets.csv`;
3. the folder containing the 200 verified JPEG previews;
4. choose your annotator name.

The labeler uses keys `0`, `1`, and `2` to select a score, then `Enter` to save and advance. Left/right arrows navigate without saving. `Skip without label` leaves the pair unjudged; it does not imply relevance 0. Download labels regularly; timestamps are written in UTC.

Metadata suggestions are enabled by default and use lexical overlap between query text and the asset title. They do not analyze the preview and can be wrong. Check every preview and edit the score/evidence note as needed. Assisted output is named `labels_khue_assisted.csv` or `labels_huyen_assisted.csv` and the evidence note records whether the suggestion was accepted or edited. These assisted files must not be presented as fully independent labels under the current benchmark protocol. Turn suggestions off for a blind independent pass; that exports `labels_khue.csv` or `labels_huyen.csv`.

Khuê and Huyền must use separate output files and must not compare judgments until both passes are complete. Keep original files unchanged; merge differences later into `qrels.csv` through adjudication. For protocol-compliant independent labels, turn suggestions off for both annotators; assisted labels are useful as a separate exploratory artifact but are not independent ground truth.

Do not represent draft queries or empty templates as completed labels. The W2 keyword diagnostic is not the requested text-retrieval baseline. Final retrieval evaluation depends on ranked results and provenance from Chi for the matching snapshot; the W3 HTTP text-search API is outside this issue's scope.

## Local adjudication

Open `adjudicator.html` in Chrome or Edge. Load `labels_khue.csv`, `labels_huyen.csv`, `queries.csv`, `candidate_assets.csv`, and the verified preview folder. Click **Mở qrels.csv để cập nhật** and select this directory's `qrels.csv`; grant write access when prompted. The file contains all 14,000 final pair judgments with status `Adjudicated`.

The interface shows only disagreements that remain unresolved in qrels. If a future benchmark has disagreements, select the jointly agreed score, enter a short adjudication reason, then press Enter. Each decision is written directly to the selected qrels file with `adjudication_status=Adjudicated`, `adjudicated_by=Khue, Huyen`, and a UTC timestamp. Use one adjudicator window at a time; the page detects external changes before writing to avoid overwriting another session. If direct file access is unavailable, use a current desktop Chrome or Edge browser.

For matching scores, the qrels note is derived from the score: `Directly relevant`, `Partly relevant`, or `Not relevant`. Do not change the two source label files while adjudicating. The current benchmark is locked; changes to query text, qrels, or split require a new benchmark version.
