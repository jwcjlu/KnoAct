# 清理已合入 master 的本地 feature 分支。
#
# 用法：
#   powershell -File scripts/clean-merged-branches.ps1            # 只列出，不删
#   powershell -File scripts/clean-merged-branches.ps1 -Apply     # 真的删
#
# 只删「已完全合入 master」的分支，并按白名单过滤——仓库里有些分支名看起来像
# feature 但其实还挂着别的用途，误删代价高于收益。要加白名单直接改下面的数组。

param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# 只考虑这些前缀的分支
$patterns = @("feat/practice-parsing-*", "feature/practice-parsing-*")
# 永不删除
$protect = @("master", "main", "develop")

$current = (git rev-parse --abbrev-ref HEAD).Trim()
$merged = git branch --merged master |
    ForEach-Object { $_.Trim().TrimStart('*').Trim() } |
    Where-Object { $_ -and $_ -ne "" }

$targets = @()
foreach ($name in $merged) {
    if ($protect -contains $name) { continue }
    if ($name -eq $current) { continue }
    $hit = $false
    foreach ($p in $patterns) { if ($name -like $p) { $hit = $true } }
    if ($hit) { $targets += $name }
}

if ($targets.Count -eq 0) {
    Write-Host "没有已合入 master 的可清理分支（当前在 $current）"
    exit 0
}

Write-Host "已合入 master 的候选分支："
foreach ($t in $targets) { Write-Host "  - $t" }

if (-not $Apply) {
    Write-Host ""
    Write-Host "这是预演。加 -Apply 才会真的删除："
    Write-Host "  powershell -File scripts/clean-merged-branches.ps1 -Apply"
    exit 0
}

foreach ($t in $targets) {
    Write-Host "删除 $t"
    # -d 只删已合并的；万一判断有误 git 会拒绝，不会丢提交
    git branch -d $t
}

Write-Host "完成。当前分支：$((git rev-parse --abbrev-ref HEAD).Trim())"
