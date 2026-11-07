param(
    [string]$QueryPath = "data/benchmark/image_queries_v1.csv",
    [string]$CandidateAssetsPath = "data/benchmark/candidate_assets.csv",
    [string]$SnapshotPath = "data/manifests/objaverse_200.json",
    [string]$OutputPath = "data/benchmark/image_candidate_pairs_v1.csv",
    [string]$QrelsTemplatePath = "data/benchmark/image_qrels_v1.template.csv"
)

$ErrorActionPreference = "Stop"
$queries = @(Import-Csv -LiteralPath $QueryPath)
$candidates = @(Import-Csv -LiteralPath $CandidateAssetsPath)
$snapshot = @(Get-Content -LiteralPath $SnapshotPath -Raw -Encoding utf8 | ConvertFrom-Json)
$snapshotHash = (Get-FileHash -LiteralPath $SnapshotPath -Algorithm SHA256).Hash.ToLowerInvariant()
$expectedHash = "9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd"

if ($snapshotHash -ne $expectedHash) { throw "Snapshot manifest hash changed: $snapshotHash" }
if ($candidates.Count -ne 200 -or $snapshot.Count -ne 200) { throw "Expected exactly 200 snapshot candidates." }
if ($queries.Count -ne 20 -or @($queries | Where-Object { $_.query_type -ne "similarity" }).Count -ne 0) {
    throw "Expected the approved 20-query similarity set."
}
if (@($candidates.asset_id | Sort-Object -Unique).Count -ne 200 -or @($snapshot.asset_id | Sort-Object -Unique).Count -ne 200) {
    throw "Candidate or snapshot asset IDs are not unique."
}
$candidateIds = @($candidates.asset_id | Sort-Object)
$snapshotIds = @($snapshot.asset_id | Sort-Object)
if (Compare-Object $candidateIds $snapshotIds) { throw "candidate_assets.csv does not match the 200-asset snapshot IDs." }

$pairs = foreach ($query in $queries) {
    foreach ($candidate in $candidates) {
        [PSCustomObject]@{
            query_id = $query.query_id
            query_group_id = $query.query_group_id
            asset_id = $candidate.asset_id
            asset_name = $candidate.name
            preview_sha256 = $candidate.preview_sha256
        }
    }
}
if (@($pairs).Count -ne 4000) { throw "Expected 4,000 query/candidate pairs." }
$pairs | Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Encoding utf8
$qrelsHeader = "query_id,asset_id,relevance,adjudication_status,adjudication_note,adjudicated_by,adjudicated_at_utc"
Set-Content -LiteralPath $QrelsTemplatePath -Value $qrelsHeader -Encoding utf8
Write-Output "Created $OutputPath ($(@($pairs).Count) pairs)"
Write-Output "Created empty qrels template $QrelsTemplatePath; no relevance labels were created."
