param([switch]$Demo, [int]$Porta = 5128)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Execute .\configurar-ed-crm.ps1 primeiro.' }
    if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Compile a interface com .\configurar-ed-crm.ps1.' }
    $env:PYTHONUTF8 = '1'
    $env:TEMP = Join-Path $PSScriptRoot '.cache\tmp'
    $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Force $env:TEMP | Out-Null
    $argumentos = @('scripts/servir-crm.py', '--port', "$Porta")
    if ($Demo) { $argumentos += '--demo' }
    & .\.venv\Scripts\python.exe @argumentos
    if ($LASTEXITCODE -ne 0) { throw 'Servidor encerrou com erro. Confira a porta escolhida.' }
} finally { Pop-Location }
