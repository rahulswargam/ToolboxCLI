#define AppName "Rahul's Toolbox"
#define AppVersion "3.3.0"

[Setup]
#ifdef VerificationBuild
AppId={{89FD19D0-5CEF-4FEA-936C-6C9558B178D1}
#else
AppId={{FF4C995E-C2D7-40D8-AEEA-3E239EBB2F71}
#endif
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} - {#AppVersion}
UninstallDisplayName={#AppName} - {#AppVersion}
AppPublisher=Rahul Swargam
DefaultDirName={localappdata}\Programs\RahulsToolbox
#ifdef VerificationBuild
DefaultGroupName=RahulsToolbox Verification
#else
DefaultGroupName={#AppName}
#endif
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
WizardStyle=modern
WizardImageFile=..\assets\wizard.bmp
WizardSmallImageFile=..\assets\wizard-small.bmp
WizardImageStretch=yes
SetupIconFile=..\assets\toolbox.ico
UninstallDisplayIcon={app}\toolbox-brand.ico
#ifdef VerificationBuild
OutputDir=..\artifacts\installer-verification-3.3.0
#else
OutputDir=..\release
#endif
OutputBaseFilename=RahulsToolbox-3.3.0-Setup
Compression=lzma2/fast
SolidCompression=yes
LicenseFile=..\THIRD_PARTY_NOTICES.md
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\RahulsToolbox\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\toolbox.ico"; DestDir: "{app}"; DestName: "toolbox-brand.ico"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\RahulsToolbox.exe"; IconFilename: "{app}\toolbox-brand.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\RahulsToolbox.exe"; IconFilename: "{app}\toolbox-brand.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\RahulsToolbox.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
