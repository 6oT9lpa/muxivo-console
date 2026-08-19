[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$runtimeDirectory = Join-Path $repositoryRoot ".dev"

foreach ($name in @("api", "web")) {
    $pidFile = Join-Path $runtimeDirectory "$name.pid"
    if (-not (Test-Path -LiteralPath $pidFile)) { continue }
    $processId = [int](Get-Content -LiteralPath $pidFile -Raw)
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $pidFile -Force
}

Push-Location $repositoryRoot
try {
    docker compose -f docker-compose.dev.yml down | Out-Host
} finally {
    Pop-Location
}

Write-Host "Muxivo Console development processes have stopped. PostgreSQL data is preserved in the Docker volume."
