"""Reglas de ocupación y disponibilidad de franjas para turnos."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from clinican.dominio.abonos import esta_vencido
from clinican.dominio.agenda import ZONA, Bloqueo, Franja, HorarioSemanal, generar_franjas
from clinican.dominio.cupos import CategoriaCupo
from clinican.dominio.entidades import Turno
from clinican.dominio.errores import FranjaNoDisponible
from clinican.dominio.estados import EstadoTurno, ocupa_cupo

# Turnos que todavía no terminaron (bloquear su franja los dejaría sin atender).
ESTADOS_ACTIVOS = frozenset(
    {EstadoTurno.PENDIENTE_ABONO, EstadoTurno.CONFIRMADO, EstadoTurno.EN_ATENCION}
)


def ocupa_franja(turno: Turno, ahora: datetime, minutos_expiracion: int) -> bool:
    """Un pendiente de abono ocupa cupo solo mientras su abono no haya vencido."""
    if turno.estado is EstadoTurno.PENDIENTE_ABONO:
        return not esta_vencido(turno.creado_en, ahora, minutos_expiracion)
    return ocupa_cupo(turno.estado)


def esta_activo(turno: Turno, ahora: datetime, minutos_expiracion: int) -> bool:
    return turno.estado in ESTADOS_ACTIVOS and ocupa_franja(turno, ahora, minutos_expiracion)


def contar_ocupacion(
    turnos: Iterable[Turno],
    ahora: datetime,
    minutos_expiracion: int,
    excluir_id: int | None = None,
) -> dict[CategoriaCupo, int]:
    ocupacion = {c: 0 for c in CategoriaCupo}
    for turno in turnos:
        if turno.id != excluir_id and ocupa_franja(turno, ahora, minutos_expiracion):
            ocupacion[turno.categoria] += 1
    return ocupacion


def _hora(momento: datetime) -> str:
    return momento.astimezone(ZONA).strftime("%H:%M del %d/%m/%Y")


def validar_franja(
    inicio: datetime,
    horario: HorarioSemanal,
    bloqueos: Iterable[Bloqueo],
) -> Franja:
    """Devuelve la franja si es reservable; si no, lanza FranjaNoDisponible."""
    try:
        franja = Franja(inicio)
    except ValueError as error:
        raise FranjaNoDisponible(f"La hora indicada no es una franja válida: {error}") from None
    fecha = franja.inicio.astimezone(ZONA).date()
    if horario.jornada(fecha) is None:
        raise FranjaNoDisponible(f"El {fecha.strftime('%d/%m/%Y')} no se reciben perros")
    if franja not in generar_franjas(fecha, horario):
        raise FranjaNoDisponible(
            f"La franja de las {_hora(franja.inicio)} está fuera del horario de recepción"
        )
    for bloqueo in bloqueos:
        if bloqueo.cubre(franja):
            motivo = f" ({bloqueo.motivo})" if bloqueo.motivo else ""
            raise FranjaNoDisponible(f"La franja de las {_hora(franja.inicio)} está bloqueada{motivo}")
    return franja
