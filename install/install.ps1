# Instalador da Patentometria para Windows (sem administrador).
$ErrorActionPreference = "Stop"
$Ver = "0.3.1"
$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$Wheel = Join-Path $Aqui "patentometria-$Ver-py3-none-any.whl"

if (-not (Test-Path $Wheel)) {
    Write-Host "ERRO: wheel nao encontrado em $Wheel" -ForegroundColor Red
    Read-Host "Pressione Enter para fechar"
    exit 1
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Instalando uv (gerenciador de Python)..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

Write-Host "Instalando Patentometria $Ver..."
uv tool install --force $Wheel

$Shim = Join-Path $env:USERPROFILE ".local\bin\patentometria.exe"
if (-not (Test-Path $Shim)) {
    Write-Host "ERRO: patentometria.exe nao encontrado apos a instalacao." -ForegroundColor Red
    Read-Host "Pressione Enter para fechar"
    exit 1
}

$Ws = New-Object -ComObject WScript.Shell

$AtalhoDesktop = $Ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Patentometria.lnk"))
$AtalhoDesktop.TargetPath = $Shim
$AtalhoDesktop.WorkingDirectory = $env:USERPROFILE
$AtalhoDesktop.Description = "Analise patentometrica (PGEN1075/UFES)"
$AtalhoDesktop.Save()

$MenuIniciar = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"
New-Item -ItemType Directory -Force -Path $MenuIniciar | Out-Null
$AtalhoMenu = $Ws.CreateShortcut((Join-Path $MenuIniciar "Patentometria.lnk"))
$AtalhoMenu.TargetPath = $Shim
$AtalhoMenu.WorkingDirectory = $env:USERPROFILE
$AtalhoMenu.Description = "Analise patentometrica (PGEN1075/UFES)"
$AtalhoMenu.Save()

& $Shim --check
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: verificacao falhou." -ForegroundColor Red
    Read-Host "Pressione Enter para fechar"
    exit 1
}

Write-Host ""
Write-Host "Pronto. Atalhos criados no Desktop e no Menu Iniciar." -ForegroundColor Green
$Dados = & $Shim where
Write-Host "Pasta de dados: $Dados"
Read-Host "Pressione Enter para fechar"
