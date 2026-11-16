"""Reglas de la bandeja de salida: cuándo recordar, reintentos y retención."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

from clinican.dominio.agenda import ZONA
from clinican.dominio.fechas_texto import dia_en_texto, hora_en_texto

TIPO_RECORDATORIO = "recordatorio"
TIPO_RECORDATORIO_FINAL = "recordatorio_final"

ESPERAS_REINTENTO = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15))

DIAS_RETENCION = 90

HORAS_ANTES_RECORDATORIO = 24
HORAS_ANTES_RECORDATORIO_FINAL = 1

PLANTILLA_TEXTO = (
    "Estimado cliente, le recordamos que {dia}, tiene un turno de peluquería para {mascota}, "
    "a las {hora}. En caso de no poder asistir, avisar con anterioridad para evitar pérdida "
    "del saldo abonado. Muchas gracias."
)


def planificar_recordatorios(
    inicio: datetime, anticipaciones: Sequence[tuple[str, int]], ahora: datetime
) -> list[tuple[str, datetime]]:
    """Qué recordatorios programar y cuándo: ``(tipo, momento)``.

    Cada uno sale ``horas`` antes del turno. Si ese momento ya pasó (el turno se
    agendó con menos anticipación), ese recordatorio no se programa: con menos
    de 24 h solo sale el de 1 h, y con menos de 1 h ninguno. 0 horas lo apaga.
    """
    planes: list[tuple[str, datetime]] = []
    for tipo, horas in anticipaciones:
        if isinstance(horas, bool) or not isinstance(horas, int) or horas < 0:
            raise ValueError("Las horas antes del turno deben ser un entero >= 0")
        if horas == 0:
            continue
        cuando = inicio - timedelta(hours=horas)
        if cuando >= ahora and all(cuando != otro for _, otro in planes):
            planes.append((tipo, cuando))
    return planes


def parametros_recordatorio(mascota: str, inicio: datetime, ahora: datetime) -> tuple[str, str, str]:
    """Los 3 datos de la plantilla de WhatsApp: día, mascota y hora (en hora de Colombia).

    «hoy» o «el día de mañana» se calcula con ``ahora``, es decir, al enviar.
    """
    local = inicio.astimezone(ZONA)
    return (
        dia_en_texto(local.date(), ahora.astimezone(ZONA).date()),
        mascota,
        hora_en_texto(local),
    )


def texto_recordatorio(mascota: str, inicio: datetime, ahora: datetime) -> str:
    """El mensaje completo, igual al de la plantilla aprobada en Meta."""
    dia, mascota, hora = parametros_recordatorio(mascota, inicio, ahora)
    return PLANTILLA_TEXTO.format(dia=dia, mascota=mascota, hora=hora)


def espera_tras_fallo(intentos_hechos: int) -> timedelta | None:
    """Espera antes del siguiente intento, o None si ya no quedan reintentos (FALLIDA)."""
    if intentos_hechos < 1:
        raise ValueError("intentos_hechos debe ser al menos 1")
    indice = intentos_hechos - 1
    return ESPERAS_REINTENTO[indice] if indice < len(ESPERAS_REINTENTO) else None


def limite_retencion(ahora: datetime) -> datetime:
    """Los registros cerrados antes de este momento se pueden purgar."""
    return ahora - timedelta(days=DIAS_RETENCION)
