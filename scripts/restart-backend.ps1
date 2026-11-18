# 重启本地 FastAPI 后端（端口 8010）。
#
# 用法：
#   powershell -File scripts/restart-backend.ps1
#
# 必须在 backend/ 下启动：DATABASE_URL 默认是 sqlite:///./zhixueban.db，
# 工作目录不对会读到另一个空库。

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$port = 8010

$pids = @()
netstat -ano | Select-String -Pattern ":$port\s+.*LISTENING" | ForEach-Object {
    $parts = ($_.ToString() -split '\s+') | Where-Object { $_ -ne '' }
    $procId = [int]$parts[-1]
    if ($procId -gt 0) { $script:pids += $procId }
}
$pids = $pids | Select-Object -Unique
foreach ($procId in $pids) {
    Write-Host "停止占用端口 $port 的进程 $procId"
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}
if ($pids.Count -gt 0) { Start-Sleep -Seconds 1 }

Write-Host "从 $backend 启动 uvicorn :$port"
Set-Location $backend
python -m uvicorn app.main:app --host 127.0.0.1 --port $port
