param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$PythonPath = "$((Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path '.venv\\Scripts\\python.exe'))",
    [string]$CeleryPath = "$((Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path '.venv\\Scripts\\celery.exe'))",
    [switch]$SkipContainers
)

Write-Host "[*] Starting PDF Convert stack from $ProjectRoot" -ForegroundColor Cyan

if (-not $SkipContainers) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker Desktop is required to launch Redis/PostgreSQL/Ollama containers.'
    }

    $composeFile = Join-Path $PSScriptRoot 'docker-compose.windows.yml'
    Write-Host "[*] Booting infrastructure containers (Redis, PostgreSQL, Ollama)..." -ForegroundColor Cyan
    docker compose -f $composeFile up -d | Out-Null
}

if (-not (Test-Path $PythonPath)) {
    throw "Python virtual environment not found at $PythonPath. Update the -PythonPath parameter."
}
if (-not (Test-Path $CeleryPath)) {
    throw "Celery executable not found at $CeleryPath. Update the -CeleryPath parameter."
}

$databaseUrl = 'postgresql+psycopg://pdf_convert:pdf_convert@localhost:5432/pdf_convert'
$redisUrl = 'redis://localhost:6379/0'
$sharedEnv = @{
    'PDFCONVERT_DATABASE_URL'      = $databaseUrl
    'PDFCONVERT_REDIS_URL'         = $redisUrl
}
foreach ($name in 'PDFCONVERT_LLM_PROVIDER','PDFCONVERT_LLM_BASE_URL','PDFCONVERT_LLM_MODEL','PDFCONVERT_LLM_FALLBACK_ENABLED') {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    if (-not $value) {
        $value = [Environment]::GetEnvironmentVariable($name, 'Machine')
    }
    if (-not $value) {
        $value = [Environment]::GetEnvironmentVariable($name, 'User')
    }
    if ($value) {
        $sharedEnv[$name] = $value
    }
}

Write-Host "[*] Launching FastAPI (uvicorn)" -ForegroundColor Cyan
$backendCommand = @(
    '-NoExit',
    '-Command',
    "Set-Location '$ProjectRoot'; & '$PythonPath' -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8000"
)
Start-Process -FilePath 'powershell.exe' -ArgumentList $backendCommand -Environment $sharedEnv | Out-Null

Start-Sleep -Seconds 2

Write-Host "[*] Launching Celery worker" -ForegroundColor Cyan
$workerCommand = @(
    '-NoExit',
    '-Command',
    "Set-Location '$ProjectRoot'; & '$CeleryPath' -A src.backend.celery_app worker --loglevel=INFO"
)
Start-Process -FilePath 'powershell.exe' -ArgumentList $workerCommand -Environment $sharedEnv | Out-Null

Write-Host "[+] Stack started. Ensure Windows Firewall allows inbound TCP 8000/6379/5432/11434 for trusted networks." -ForegroundColor Green
Write-Host "[!] If using external LLM providers, verify outbound HTTPS (TCP 443) is permitted for the target endpoints." -ForegroundColor Yellow
