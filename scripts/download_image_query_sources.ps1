param(
    [string]$CsvPath = "data/benchmark/image_query_sources_v1.csv",
    [string]$OutputDirectory = "data/benchmark/query_images/source_candidates",
    [int]$ThumbnailWidth = 1280
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$workspacePath = (Get-Location).Path.TrimEnd("\", "/")
$csvFullPath = [System.IO.Path]::GetFullPath($CsvPath)
$outputFullPath = [System.IO.Path]::GetFullPath($OutputDirectory)
if (-not (Test-Path -LiteralPath $csvFullPath -PathType Leaf)) {
    throw "Source CSV not found: $csvFullPath"
}
New-Item -ItemType Directory -Force -Path $outputFullPath | Out-Null

$rows = @(Import-Csv -LiteralPath $csvFullPath)
if ($rows.Count -eq 0) { throw "Source CSV has no rows." }
$updatedRows = [System.Collections.Generic.List[object]]::new()

foreach ($row in $rows) {
    $uri = [Uri]$row.source_page_url
    $fileName = [Uri]::UnescapeDataString(($uri.AbsolutePath -split "/")[-1]).Replace("_", " ")
    if (-not $fileName.StartsWith("File:", [System.StringComparison]::OrdinalIgnoreCase)) {
        $fileName = "File:$fileName"
    }
    $filePathName = ($fileName -replace "^File:", "").Replace(" ", "_")
    $md5 = [System.Security.Cryptography.MD5]::Create()
    $fileHash = [BitConverter]::ToString($md5.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($filePathName))).Replace("-", "").ToLowerInvariant()
    $md5.Dispose()
    # Commons uses a non-obvious canonical title hash for this comma-containing filename.
    if ($row.candidate_category -eq "table_lamp") { $fileHash = "7c" }
    $fileLeafOnCommons = [Uri]::EscapeDataString($filePathName)
    $thumbLeaf = [Uri]::EscapeDataString("${ThumbnailWidth}px-$filePathName")
    $downloadUrl = "https://thumb.wikimedia.org/wikipedia/commons/thumb/$($fileHash.Substring(0, 1))/$($fileHash.Substring(0, 2))/$fileLeafOnCommons/$thumbLeaf"
    $extension = [System.IO.Path]::GetExtension($fileName)
    $fileLeaf = "{0}_{1}{2}" -f $row.candidate_category, $row.candidate_asset_id, $extension
    $targetPath = Join-Path $outputFullPath $fileLeaf
    $status = "download_failed"
    $sha256 = ""
    $relativePath = ""
    $notes = $row.notes

    if ($row.status -in @("downloaded_visual_review_pending", "owner_approved_candidate") -and -not [string]::IsNullOrWhiteSpace($row.local_image_path)) {
        $existingPath = Join-Path $workspacePath $row.local_image_path.Replace("/", "\")
        if (Test-Path -LiteralPath $existingPath -PathType Leaf) {
            $existingHash = (Get-FileHash -LiteralPath $existingPath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($existingHash -eq $row.sha256) {
                $updatedRows.Add($row)
                Write-Output ("{0}: reusing verified download, SHA-256 {1}" -f $row.candidate_category, $existingHash)
                continue
            }
        }
    }

    try {
        Invoke-WebRequest -Uri $downloadUrl -OutFile $targetPath -Headers @{ "User-Agent" = "SE2026-T03-W4-Benchmark/1.0 (image query provenance audit)" }
        if ((Get-Item -LiteralPath $targetPath).Length -lt 256) {
            throw "Downloaded file is unexpectedly small."
        }
        $sha256 = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $relativePath = $targetPath.Substring($workspacePath.Length).TrimStart("\", "/").Replace("\", "/")
        $status = "downloaded_visual_review_pending"
        Write-Output ("{0}: downloaded {1} bytes, SHA-256 {2}" -f $row.candidate_category, (Get-Item -LiteralPath $targetPath).Length, $sha256)
    } catch {
        $downloadError = "Download failed: $($_.Exception.Message)"
        $notes = (@($row.notes, $downloadError) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join " "
        Write-Warning ("{0}: {1}" -f $row.candidate_category, $downloadError)
        if (Test-Path -LiteralPath $targetPath) { Remove-Item -LiteralPath $targetPath -Force }
    }

    $updatedRows.Add([PSCustomObject]@{
        query_type = $row.query_type
        candidate_category = $row.candidate_category
        candidate_asset_id = $row.candidate_asset_id
        candidate_asset_name = $row.candidate_asset_name
        source_title = $row.source_title
        source_author = $row.source_author
        source_page_url = $row.source_page_url
        license = $row.license
        license_url = $row.license_url
        local_image_path = $relativePath
        sha256 = $sha256
        status = $status
        notes = $notes
        download_url = $downloadUrl
        visual_review_status = "pending"
    })
    Start-Sleep -Seconds 3
}

$updatedRows | Export-Csv -LiteralPath $csvFullPath -NoTypeInformation -Encoding UTF8
Write-Output ("Updated source inventory: {0}" -f $csvFullPath)
