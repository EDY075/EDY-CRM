# Roda uma rodada completa de prospecção: busca no Google Maps + filtra + gera WhatsApp.
# Uso:
#   .\buscar.ps1
# (antes, edite o arquivo queries.txt com o nicho + cidade que você quer buscar)

# Caminho do Node usado pelo Playwright embutido no scraper. Se o seu Node estiver
# em outro lugar, defina a variável de ambiente antes de rodar o script.
if (-not $env:PLAYWRIGHT_NODEJS_PATH) {
    $env:PLAYWRIGHT_NODEJS_PATH = (Get-Command node -ErrorAction Stop).Source
}

$data = Get-Date -Format "yyyy-MM-dd_HHmmss"
$arquivoBruto = "saidas\bruto_$data.csv"

Write-Host "Buscando no Google Maps..." -ForegroundColor Cyan
.\google-maps-scraper.exe -input queries.txt -results $arquivoBruto -lang pt -depth 5 -exit-on-inactivity 3m

if (Test-Path $arquivoBruto) {
    Write-Host "Filtrando leads (nota >= 4.0, sem site) e gerando WhatsApp..." -ForegroundColor Cyan
    py processar.py $arquivoBruto
} else {
    Write-Host "Nenhum resultado bruto foi gerado - confira o queries.txt e tente de novo." -ForegroundColor Red
}
