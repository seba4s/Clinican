"""Abonos: vencimiento, inasistencias y saldo a favor.

Todo el dinero se maneja en pesos enteros (``int``), nunca en ``float``. El
reloj se recibe como parámetro: ninguna función consulta la hora actual.
"""

from __future__ import annotations

from datetime import datetime, timedelta

MINUTOS_EXPIRACION = 30
HORAS_AVISO_INASISTENCIA = 12


def validar_pesos(valor: int, nombre: str = "valor") -> int:
    """Exige un entero >= 0 (rechaza float y bool)."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise TypeError(f"{nombre} debe ser un entero de pesos, no {type(valor).__name__}")
    if valor < 0:
        raise ValueError(f"{nombre} no puede ser negativo")
    return valor


def _con_zona(momento: datetime, nombre: str) -> datetime:
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError(f"{nombre} debe tener zona horaria")
    return momento


def vence_en(creado_en: datetime, minutos: int = MINUTOS_EXPIRACION) -> datetime:
    return _con_zona(creado_en, "creado_en") + timedelta(minutes=minutos)


def esta_vencido(creado_en: datetime, ahora: datetime, minutos: int = MINUTOS_EXPIRACION) -> bool:
    """El abono pendiente vence ``minutos`` después de creado el turno."""
    if minutos <= 0:
        raise ValueError("minutos debe ser positivo")
    return _con_zona(ahora, "ahora") >= vence_en(creado_en, minutos)


def resultado_inasistencia(
    inicio_turno: datetime,
    aviso_en: datetime | None,
    abono: int,
) -> int:
    """Saldo a favor que deja una inasistencia.

    Si el dueño avisó con 12 horas o más de anticipación, el abono completo
    queda como saldo a favor; si no avisó o avisó tarde, se pierde (0).
    """
    validar_pesos(abono, "abono")
    _con_zona(inicio_turno, "inicio_turno")
    if aviso_en is None:
        return 0
    if inicio_turno - _con_zona(aviso_en, "aviso_en") >= timedelta(hours=HORAS_AVISO_INASISTENCIA):
        return abono
    return 0


def aplicar_saldo(saldo: int, abono_requerido: int) -> tuple[int, int, int]:
    """Aplica el saldo a favor al abono del siguiente turno del cliente.

    Devuelve ``(abono_cubierto, saldo_restante, faltante)``.
    """
    validar_pesos(saldo, "saldo")
    validar_pesos(abono_requerido, "abono_requerido")
    cubierto = min(saldo, abono_requerido)
    return cubierto, saldo - cubierto, abono_requerido - cubierto
