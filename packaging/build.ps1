param([switch]$SkipInstall, [switch]$Incremental)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required to build.' }
}
if (-not $SkipInstall) {
    & $pythonExe -m pip install -r requirements-desktop.lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& $pythonExe packaging\prepare_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Asset preparation failed.' }
$cleanArgs = @()
if (-not $Incremental) { $cleanArgs += '--clean' }
& $pythonExe -m PyInstaller --noconfirm @cleanArgs --windowed --onedir --name RahulsToolbox --icon assets\toolbox.ico --add-data 'THIRD_PARTY_NOTICES.md:.' --add-data 'LICENSE:.' --add-data 'assets:assets' --collect-all pymupdf --collect-all pdf2docx --collect-all pypdf --collect-all rapidocr_onnxruntime --collect-all onnxruntime --collect-all shapely --hidden-import PIL --hidden-import send2trash --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick desktop.pyw
if ($LASTEXITCODE -ne 0) { throw 'Application bundling failed.' }
Copy-Item -LiteralPath THIRD_PARTY_NOTICES.md, LICENSE -Destination dist\RahulsToolbox
& $pythonExe packaging\prepare_release.py
if ($LASTEXITCODE -ne 0) { throw 'Release preparation failed.' }
$compilerPaths = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
)
$compiler = $compilerPaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $compiler) { throw 'Install Inno Setup 6 (winget install JRSoftware.InnoSetup), then run this script again.' }
$compiled = $false
for ($setupAttempt = 1; $setupAttempt -le 3; $setupAttempt++) {
    $stagingDirectory = Join-Path $projectRoot ('artifacts\setup-staging-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $stagingDirectory | Out-Null
    & $compiler /Qp ('/O' + $stagingDirectory) packaging\installer.iss
    if ($LASTEXITCODE -eq 0) {
        Copy-Item -LiteralPath (Join-Path $stagingDirectory 'RahulsToolbox-3.3.0-Setup.exe') -Destination (Join-Path $projectRoot 'release\RahulsToolbox-3.3.0-Setup.exe') -Force
        $compiled = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $compiled) { throw 'Installer compilation failed after three fresh staging attempts.' }
Get-FileHash -Algorithm SHA256 release\RahulsToolbox-3.3.0-Setup.exe | Format-List
