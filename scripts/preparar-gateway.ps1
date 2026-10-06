$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$config=Get-Content -LiteralPath (Join-Path $projectRoot 'config/gateway-runtime.json') -Raw | ConvertFrom-Json
$checkoutPath=[IO.Path]::GetFullPath((Join-Path $projectRoot $config.codigo))
if (-not $checkoutPath.StartsWith($projectRoot+[IO.Path]::DirectorySeparatorChar)) { throw 'Checkout fora do projeto.' }
if (-not (Test-Path -LiteralPath $checkoutPath)) { git clone --no-checkout $config.repositorio $checkoutPath; if ($LASTEXITCODE -ne 0) { throw 'Clone falhou.' }; git -C $checkoutPath checkout --detach $config.commit }
if ((git -C $checkoutPath rev-parse HEAD).Trim() -ne $config.commit) { throw 'Commit do gateway diverge do pin. Nenhum reset automático realizado.' }
$lockSource=Join-Path $projectRoot $config.lock
if ((Get-FileHash -LiteralPath $lockSource -Algorithm SHA256).Hash.ToLowerInvariant() -ne $config.lock_sha256) { throw 'Lock do gateway alterado.' }
Copy-Item -LiteralPath $lockSource -Destination (Join-Path $checkoutPath 'package-lock.json')
# Estas variáveis ficam apenas no processo deste script, sem alteração global.
$env:DATA_DIR=Join-Path $projectRoot $config.dados
$env:USERPROFILE=Join-Path $projectRoot '.cache/gateway-home'
$env:APPDATA=Join-Path $env:USERPROFILE 'AppData/Roaming'
$env:LOCALAPPDATA=Join-Path $env:USERPROFILE 'AppData/Local'
$env:TEMP=Join-Path $projectRoot '.cache/gateway-tmp'; $env:TMP=$env:TEMP
$env:npm_config_cache=Join-Path $projectRoot '.cache/npm-gateway'; $env:NEXT_TELEMETRY_DISABLED='1'
New-Item -ItemType Directory -Force -Path $env:DATA_DIR,$env:TEMP,$env:USERPROFILE,$env:APPDATA,$env:LOCALAPPDATA | Out-Null
Push-Location -LiteralPath $checkoutPath
try {
 if (Test-Path -LiteralPath 'package-lock.json') { npm ci --ignore-scripts --no-audit --no-fund } else { npm install --ignore-scripts --no-audit --no-fund }
 if ($LASTEXITCODE -ne 0) { throw 'Instalação local falhou.' }
 npm run build
 if ($LASTEXITCODE -ne 0) { throw 'Build do gateway falhou.' }
} finally { Pop-Location }
Write-Output 'Gateway preparado neste projeto com commit fixado; upstreams continuam pendentes de acesso próprio.'
