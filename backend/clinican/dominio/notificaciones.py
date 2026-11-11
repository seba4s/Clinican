"""Reglas de la bandeja de salida: cuándo recordar, reintentos y retención."""

from __future__ import annotations

from datetime import datetime, timedelta

TIPO_RECORDATORIO = "recordatorio"

# Esperas tras cada intento fallido: máximo 3 reintentos después del primer intento.
ESPERAS_REINTENTO = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15))

# Los registros cerrados (enviados, descartados o fallidos) se purgan después de esto.
DIAS_RETENCION = 90

# Horas de anticipación del recordatorio por defecto (confirmado: 24 h; configurable).
HORAS_ANTES_RECORDATORIO = 24


def hora_recordatorio(inicio: datetime, horas_antes: int, ahora: datetime) -> datetime:
    """Momento de envío: ``horas_antes`` antes del turno, o ya si falta menos que eso."""
    if isinstance(horas_antes, bool) or not isinstance(horas_antes, int) or horas_antes < 0:
        raise ValueError("horas_antes debe ser un entero >= 0")
    return max(inicio - timedelta(hours=horas_antes), ahora)


def espera_tras_fallo(intentos_hechos: int) -> timedelta | None:
    """Espera antes del siguiente intento, o None si ya no quedan reintentos (FALLIDA)."""
    if intentos_hechos < 1:
        raise ValueError("intentos_hechos debe ser al menos 1")
    indice = intentos_hechos - 1
    return ESPERAS_REINTENTO[indice] if indice < len(ESPERAS_REINTENTO) else None


def limite_retencion(ahora: datetime) -> datetime:
    """Los registros cerrados antes de este momento se pueden purgar."""
    return ahora - timedelta(days=DIAS_RETENCION)
