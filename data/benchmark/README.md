# Benchmark labeling work files

`queries.csv` contains 70 English text queries for Issue #46, reviewed by Khuê on 2026-11-01. Independent labels have not started. The split is recorded in the draft manifest and must remain fixed; benchmark locking is still pending adjudicated qrels and the pre-evaluation freeze.

The candidate set is `candidate_assets.csv`, derived from the 200 asset IDs in `data/manifests/objaverse_200.json`. Its `preview_sha256` column identifies the verified preview filename (`<sha256>.jpg`). The local `home-interior-clear-200-v3` preview package is not included in Git. Restore the verified package before visual annotation; do not substitute mutable source URLs for the verified images.

## Local labeler

Open `annotator.html` in a browser and load:

1. `queries.csv`;
2. `candidate_assets.csv`;
3. the folder containing the 200 verified JPEG previews;
4. choose your annotator name.

The labeler uses keys `0`, `1`, and `2` to select a score, then `Enter` to save and advance. Left/right arrows navigate without saving. `Skip without label` leaves the pair unjudged; it does not imply relevance 0. Download labels regularly; timestamps are written in UTC.

Metadata suggestions are enabled by default and use lexical overlap between query text and the asset title. They do not analyze the preview and can be wrong. Check every preview and edit the score/evidence note as needed. Assisted output is named `labels_khue_assisted.csv` or `labels_huyen_assisted.csv` and the evidence note records whether the suggestion was accepted or edited. These assisted files must not be presented as fully independent labels under the current benchmark protocol. Turn suggestions off for a blind independent pass; that exports `labels_khue.csv` or `labels_huyen.csv`.

Khuê and Huyền must use separate output files and must not compare judgments until both passes are complete. Keep original files unchanged; merge differences later into `qrels.csv` through adjudication. For protocol-compliant independent labels, turn suggestions off for both annotators; assisted labels are useful as a separate exploratory artifact but are not independent ground truth.

The CSV templates are header-only until actual judgments exist. Do not represent draft queries or empty templates as completed labels. The baseline run is a separate step and depends on Chi's product search results for the matching snapshot.
