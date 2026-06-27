param()

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Missing virtual environment Python: $python"
}

Push-Location $root
$originalPath = $env:PATH
try {
    $env:PATH = (($env:PATH -split ';') | Where-Object {
        $_ -and ($_ -notmatch '\\anaconda3(\\|$)') -and ($_ -notmatch '\\conda(\\|$)')
    }) -join ';'

    & $python -m pip install -e ".[dev]"
    & $python -m PyInstaller --noconfirm --clean "RemoteImageCompare.spec"

    $distRoot = Join-Path $root "dist\RemoteImageCompare"
    $configRoot = Join-Path $distRoot ".remote_image_compare"
    if (-not (Test-Path $configRoot)) {
        New-Item -ItemType Directory -Path $configRoot | Out-Null
    }

    Write-Host "Build complete: $distRoot"
} finally {
    $env:PATH = $originalPath
    Pop-Location
}
