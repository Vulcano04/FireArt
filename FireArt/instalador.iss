#define NombreApp "FireArt"
#define Version "0.1.0"

[Setup]
AppId={{3F7A9C52-8D1B-4E6A-B0C4-71E2A5D9F386}
AppName={#NombreApp}
AppVersion={#Version}
AppPublisher=FireArt
AppComments=Una alternativa limpia y gratuita
DefaultDirName={autopf}\FireArt
DefaultGroupName=FireArt
OutputDir=salida
OutputBaseFilename=FireArt-Instalador
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
UninstallDisplayName=FireArt
ChangesAssociations=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "icono"; Description: "Crear un acceso directo en el &escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\FireArt\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FireArt"; Filename: "{app}\FireArt.exe"
Name: "{group}\Desinstalar FireArt"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FireArt"; Filename: "{app}\FireArt.exe"; Tasks: icono

[Registry]
Root: HKA; Subkey: "Software\Classes\.fireart"; ValueType: string; ValueData: "FireArt.Proyecto"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\FireArt.Proyecto"; ValueType: string; ValueData: "Proyecto de FireArt"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\FireArt.Proyecto\shell\open\command"; ValueType: string; ValueData: """{app}\FireArt.exe"" ""%1"""

[Run]
Filename: "{app}\FireArt.exe"; Description: "Abrir FireArt"; Flags: nowait postinstall skipifsilent
