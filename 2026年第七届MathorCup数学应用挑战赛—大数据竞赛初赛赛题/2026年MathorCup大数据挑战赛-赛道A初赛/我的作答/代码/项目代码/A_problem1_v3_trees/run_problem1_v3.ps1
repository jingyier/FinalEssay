param(
    [string]$PythonData = 'C:\Users\llxxz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',
    [string]$PythonML = 'C:\Users\llxxz\AppData\Local\Python\pythoncore-3.10-64\python.exe'
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath $PythonData)) { throw "PythonData not found: $PythonData" }
if (-not (Test-Path -LiteralPath $PythonML)) { throw "PythonML not found: $PythonML" }

& $PythonData (Join-Path $PSScriptRoot 'src\extract_inputs.py')
if ($LASTEXITCODE -ne 0) { throw 'Workbook input audit failed.' }

& $PythonML (Join-Path $PSScriptRoot 'src\solve_problem1_v3.py')
if ($LASTEXITCODE -ne 0) { throw 'Model fitting and score calculation failed.' }

& $PythonData (Join-Path $PSScriptRoot 'src\write_scorecards.py')
if ($LASTEXITCODE -ne 0) { throw 'Excel scorecard writing failed.' }

Write-Host 'Problem 1 v3 reproduced successfully.'
