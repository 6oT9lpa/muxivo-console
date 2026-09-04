[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$runtimeDirectory = Join-Path $repositoryRoot ".dev"
$environmentFile = Join-Path $runtimeDirectory "console.env"
$python = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
$webDirectory = Join-Path $repositoryRoot "apps\web"
$webLog = Join-Path $runtimeDirectory "web.log"
$webErrorLog = Join-Path $runtimeDirectory "web.error.log"
$webPidFile = Join-Path $runtimeDirectory "web.pid"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment is missing. Create it with: py -3.12 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e '.[dev]'"
}
if (-not (Test-Path -LiteralPath (Join-Path $webDirectory "node_modules"))) {
    throw "Web dependencies are missing. Run: Push-Location apps\web; npm install; Pop-Location"
}

function New-RandomBase64([int]$Length = 32) {
    $bytes = [byte[]]::new($Length)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes)
}

function New-FernetKey {
    $bytes = [byte[]]::new(32)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_").TrimEnd("=") + "="
}

function Import-EnvironmentFile([string]$Path) {
    Get-Content -LiteralPath $Path | ForEach-Object {
        if ($_ -match "^([^#=]+)=(.*)$") {
            Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2]
        }
    }
}

function Test-ProcessRunning([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    try {
        Get-Process -Id ([int](Get-Content -LiteralPath $Path -Raw)) -ErrorAction Stop | Out-Null
        return $true
    } catch {
        Remove-Item -LiteralPath $Path -Force
        return $false
    }
}

New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
if (-not (Test-Path -LiteralPath $environmentFile)) {
    @(
        "MUXIVO_CONSOLE_ENVIRONMENT=development"
        "MUXIVO_CONSOLE_DATABASE_URL=postgresql+asyncpg://muxivo:muxivo@postgres:5432/muxivo_console"
        "MUXIVO_CONSOLE_EMAIL_LOOKUP_KEY=$(New-RandomBase64)"
        "MUXIVO_CONSOLE_EMAIL_ENCRYPTION_KEY=$(New-FernetKey)"
        "MUXIVO_CONSOLE_SESSION_TOKEN_PEPPER=$(New-RandomBase64)"
        "MUXIVO_DISCORD_CONTROL_BASE_URL=http://127.0.0.1:8030"
        "MUXIVO_DISCORD_CONTROL_SIGNING_KEY=$(New-RandomBase64)"
    ) | Set-Content -LiteralPath $environmentFile -Encoding utf8
}
else {
    $environmentContent = Get-Content -LiteralPath $environmentFile -Raw
    $legacyDatabaseUrl = "postgresql+asyncpg://muxivo:muxivo@127.0.0.1:5432/muxivo_console"
    $containerDatabaseUrl = "postgresql+asyncpg://muxivo:muxivo@postgres:5432/muxivo_console"
    if ($environmentContent.Contains($legacyDatabaseUrl)) {
        $environmentContent.Replace($legacyDatabaseUrl, $containerDatabaseUrl) |
            Set-Content -LiteralPath $environmentFile -Encoding utf8
    }
}

Import-EnvironmentFile $environmentFile
Push-Location $repositoryRoot
try {
    docker compose -f docker-compose.dev.yml up -d --build --wait postgres api | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop must be running before the Console development environment can start."
    }
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            if ((Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/healthz").StatusCode -eq 200) { break }
        } catch {
            Start-Sleep -Seconds 1
        }
        if ($attempt -eq 30) { throw "Console API did not become ready. Run: docker compose -f docker-compose.dev.yml logs api" }
    }

    if (-not (Test-ProcessRunning $webPidFile)) {
        $web = Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") -WorkingDirectory $webDirectory -WindowStyle Hidden -RedirectStandardOutput $webLog -RedirectStandardError $webErrorLog -PassThru
        Set-Content -LiteralPath $webPidFile -Value $web.Id -Encoding ascii
    }
} finally {
    Pop-Location
}

Write-Host "Muxivo Console is ready at http://127.0.0.1:5173"
Write-Host "Use the Create account flow; an account is created only after the six-digit e-mail code is verified."
Write-Host "Configure development SMTP variables in $environmentFile to exercise real verification and recovery delivery."
Write-Host "The real Discord Control API is optional for this local Console walkthrough; its URL is configured in $environmentFile."
