param(
    [string]$CandidateAssetsPath = "data/benchmark/candidate_assets.csv",
    [string]$SnapshotPath = "data/manifests/objaverse_200.json",
    [string]$OutputDirectory = "data/benchmark/objaverse/previews"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$candidateCsv = [System.IO.Path]::GetFullPath($CandidateAssetsPath)
$snapshotJson = [System.IO.Path]::GetFullPath($SnapshotPath)
$outputPath = [System.IO.Path]::GetFullPath($OutputDirectory)
$workspace = (Get-Location).Path.TrimEnd("\", "/")
if (-not $candidateCsv.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Candidate CSV must be inside the repository." }
if (-not $snapshotJson.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Snapshot manifest must be inside the repository." }
if (-not $outputPath.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Output directory must be inside the repository." }

$expectedSnapshotHash = "9dcc0afdab56adfd670ef1ecb0bc6e2a968a76eeb978be1ec0f32ff5fc7a9ffd"
$actualSnapshotHash = (Get-FileHash -LiteralPath $snapshotJson -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSnapshotHash -ne $expectedSnapshotHash) { throw "Unexpected snapshot manifest hash: $actualSnapshotHash" }
$snapshot = @(Get-Content -LiteralPath $snapshotJson -Raw -Encoding utf8 | ConvertFrom-Json)
$candidates = @(Import-Csv -LiteralPath $candidateCsv)
if ($snapshot.Count -ne 200 -or $candidates.Count -ne 200) { throw "Expected exactly 200 snapshot assets and candidate rows." }
if (Compare-Object @($snapshot.asset_id | Sort-Object) @($candidates.asset_id | Sort-Object)) { throw "Candidate IDs do not match the verified snapshot." }
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

$ok = 0
$failed = [System.Collections.Generic.List[string]]::new()
foreach ($candidate in $candidates) {
    $hash = $candidate.preview_sha256.ToLowerInvariant()
    if ($hash -notmatch '^[0-9a-f]{64}$' -or -not $candidate.preview_url) { $failed.Add("$($candidate.asset_id): missing valid hash or URL"); continue }
    $target = Join-Path $outputPath "$hash.jpg"
    if (Test-Path -LiteralPath $target -PathType Leaf) {
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -eq $hash) { $ok++; continue }
        $failed.Add("$($candidate.asset_id): existing hash-named file does not match expected SHA-256"); continue
    }
    $temporary = Join-Path $outputPath ([Guid]::NewGuid().ToString("N") + ".download")
    try {
        Invoke-WebRequest -Uri $candidate.preview_url -OutFile $temporary -Headers @{ "User-Agent" = "SE2026-T03-W4-Image-Benchmark/1.0" }
        if ((Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash) { throw "Downloaded preview SHA-256 mismatch." }
        Move-Item -LiteralPath $temporary -Destination $target
        $ok++
    } catch {
        $failed.Add("$($candidate.asset_id): $($_.Exception.Message)")
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
    Start-Sleep -Milliseconds 150
}

Write-Output "Verified previews: $ok / $($candidates.Count)"
if ($failed.Count) { $failed | ForEach-Object { Write-Warning $_ }; throw "Preview download incomplete; resolve the listed failures before annotation." }
Write-Output "Preview directory: $outputPath"
