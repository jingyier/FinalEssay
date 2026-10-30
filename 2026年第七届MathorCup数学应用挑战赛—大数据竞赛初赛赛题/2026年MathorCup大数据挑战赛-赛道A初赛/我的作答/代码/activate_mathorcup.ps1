# Activate the reproducibility environment for this project.
$envRoot = 'D:\MathorCup\.mathorcup-venv'
$projectCode = 'D:\MathorCup\2026年第七届MathorCup数学应用挑战赛—大数据竞赛初赛赛题\2026年MathorCup大数据挑战赛-赛道A初赛\我的作答\代码'
& "$envRoot\Scripts\Activate.ps1"
Set-Location $projectCode
Write-Host "MathorCup environment active: $env:VIRTUAL_ENV"

