$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $env:PIP_CACHE_DIR = Join-Path $PSScriptRoot '.cache\pip'
    $env:PYTHONUTF8 = '1'
    $env:npm_config_cache = Join-Path $PSScriptRoot '.cache\npm'
    $env:TEMP = Join-Path $PSScriptRoot '.cache\tmp'
    $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Force $env:TEMP | Out-Null
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel criar o ambiente Python.' }
    }
    & .\.venv\Scripts\python.exe -m pip install 'pip==26.2.1'
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar o pip local.' }
    & .\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências Python.' }
    Push-Location frontend
    try {
        npm ci --ignore-scripts --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências frontend.' }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar a interface.' }
    } finally { Pop-Location }
    Write-Host 'Pronto. Execute .\iniciar-ed-crm.ps1 e abra http://127.0.0.1:5128'
} finally { Pop-Location }
