$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$verificationRoot = Join-Path $projectRoot ('artifacts\installer-verification-3.3.0-' + [guid]::NewGuid().ToString('N'))
# Compile identical payload with a separate test identity. Never change a
# user's real install/uninstall registration while verifying a release.
$compiler = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    $compiler = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
}
& $compiler /Qp /DVerificationBuild ('/O' + $verificationRoot) (Join-Path $PSScriptRoot 'installer.iss')
if ($LASTEXITCODE -ne 0) { throw 'Verification installer compilation failed.' }
$installerExe = Join-Path $verificationRoot 'RahulsToolbox-3.3.0-Setup.exe'
$installationFolder = Join-Path $verificationRoot 'application'
$resultsFolder = Join-Path $verificationRoot 'results'
New-Item -ItemType Directory -Force -Path $verificationRoot | Out-Null
if (Test-Path -LiteralPath $installationFolder) { throw 'Verification target already exists. Choose a fresh verification directory.' }
$verificationGroup = 'RahulsToolbox Verification'
$setupArguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/GROUP="' + $verificationGroup + '"'),
    ('/DIR="' + $installationFolder + '"'),
    ('/LOG="' + (Join-Path $verificationRoot 'setup.log') + '"'))
$setup = Start-Process -FilePath $installerExe -ArgumentList $setupArguments -WindowStyle Hidden -Wait -PassThru
if ($setup.ExitCode -ne 0) { throw "Installer failed: $($setup.ExitCode)" }
try {
    $entry = Get-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{89FD19D0-5CEF-4FEA-936C-6C9558B178D1}_is1'
    if ($entry.DisplayName -ne "Rahul's Toolbox - 3.3.0" -or $entry.DisplayVersion -ne '3.3.0') {
        throw "Installed-app name/version did not match: $($entry.DisplayName) / $($entry.DisplayVersion)"
    }
    Write-Output "Installed-app entry verified: $($entry.DisplayName)"
    $installedIcon = Join-Path $installationFolder 'toolbox-brand.ico'
    if ((Get-FileHash -LiteralPath $installedIcon).Hash -ne (Get-FileHash -LiteralPath (Join-Path $projectRoot 'assets\toolbox.ico')).Hash) {
        throw 'Installed brand icon does not match the application logo.'
    }
    $shortcutPath = Join-Path ([Environment]::GetFolderPath('Programs')) ($verificationGroup + "\Rahul's Toolbox.lnk")
    $shortcutShell = New-Object -ComObject WScript.Shell
    $shortcut = $shortcutShell.CreateShortcut($shortcutPath)
    if (-not (Test-Path -LiteralPath $shortcutPath) -or $shortcut.IconLocation -ne ($installedIcon + ',0')) {
        throw "Installed shortcut did not use the branded icon: $($shortcut.IconLocation)"
    }
    Write-Output 'Installed shortcut uses the verified Toolbox brand icon.'
    $appExe = Join-Path $installationFolder 'RahulsToolbox.exe'
    $check = Start-Process -FilePath $appExe -ArgumentList @('--self-test', ('"' + $resultsFolder + '"')) -WindowStyle Hidden -Wait -PassThru
    Get-Content -LiteralPath (Join-Path $resultsFolder 'self-test.json')
    if ($check.ExitCode -ne 0) { throw "Installed application verification failed: $($check.ExitCode)" }
} finally {
    $uninstaller = Join-Path $installationFolder 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller) {
        $uninstall = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -WindowStyle Hidden -Wait -PassThru
        if ($uninstall.ExitCode -ne 0) { throw "Uninstall verification failed: $($uninstall.ExitCode)" }
    }
}
'Installer, installed application, and uninstaller verified.'
