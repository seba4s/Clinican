$ErrorActionPreference = "Stop"
$frontend = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path (Split-Path -Parent $frontend) ".venv"
$pythonw = Join-Path $venv "Scripts\pythonw.exe"

if (-not (Test-Path $pythonw)) {
    Write-Host "Creando el entorno .venv e instalando dependencias (solo la primera vez)..."
    $python = (Get-Command py -ErrorAction SilentlyContinue)
    if ($python) { & py -3 -m venv $venv } else { & python -m venv $venv }
    & (Join-Path $venv "Scripts\python.exe") -m pip install -r (Join-Path $frontend "requirements.txt")
}

$escritorio = [Environment]::GetFolderPath("Desktop")
$destino = Join-Path $escritorio "Clinican.lnk"
$shell = New-Object -ComObject WScript.Shell
$acceso = $shell.CreateShortcut($destino)
$acceso.TargetPath = $pythonw
$acceso.Arguments = "`"$(Join-Path $frontend 'main.py')`""
$acceso.WorkingDirectory = $frontend
$acceso.IconLocation = (Join-Path $frontend "interfaz\recursos\logo_perro.ico")
$acceso.Description = "Clinican: agenda de la peluquería canina"
$acceso.Save()

Write-Host "Listo: acceso directo creado en $destino"
