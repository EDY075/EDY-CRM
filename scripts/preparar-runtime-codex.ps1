param([Parameter(Mandatory=$true)][string]$Origem,[string]$OrigemCodeModeHost)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtimeConfig = Get-Content -LiteralPath (Join-Path $projectRoot 'config/codex-runtime.json') -Raw | ConvertFrom-Json
$sourceFile = (Resolve-Path -LiteralPath $Origem).Path
$runtimeTarget = [IO.Path]::GetFullPath((Join-Path $projectRoot $runtimeConfig.executavel))
if (-not $runtimeTarget.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar)) { throw 'Destino fora do projeto.' }
$digest = (Get-FileHash -LiteralPath $sourceFile -Algorithm SHA256).Hash.ToLowerInvariant()
if ($digest -ne $runtimeConfig.sha256) { throw 'O binário não corresponde ao hash fixado. Confira distribuição e versão antes de alterar o manifesto.' }
$reportedVersion = & $sourceFile --version
if ($LASTEXITCODE -ne 0 -or $reportedVersion -ne ('codex-cli ' + $runtimeConfig.versao)) { throw 'Versão incompatível com o manifesto.' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $runtimeTarget) | Out-Null
if ($sourceFile -ne $runtimeTarget) { Copy-Item -LiteralPath $sourceFile -Destination $runtimeTarget }
foreach ($companion in $runtimeConfig.companheiros) {
 $targetPath=[IO.Path]::GetFullPath((Join-Path $projectRoot $companion.executavel))
 if (-not $targetPath.StartsWith($projectRoot+[IO.Path]::DirectorySeparatorChar)) { throw 'Companheiro fora do projeto.' }
 if ($OrigemCodeModeHost) {
  $hostSource=(Resolve-Path -LiteralPath $OrigemCodeModeHost).Path
  if ((Get-FileHash -LiteralPath $hostSource -Algorithm SHA256).Hash.ToLowerInvariant() -ne $companion.sha256) { throw 'Hash do code-mode host incompatível.' }
  if ($hostSource -ne $targetPath) { Copy-Item -LiteralPath $hostSource -Destination $targetPath }
 }
 if (-not (Test-Path -LiteralPath $targetPath) -or (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $companion.sha256) { throw 'Prepare também codex-code-mode-host.exe da mesma versão oficial. A imagem nativa depende dele.' }
}
Write-Output ('Runtime local preparado: ' + $reportedVersion + '. Nenhuma instalação global alterada.')
