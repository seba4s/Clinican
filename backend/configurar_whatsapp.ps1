# Guarda los datos de WhatsApp (Cloud API de Meta) como variables de entorno de tu usuario de Windows.
# El token NO se escribe en ningún archivo ni en el repositorio.
# Uso, desde la carpeta backend:
#     powershell -ExecutionPolicy Bypass -File .\configurar_whatsapp.ps1
# Para cambiar solo el token (por ejemplo, cuando vence el temporal), vuelve a ejecutarlo y
# deja en blanco lo que no quieras cambiar.

$ErrorActionPreference = "Stop"

function Guardar($nombre, $valor) {
    [Environment]::SetEnvironmentVariable($nombre, $valor, "User")
    Set-Item -Path "Env:$nombre" -Value $valor   # también en esta consola
}

$actualId = [Environment]::GetEnvironmentVariable("CLINICAN_WHATSAPP_NUMERO_ID", "User")
$tieneToken = [bool][Environment]::GetEnvironmentVariable("CLINICAN_WHATSAPP_TOKEN", "User")
Write-Host "Configurar WhatsApp para Clinican"
Write-Host "  Id del número actual: $(if ($actualId) { $actualId } else { '(ninguno)' })"
Write-Host "  Token guardado: $(if ($tieneToken) { 'sí' } else { 'no' })"
Write-Host ""

$seguro = Read-Host "Token de acceso (no se muestra; Enter = no cambiar)" -AsSecureString
$token = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro))
if ($token.Trim()) { Guardar "CLINICAN_WHATSAPP_TOKEN" $token.Trim() }
$token = $null

$numeroId = Read-Host "Identificador del número de teléfono (Phone number ID; Enter = no cambiar)"
if ($numeroId.Trim()) {
    if ($numeroId.Trim() -notmatch '^\d+$') { throw "El identificador del número solo lleva dígitos." }
    Guardar "CLINICAN_WHATSAPP_NUMERO_ID" $numeroId.Trim()
}

$plantilla = Read-Host "Nombre de la plantilla (Enter = recordatorio_turno)"
if ($plantilla.Trim()) { Guardar "CLINICAN_WHATSAPP_PLANTILLA" $plantilla.Trim() }

Write-Host ""
Write-Host "Listo. Cierra y vuelve a abrir Clinican (y las consolas abiertas) para que tome los cambios."
Write-Host "Para probar el envío:  python probar_whatsapp.py 3001234567"
