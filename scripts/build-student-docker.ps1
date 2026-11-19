#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Build KnoAct student-app Docker image on Windows via WSL Docker Engine,
  then export it as a .tar file.

.DESCRIPTION
  1. Flutter Web build in Windows (student-app/) with API_BASE="" (nginx proxy)
  2. Docker build via WSL Ubuntu — the WSL distro must have Docker Engine installed
     and its daemon running
  3. Export image to $OutputDir/knoact-student-app-<tag>.tar

.PARAMETER Tag
  Image tag, default "knoact-student-app:latest".

.PARAMETER SkipFlutter
  Skip the Flutter Web build step (use existing student-app/build/web).

.PARAMETER Push
  Also push the image after build. Requires DOCKER_REGISTRY env var set to the
  registry prefix (e.g. "registry.example.com/knoact/").

.PARAMETER OutputDir
  Directory to write the exported .tar file, default is the repo root.

.EXAMPLE
  .\scripts\build-student-docker.ps1
  .\scripts\build-student-docker.ps1 -Tag "knoact-student-app:v1.2.3"
  .\scripts\build-student-docker.ps1 -SkipFlutter   # Docker build only
  .\scripts\build-student-docker.ps1 -Push           # Build & push
#>

param(
    [string]$Tag = "knoact-student-app:latest",
    [switch]$SkipFlutter,
    [switch]$Push,
    [string]$OutputDir = $null
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot/..").Path
$AppDir   = Join-Path $RepoRoot "student-app"

if (-not $OutputDir) {
    $OutputDir = $RepoRoot
}
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$safeTag = $Tag -replace '[:/]', '-' -replace '[^a-zA-Z0-9._-]', '_'
$TarFile = Join-Path $OutputDir "knoact-student-app-$safeTag.tar"

# ── 1. Flutter Web build ──────────────────────────────────────────────
if (-not $SkipFlutter) {
    $total = if ($Push) { 4 } else { 3 }
    Write-Host "=== [1/$total] Flutter web build ===" -ForegroundColor Cyan
    Push-Location $AppDir
    try {
        flutter build web --release --no-web-resources-cdn --no-wasm-dry-run `
            --dart-define=API_BASE=""
        if ($LASTEXITCODE -ne 0) { throw "Flutter build failed" }
        Write-Host "Flutter web build done: $AppDir\build\web" -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

# ── 2. Docker build via WSL ───────────────────────────────────────────
$step = if ($SkipFlutter) { 1 } else { 2 }
$total = if ($Push) { $step + 2 } else { $step + 1 }
Write-Host "=== [$step/$total] Docker build ($Tag) ===" -ForegroundColor Cyan
$WslAppDir = ($AppDir -replace '\\', '/' -replace '^([A-Z]):', '/mnt/$1').ToLower()

wsl.exe -d Ubuntu -- bash -c "docker build -t $Tag $WslAppDir"
if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed (exit code $LASTEXITCODE)"
}
Write-Host "Docker build done: $Tag" -ForegroundColor Green

# ── 3. Export image ───────────────────────────────────────────────────
$step++
Write-Host "=== [$step/$total] Export $TarFile ===" -ForegroundColor Cyan
$WslTar = ($TarFile -replace '\\', '/' -replace '^([A-Z]):', '/mnt/$1').ToLower()
wsl.exe -d Ubuntu -- bash -c "docker save $Tag -o $WslTar"
if ($LASTEXITCODE -ne 0) {
    throw "Docker save failed (exit code $LASTEXITCODE)"
}
$tarSize = [math]::Round((Get-Item $TarFile).Length / 1MB, 1)
Write-Host "Exported: $TarFile ($tarSize MB)" -ForegroundColor Green

# ── 4. Push (optional) ────────────────────────────────────────────────
if ($Push) {
    if (-not $env:DOCKER_REGISTRY) {
        throw "DOCKER_REGISTRY env var not set (e.g. 'registry.example.com/knoact/')"
    }
    $remoteTag = $env:DOCKER_REGISTRY + ($Tag -replace '.*/(?=[^/]+$)', '')
    $step++
    Write-Host "=== [$step/$total] Push $remoteTag ===" -ForegroundColor Cyan
    wsl.exe -d Ubuntu -- bash -c "docker tag $Tag $remoteTag && docker push $remoteTag"
    if ($LASTEXITCODE -ne 0) { throw "Docker push failed" }
    Write-Host "Push done: $remoteTag" -ForegroundColor Green
}

Write-Host "`nDone. Image: $Tag | Export: $TarFile" -ForegroundColor Green