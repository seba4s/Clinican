"""Recordatorios a los dueños (driver D3, ADR-003): reglas puras, sin canal ni base de datos.

El dominio decide **qué** se avisa, **cuándo** y **si se puede** avisar. Cómo se
entrega (WhatsApp, SMS, archivo) lo decide un adaptador fuera del dominio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from clinican.dominio.formato import fecha_larga

# Estados de un mensaje en la bandeja de salida
PENDIENTE = "PENDIENTE"
ENVIADO = "ENVIADO"
DESCARTADO = "DESCARTADO"  # ya no tiene sentido enviarlo (turno cancelado, vencido o sin autorización)
ESTADOS = (PENDIENTE, ENVIADO, DESCARTADO)

PLANTILLA_RECORDATORIO = "recordatorio_turno"
MAX_ESPERA_MINUTOS = 60


@dataclass(frozen=True)
class Mensaje:
    """Lo que el dominio entrega a un canal. El canal no conoce turnos ni mascotas."""

    destino: str  # celular en formato internacional, solo dígitos (57…)
    plantilla: str  # nombre de la plantilla aprobada (WhatsApp) o del formato del canal
    parametros: tuple[str, ...]  # valores para la plantilla, en orden
    texto: str  # el mismo mensaje en texto plano, para canales sin plantillas
    referencia: str = ""  # identificador propio, útil en registros
    extra: dict = field(default_factory=dict, compare=False)


def momento_de_envio(inicio_turno: datetime, horas_antes: int, ahora: datetime) -> datetime:
    """Se avisa ``horas_antes`` horas antes del turno; si ese momento ya pasó, de inmediato."""
    return max(inicio_turno - timedelta(hours=horas_antes), ahora)


def motivo_para_descartar(estado_turno: str, inicio_turno: datetime, ahora: datetime,
                          tiene_autorizacion_datos: bool, tiene_celular: bool) -> str | None:
    """None si el recordatorio se puede enviar; si no, el motivo para descartarlo.

    - Solo se recuerdan turnos confirmados (con abono).
    - Un recordatorio de un turno que ya empezó no sirve.
    - Ley 1581 de 2012: sin autorización vigente de tratamiento de datos no se contacta al dueño.
    """
    if estado_turno != "CONFIRMADO":
        return "El turno ya no está confirmado."
    if inicio_turno <= ahora:
        return "El turno ya empezó: el recordatorio llegaría tarde."
    if not tiene_autorizacion_datos:
        return "El propietario no tiene vigente la autorización de tratamiento de datos (Ley 1581)."
    if not tiene_celular:
        return "El propietario no tiene celular registrado."
    return None


def espera_reintento(intentos: int) -> timedelta:
    """Espera creciente entre intentos fallidos: 1, 2, 4, 8… minutos, hasta una hora."""
    return timedelta(minutes=min(2 ** max(intentos - 1, 0), MAX_ESPERA_MINUTOS))


def celular_internacional(celular: str) -> str:
    """"3014417194" -> "573014417194" (Colombia)."""
    digitos = "".join(c for c in str(celular) if c.isdigit())
    return digitos if digitos.startswith("57") and len(digitos) == 12 else f"57{digitos}"


def recordatorio(celular: str, propietario: str, mascota: str, inicio_turno: datetime, negocio: str,
                 referencia: str = "") -> Mensaje:
    """Mensaje de recordatorio de turno."""
    dia = fecha_larga(inicio_turno.date())
    hora = inicio_turno.strftime("%H:%M")
    nombre = propietario.split()[0] if propietario.strip() else propietario
    texto = (f"Hola, {nombre}. Le recordamos el turno de peluquería de {mascota} el {dia} a las {hora} "
             f"en {negocio}. Si no puede asistir, avísenos con anticipación.")
    return Mensaje(celular_internacional(celular), PLANTILLA_RECORDATORIO,
                   (nombre, mascota, dia, hora, negocio), texto, referencia)
