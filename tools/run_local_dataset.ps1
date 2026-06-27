param(
    [string]$Root = ""
)

$ErrorActionPreference = "Stop"

if (-not $Root) {
    throw "Please pass -Root with your dataset path, for example: .\tools\run_local_dataset.ps1 -Root 'D:\SR数据集\livePhoto_out'"
}

$root = $Root
$sources = @(
    (Join-Path $root "HR"),
    (Join-Path $root "LR"),
    (Join-Path $root "LR_aligned_adaptive_3d_lut"),
    (Join-Path $root "LR_color_adaptive_3d_lut")
)

foreach ($path in $sources) {
    if (-not (Test-Path $path)) {
        throw "Missing source path: $path"
    }
}

$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
& $python -m remote_image_compare.app `
    --source $sources[0] `
    --source $sources[1] `
    --source $sources[2] `
    --source $sources[3]
