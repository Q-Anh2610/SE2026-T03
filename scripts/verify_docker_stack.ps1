<# Infrastructure smoke for #148. Does not seed data, download models or run retrieval. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9][a-z0-9_-]*$')]
    [string]$ProjectName,
    [string[]]$ComposeFiles = @('docker-compose.yml'),
    [string]$ReportPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$composeArgs = @('compose', '--project-name', $ProjectName)
foreach ($composeFile in $ComposeFiles) { $composeArgs += @('-f', $composeFile) }
$checks = [ordered]@{}
$report = [ordered]@{
    issue = 148
    scope = 'docker_infrastructure_only'
    project = $ProjectName
    started_at = [DateTime]::UtcNow.ToString('o')
    os = [Environment]::OSVersion.VersionString
    powershell = $PSVersionTable.PSVersion.ToString()
    status = 'failed'
    checks = $checks
    retrieval_verified = $false
    e2e_verified = $false
    benchmark_verified = $false
}

function Invoke-Compose {
    param([string[]]$CommandArgs)
    $result = & docker @composeArgs @CommandArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed (exit $LASTEXITCODE)." }
    return $result
}

function Get-ServiceOrigin {
    param([string]$Service, [int]$ContainerPort)
    $binding = (Invoke-Compose @('port', $Service, "$ContainerPort") | Out-String).Trim()
    if ($binding -notmatch '^127\.0\.0\.1:[0-9]+$') {
        throw "Expected a loopback-only published port for $Service."
    }
    return "http://$binding"
}

function Get-Response {
    param([string]$Url)
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15
    if ($response.StatusCode -ne 200) { throw 'HTTP probe failed.' }
    return $response
}

Push-Location $repoRoot
try {
    if (-not (Test-Path -LiteralPath '.env' -PathType Leaf)) {
        throw 'Prepare the local .env using the runbook before verifying.'
    }
    $report['commit'] = (& git rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read source commit.' }
    $sourceChanges = @(& git status --porcelain --untracked-files=normal)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read source status.' }
    $report['dirty'] = $sourceChanges.Count -gt 0
    $sourceHashes = [ordered]@{}
    foreach ($sourcePath in @(
        'docker-compose.yml', 'docker-compose.search.yml', 'backend/Dockerfile',
        'backend/.dockerignore', 'backend/requirements.txt', 'frontend/Dockerfile',
        'frontend/.dockerignore', 'frontend/nginx.conf', 'frontend/package-lock.json',
        'scripts/verify_docker_stack.ps1', '.github/workflows/docker-stack.yml'
    )) {
        $sourceHashes[$sourcePath] = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourcePath).Hash.ToLowerInvariant()
    }
    $report['source_sha256'] = $sourceHashes
    $report['compose_version'] = (Invoke-Compose @('version', '--short') | Out-String).Trim()
    $report['docker_server_version'] = (& docker version --format '{{.Server.Version}}' | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read Docker server version.' }
    $report['image_ids'] = @(Invoke-Compose @('images', '--quiet') | Sort-Object -Unique)
    # Compose emits JSON objects per line; older releases may emit an array.
    $rows = @(Invoke-Compose @('ps', '--all', '--format', 'json') |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        ForEach-Object { $_ | ConvertFrom-Json })
    foreach ($service in @('postgres', 'qdrant', 'backend', 'frontend')) {
        $serviceRows = @($rows | Where-Object { $_.Service -eq $service })
        if ($serviceRows.Count -ne 1 -or $serviceRows[0].State -ne 'running' -or $serviceRows[0].Health -ne 'healthy') {
            throw "Service $service must have exactly one running, healthy container."
        }
        $checks[$service] = 'running_healthy'
    }
    $migration = @($rows | Where-Object { $_.Service -eq 'migrate' })
    if ($migration.Count -ne 1 -or $migration[0].State -ne 'exited' -or $migration[0].ExitCode -ne 0) {
        throw 'Migration must have exited successfully.'
    }
    $checks['migration_container'] = 'exited_0'
    $revisionFile = Get-ChildItem -LiteralPath 'backend/alembic/versions' -Filter '*.py' |
        Where-Object { $_.BaseName -match '^[0-9]{4}_' } |
        Sort-Object Name | Select-Object -Last 1
    $expectedRevision = $revisionFile.BaseName.Split('_')[0]
    $revision = Invoke-Compose @('exec', '-T', 'backend', 'python', '-m', 'alembic', 'current') | Out-String
    if ($revision -notmatch "(?m)^$expectedRevision\s+\(head\)") {
        throw 'Database migration revision does not match the repository head.'
    }
    $checks['database_revision'] = $expectedRevision
    $ui = Get-ServiceOrigin 'frontend' 80
    $api = Get-ServiceOrigin 'backend' 8000
    $qdrant = Get-ServiceOrigin 'qdrant' 6333
    $page = Get-Response "$ui/"
    if ($page.Content -notmatch '<div id="root">') { throw 'UI HTML is missing its React root.' }
    $checks['ui_html'] = 'http_200_react_root'
    $null = Get-Response "$ui/ui-healthz"
    foreach ($origin in @($api, $ui)) {
        $health = (Get-Response "$origin/healthz").Content | ConvertFrom-Json
        if ($health.status -ne 'ok') { throw 'API liveness response is invalid.' }
    }
    $checks['backend_and_proxy_liveness'] = 'http_200_status_ok'
    $assets = (Get-Response "$ui/api/v1/assets?page=1&limit=1").Content | ConvertFrom-Json
    if ($assets.mock -ne $false -or $assets.pagination.page -ne 1 -or $assets.pagination.limit -ne 1) {
        throw 'Asset API must read PostgreSQL through the frontend proxy.'
    }
    $checks['ui_proxy_postgres_assets'] = 'http_200_mock_false'
    $null = Get-Response "$qdrant/readyz"
    $collections = (Get-Response "$qdrant/collections").Content | ConvertFrom-Json
    $checks['qdrant_ready'] = 'http_200'
    $checks['qdrant_collection_count'] = @($collections.result.collections).Count
    $report['status'] = 'infrastructure_verified'
}
finally {
    try {
        $report['finished_at'] = [DateTime]::UtcNow.ToString('o')
        if (-not $ReportPath) {
            $ReportPath = Join-Path $repoRoot ('data/runtime/issue148/' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '.json')
        }
        if (-not [IO.Path]::IsPathRooted($ReportPath)) { $ReportPath = Join-Path $repoRoot $ReportPath }
        $fullReportPath = [IO.Path]::GetFullPath($ReportPath)
        if (Test-Path -LiteralPath $fullReportPath) { throw 'Refusing to overwrite an existing report.' }
        $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $fullReportPath)
        [IO.File]::WriteAllText($fullReportPath, ($report | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
        Write-Output "Report: $fullReportPath"
        Write-Output "Status: $($report.status); retrieval/E2E/benchmark not verified."
        Write-Output ($report | ConvertTo-Json -Depth 8)
    }
    finally { Pop-Location }
}
