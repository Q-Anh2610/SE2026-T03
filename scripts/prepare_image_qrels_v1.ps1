param(
    [string]$CandidatePairsPath = "data/benchmark/image_candidate_pairs_v1.csv",
    [string]$KhueLabelsPath = "data/benchmark/labels_image_v1_khue.csv",
    [string]$HuyenLabelsPath = "data/benchmark/labels_image_v1_huyen.csv",
    [string]$OutputPath = "data/benchmark/image_qrels_v1.work.csv"
)

$ErrorActionPreference = "Stop"
$pairs = @(Import-Csv -LiteralPath $CandidatePairsPath)
$khueRows = @(Import-Csv -LiteralPath $KhueLabelsPath)
$huyenRows = @(Import-Csv -LiteralPath $HuyenLabelsPath)
$validScores = @("0", "1", "2")
if ($pairs.Count -ne 4000 -or $khueRows.Count -ne 4000 -or $huyenRows.Count -ne 4000) {
    throw "Expected 4,000 candidate pairs and 4,000 complete labels from each annotator."
}

function ConvertTo-LabelMap($rows, $expectedAnnotator) {
    $map = @{}
    foreach ($row in $rows) {
        $key = "$($row.query_id)`t$($row.asset_id)"
        if ($row.annotator -ne $expectedAnnotator -or $row.relevance -notin $validScores -or $map.ContainsKey($key)) {
            throw "Invalid, duplicate, or misattributed label for $key in $expectedAnnotator's file."
        }
        if ([string]::IsNullOrWhiteSpace($row.evidence_note) -or [string]::IsNullOrWhiteSpace($row.annotated_at_utc)) {
            throw "Missing evidence note or UTC timestamp for $key in $expectedAnnotator's file."
        }
        $map[$key] = $row
    }
    return $map
}

$khue = ConvertTo-LabelMap $khueRows "Doan Thi Minh Khue"
$huyen = ConvertTo-LabelMap $huyenRows "Trinh Thi Thu Huyen"
$result = [System.Collections.Generic.List[object]]::new()
foreach ($pair in $pairs) {
    $key = "$($pair.query_id)`t$($pair.asset_id)"
    if (-not $khue.ContainsKey($key) -or -not $huyen.ContainsKey($key)) { throw "Missing independent label for $key." }
    $same = $khue[$key].relevance -eq $huyen[$key].relevance
    $score = if ($same) { $khue[$key].relevance } else { "" }
    $status = if ($same) { "Agreed" } else { "" }
    $note = if ($same) { @{ "0" = "Not relevant"; "1" = "Partly relevant"; "2" = "Directly relevant" }[$score] } else { "" }
    $result.Add([PSCustomObject]@{
        query_id = $pair.query_id
        asset_id = $pair.asset_id
        relevance = $score
        adjudication_status = $status
        adjudication_note = $note
        adjudicated_by = ""
        adjudicated_at_utc = ""
    })
}
$result | Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Encoding utf8
$pending = @($result | Where-Object { -not $_.adjudication_status }).Count
Write-Output "Created qrels work file with $($result.Count) pairs; $pending disagreements remain for joint adjudication."
