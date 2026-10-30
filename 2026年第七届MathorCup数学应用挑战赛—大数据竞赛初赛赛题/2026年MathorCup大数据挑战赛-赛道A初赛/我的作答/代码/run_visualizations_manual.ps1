param(
    [switch]$Clear
)

$ErrorActionPreference = "Stop"
$Code = Split-Path -Parent $MyInvocation.MyCommand.Path
$Viz = Join-Path $Code "可视化代码"
$FigureDir = Join-Path $Viz "图表"
$Python = "D:\MathorCup\_environments\mathorcup-venv\Scripts\python.exe"

if (!(Test-Path $Python)) {
    throw "找不到虚拟环境 Python: $Python"
}
New-Item -ItemType Directory -Force $FigureDir | Out-Null

if ($Clear) {
    Get-ChildItem $FigureDir -File | Remove-Item -Force
    Set-Content -Encoding UTF8 (Join-Path $Code "figures_manifest.csv") "figure,path,sha256,bytes"
}

$env:FIG_DIR = $FigureDir
$env:Q2_RESULTS = Join-Path $Code "项目代码\A_full_solution_v4\q2\results"

$scripts = @(
    "make_q1_dimension_audit.py",
    "make_q1_local_contribution_beeswarm.py",
    "make_heatmap_q1_matplotlib_v4.py",
    "make_q2_frequency_matplotlib.py",
    "make_q3_beer230_transfer_profile.py",
    "make_rest_figures.py"
)

foreach ($script in $scripts) {
    Write-Host "=== $script ===" -ForegroundColor Cyan
    & $Python (Join-Path $Viz $script)
}

Write-Host "完成。图片目录：$FigureDir" -ForegroundColor Green
Get-ChildItem $FigureDir -File | Select-Object Name, Length


