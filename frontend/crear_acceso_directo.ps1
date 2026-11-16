# Crea en el escritorio un acceso directo "Clinican" que abre el programa sin consola.
# Uso (una sola vez), desde la carpeta backend:
#     powershell -ExecutionPolicy Bypass -File .\crear_acceso_directo.ps1
# Si todavía no existe el entorno .venv, lo crea e instala las dependencias.

$ErrorActionPreference = "Stop"
$backend = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $backend ".venv"
$pythonw = Join-Path $venv "Scripts\pythonw.exe"

if (-not (Test-Path $pythonw)) {
    Write-Host "Creando el entorno .venv e instalando dependencias (solo la primera vez)..."
    $python = (Get-Command py -ErrorAction SilentlyContinue)
    if ($python) { & py -3 -m venv $venv } else { & python -m venv $venv }
    & (Join-Path $venv "Scripts\python.exe") -m pip install -r (Join-Path $backend "requirements.txt")
}

$escritorio = [Environment]::GetFolderPath("Desktop")  # funciona aunque el escritorio esté en OneDrive
$destino = Join-Path $escritorio "Clinican.lnk"
$shell = New-Object -ComObject WScript.Shell
$acceso = $shell.CreateShortcut($destino)
$acceso.TargetPath = $pythonw
$acceso.Arguments = "`"$(Join-Path $backend 'main.py')`""
$acceso.WorkingDirectory = $backend
$acceso.IconLocation = (Join-Path $backend "clinican\ui\recursos\logo_perro.ico")
$acceso.Description = "Clinican: agenda de la peluquería canina"
$acceso.Save()

Write-Host "Listo: acceso directo creado en $destino"
