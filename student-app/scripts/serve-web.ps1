# 托管最新 Flutter Web 构建（需先 flutter build web）
# 用法: .\scripts\serve-web.ps1 [-Port 8898] [-Rebuild]
param(
  [int]$Port = 8898,
  [switch]$Rebuild
)

$appRoot = Split-Path $PSScriptRoot -Parent
Set-Location $appRoot

if ($Rebuild) {
  & flutter build web --release --dart-define=API_BASE=http://127.0.0.1:8010
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$web = Join-Path $appRoot "build\web"
if (-not (Test-Path $web)) {
  Write-Error "缺少 build/web，请先运行: flutter build web --release --dart-define=API_BASE=http://127.0.0.1:8010"
  exit 1
}

Write-Host "Serving $web on http://127.0.0.1:$Port/ (Ctrl+C 停止)"
Set-Location $web
python -m http.server $Port
