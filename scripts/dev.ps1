# 一键管理本地三个服务（后端 / 家长端 / 学生端）。
#
# 用法（仓库根目录）：
#   powershell -File scripts/dev.ps1 -Status      # 看状态（默认）
#   powershell -File scripts/dev.ps1 -Start       # 起没在跑的服务
#   powershell -File scripts/dev.ps1 -Stop        # 停掉三个服务
#   powershell -File scripts/dev.ps1 -Restart     # 先停再起
#
# 设计要点（都是踩过坑总结的）：
#   1. 用 netstat 判端口，不用 Get-NetTCPConnection —— 后者看不到 dartvm
#      等进程名占用的端口，会把「正在跑」误报成 DOWN，导致重复启动撞端口。
#   2. 用 Start-Process 起服务，脱离当前终端会话 —— 终端超时不会带走服务，
#      也就不会再有「任务失败」通知。
#   3. 停服务按「监听该端口的 PID」精确 stop，不按进程名杀（避免误杀别的
#      python / dart）。
#   4. 启动前检查端口占用，已占用就跳过并说明，不会起第二份撞端口。

param(
    [switch]$Start,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$Status
)

$ErrorActionPreference = "Stop"

# 没有显式指定动作时默认看状态
if (-not ($Start -or $Stop -or $Restart -or $Status)) { $Status = $true }

$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root ".devlogs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$flutterBin = "E:\dev\flutter\bin"

# name=显示名 port=端口 workdir=启动目录 args=命令与参数
$services = @(
    @{
        name    = "backend"
        port    = 8010
        workdir = Join-Path $root "backend"
        exe     = "python"
        args    = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8010")
        log     = "backend.log"
        probe   = "http://127.0.0.1:8010/docs"
    },
    @{
        name    = "parent-web"
        port    = 8767
        workdir = $root
        exe     = "python"
        args    = @("-m", "http.server", "8767", "--directory", "parent-web")
        log     = "parent-web.log"
        probe   = "http://127.0.0.1:8767/"
    },
    @{
        name    = "student-app"
        port    = 8082
        workdir = Join-Path $root "student-app"
        exe     = Join-Path $flutterBin "flutter.bat"
        args    = @("run", "-d", "web-server", "--web-hostname=127.0.0.1", "--web-port=8082")
        log     = "student-app.log"
        probe   = "http://127.0.0.1:8082/"
    }
)

function Get-ListeningPid([int]$port) {
    # netstat 比 Get-NetTCPConnection 可靠：后者漏报 dartvm 等
    $lines = netstat -ano | Select-String -Pattern ":$port\s+.*LISTENING"
    foreach ($ln in $lines) {
        $parts = ($ln.ToString() -split '\s+') | Where-Object { $_ -ne '' }
        $procId = 0
        if ([int]::TryParse($parts[-1], [ref]$procId) -and $procId -gt 0) {
            return $procId
        }
    }
    return $null
}

function Test-Http([string]$url, [int]$timeoutSec = 5) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSec
        return $r.StatusCode
    } catch {
        return $null
    }
}

function Show-Status {
    Write-Host "=== 服务状态 ===" -ForegroundColor Cyan
    foreach ($s in $services) {
        $procId = Get-ListeningPid $s.port
        if ($null -eq $procId) {
            Write-Host ("  {0,-12} :{1}  DOWN" -f $s.name, $s.port) -ForegroundColor Red
            continue
        }
        $code = Test-Http $s.probe
        if ($code) {
            Write-Host ("  {0,-12} :{1}  UP  pid={2}  HTTP {3}" -f $s.name, $s.port, $procId, $code) -ForegroundColor Green
        } else {
            Write-Host ("  {0,-12} :{1}  LISTENING pid={2}  但 HTTP 无响应" -f $s.name, $s.port, $procId) -ForegroundColor Yellow
        }
    }
}

function Start-Services {
    foreach ($s in $services) {
        $procId = Get-ListeningPid $s.port
        if ($null -ne $procId) {
            Write-Host "  $($s.name) :$($s.port) 已在运行（pid=$procId），跳过" -ForegroundColor DarkGray
            continue
        }
        if (-not (Test-Path $s.workdir)) {
            Write-Host "  $($s.name) 目录不存在：$($s.workdir)" -ForegroundColor Red
            continue
        }
        $logPath = Join-Path $logDir $s.log
        Write-Host "  启动 $($s.name) :$($s.port)  日志 -> $logPath" -ForegroundColor Cyan
        # -WindowStyle Hidden 让服务不依赖当前终端；输出重定向到日志文件
        Start-Process -FilePath $s.exe -ArgumentList $s.args `
            -WorkingDirectory $s.workdir -WindowStyle Hidden `
            -RedirectStandardOutput $logPath `
            -RedirectStandardError "$logPath.err" | Out-Null
    }
    Write-Host ""
    Write-Host "等待就绪（最多 90 秒）…" -ForegroundColor DarkGray
    for ($i = 0; $i -lt 45; $i++) {
        Start-Sleep -Seconds 2
        $allUp = $true
        foreach ($s in $services) {
            if ($null -eq (Get-ListeningPid $s.port)) { $allUp = $false }
        }
        if ($allUp) { break }
    }
}

function Stop-Services {
    foreach ($s in $services) {
        $procId = Get-ListeningPid $s.port
        if ($null -eq $procId) {
            Write-Host "  $($s.name) :$($s.port) 未在运行" -ForegroundColor DarkGray
            continue
        }
        Write-Host "  停止 $($s.name) :$($s.port) (pid=$procId)" -ForegroundColor Yellow
        # 只停监听该端口的进程；flutter 会派生子进程，一并停掉
        try {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) {
                $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue
                foreach ($c in $children) {
                    Stop-Process -Id $c.ProcessId -Force -ErrorAction SilentlyContinue
                }
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        } catch {
            Write-Host "    停止失败：$($_.Exception.Message)" -ForegroundColor Red
        }
    }
    Start-Sleep -Seconds 2
}

if ($Restart) {
    Write-Host "=== 重启 ===" -ForegroundColor Cyan
    Stop-Services
    Start-Services
    Write-Host ""
    Show-Status
} elseif ($Stop) {
    Write-Host "=== 停止 ===" -ForegroundColor Cyan
    Stop-Services
    Show-Status
} elseif ($Start) {
    Write-Host "=== 启动 ===" -ForegroundColor Cyan
    Start-Services
    Write-Host ""
    Show-Status
} else {
    Show-Status
    Write-Host ""
    Write-Host "操作：-Start / -Stop / -Restart / -Status" -ForegroundColor DarkGray
}
