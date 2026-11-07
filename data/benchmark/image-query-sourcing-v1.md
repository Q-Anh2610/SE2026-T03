# W4 image-query source audit v1

Status: **Owner-approved query set: 20 `similarity`, 0 `same_id`; independent relevance labeling and split remain pending**.

## Snapshot and counts

- Candidate snapshot: `home-interior-clear-200-v3` (200 assets; manifest SHA-256 `9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd`).
- Existing `data/benchmark/queries.csv` remains the locked 70-row text benchmark and is not modified.
- Approved image queries: `same_id = 0`, `similarity = 20`, confirmed by dataset owner Trịnh Thị Thu Huyền and retrieval owner Lê Thị Linh Chi in Issue #89. Chi's earlier approval of the 200-asset candidate snapshot did not by itself approve this ratio; her later confirmation did.
- Similarity source candidates: 20 retrieved, hash recorded, and visually reviewed; both owners approved this set for query use. Details and attribution/license links are in `image_query_sources_v1.csv`.
- The 20 queries span the snapshot's curated groups, including chair, sofa, desk, bed, table lamp, cabinet, shelving, sink, bathtub, toilet, washing machine, refrigerator, floor lamp, fan, cooker, microwave, shower, vacuum cleaner, coffee machine, and table. The cabinet photo is low-light but identifiable. The coffee-table photo includes a sculpture and room context; the query note explicitly targets the table. These are relevance-labeling caveats, not automatic relevance judgments.
- The bed attribution preserves both roles: Commons lists Shixart1985 as author/uploader under CC BY 2.0, while embedded source/credit metadata names Nenad Stojković. The shower record identifies DO'Neil as photographer and Mlepicki as uploader; the inventory selects CC BY-SA 3.0 from the licenses offered on the Commons file page.
- Valid alternate-view images found in the repository for `same_id`: 0 of 200 assets have more than one thumbnail image set in the annotations. Resized URLs for the same thumbnail do not qualify as alternate views. No source model has yet been rendered from another view in this work.

## Reason for the `same_id` shortfall

The checkout contains source metadata and one verified indexed preview per candidate. Annotation metadata points to a single thumbnail set per asset. Thus there are currently no independently sourced alternate renders for `same_id`; using a resized or indexed preview would violate the labeling protocol. We have not rendered the source 3D models from alternate viewpoints in this audit, so the verified repository count is 0 and the external/rendered count remains unverified.

## Decisions and remaining work

1. The owners approved 20 `similarity` queries and 0 `same_id` queries in Issue #89. This is within the documented 20–40 image-query range. The `same_id` shortfall is the verified repository audit count of zero alternate views; no resized thumbnail or indexed preview was repurposed.
2. `image_queries_v1.csv` records the approved query sources separately from the locked text `queries.csv`. Its `split` cells are intentionally blank until independent labeling and adjudication are complete; this file is an approved query-set draft, not a locked benchmark.
3. Remaining: prepare candidate pairs/qrels; obtain independent labels; adjudicate disagreements; then split by `query_group_id` and lock the image manifest. Retrieval owner must verify each model index matches the exact 200 candidate IDs/checksums before benchmark execution. Do not infer relevance from the source-to-category mapping.

No relevance labels, qrels, splits, or index results are included in this query-set draft. The 20 downloaded source images remain local and are excluded from Git by `.gitignore`; the inventory records relative paths and SHA-256 hashes for reproducibility.
