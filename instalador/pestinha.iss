; Instalador do Pestinha para Windows (Inno Setup 6). Instala só para o usuário atual, sem pedir administrador.
; Antes, gere o executável (ver README). Depois, nesta pasta: ISCC pestinha.iss
; Sai em instalador\saida\. A memória fica em %LOCALAPPDATA%\Pestinha e não é apagada ao desinstalar.

#define Versao "0.8.0"

[Setup]
AppId={{7C7C1F0E-5B0A-4B57-9A63-6E2E5A3F8D10}
AppName=Pestinha
AppVersion={#Versao}
DefaultDirName={localappdata}\Programs\Pestinha
DefaultGroupName=Pestinha
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=saida
OutputBaseFilename=Pestinha-{#Versao}-instalador
UninstallDisplayIcon={app}\Pestinha.exe
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalho"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "..\build\onefile\Pestinha.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs
Source: "..\pets\*"; DestDir: "{app}\pets"; Flags: ignoreversion recursesubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\PRIVACIDADE.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Pestinha"; Filename: "{app}\Pestinha.exe"
Name: "{group}\Configurar o Pestinha"; Filename: "{app}\Pestinha.exe"; Parameters: "--configurar"
Name: "{userdesktop}\Pestinha"; Filename: "{app}\Pestinha.exe"; Tasks: atalho

[Registry]
; A opção "abrir ao entrar no Windows" não pode sobreviver ao programa
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "Pestinha"; Flags: dontcreatekey uninsdeletevalue

[Run]
Filename: "{app}\Pestinha.exe"; Description: "Abrir o Pestinha"; Flags: nowait postinstall skipifsilent
